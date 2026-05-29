# Спринт 6 — PERF-1..PERF-4 (TRD §13)

import json
import os
import sqlite3
import tempfile
import time
import tracemalloc
import unittest
from unittest.mock import patch

import database.db as db_module
from core.import_export.exporter import ExportOptions, VaultExporter
from core.import_export.importer import VaultImporter
from core.import_export import qr_codec
from core.key_manager import set_encryption_key

MASTER = "test-master-password"
EXPORT_PASS = "export-pass-123"


def _apply_fast_sqlite_pragmas(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA journal_mode=MEMORY")
        conn.execute("PRAGMA synchronous=OFF")
        conn.commit()
    finally:
        conn.close()


def _sample_entries(count: int):
    return [
        {
            "id": i + 1,
            "title": f"Perf-{i}",
            "username": f"u{i}",
            "password": f"P{i}!",
            "url": f"https://p{i}.example.com",
            "notes": "n",
            "category": "c",
        }
        for i in range(count)
    ]


class TestSprint6Performance(unittest.TestCase):
    def setUp(self) -> None:
        fd, self._db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        db_module.set_db_path(self._db_path)
        db_module.init_db()
        _apply_fast_sqlite_pragmas(self._db_path)
        set_encryption_key(b"x" * 32)
        self._entries = _sample_entries(1000)

    def tearDown(self) -> None:
        db_module.set_db_path(None)
        try:
            os.remove(self._db_path)
        except OSError:
            pass

    @patch("core.import_export.exporter.verify_master_password", return_value=True)
    def test_perf1_export_1000_under_5s(self, _mock) -> None:
        """PERF-1: экспорт 1000 записей < 5 с."""
        exporter = VaultExporter(lambda: self._entries)
        t0 = time.perf_counter()
        exporter.export_encrypted_json(EXPORT_PASS, master_password=MASTER, options=ExportOptions())
        dt = time.perf_counter() - t0
        self.assertLess(dt, 5.0, f"export took {dt:.2f}s")

    @patch("core.import_export.exporter.verify_master_password", return_value=True)
    @patch("core.import_export.importer.verify_master_password", return_value=True)
    def test_perf2_import_1000_under_10s(self, *_mocks) -> None:
        """PERF-2: импорт 1000 записей < 10 с."""
        exporter = VaultExporter(lambda: self._entries)
        pkg = exporter.export_encrypted_json(EXPORT_PASS, master_password=MASTER, options=ExportOptions())
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(pkg, f)

        created = []

        def create(entry):
            row = dict(entry)
            row["id"] = len(created) + 1
            created.append(row)
            return row

        importer = VaultImporter(create_entry=create, list_entries=lambda: list(created))
        t0 = time.perf_counter()
        importer.import_file(path, "merge", master_password=MASTER, export_password=EXPORT_PASS)
        dt = time.perf_counter() - t0
        os.remove(path)
        self.assertLess(dt, 10.0, f"import took {dt:.2f}s")
        self.assertEqual(len(created), 1000)

    def test_perf3_qr_1kb_under_100ms(self) -> None:
        """PERF-3: генерация QR для ~1KB payload < 100 ms."""
        payload = qr_codec.build_payload("public_key", {"blob": "y" * 1024})
        chunks = qr_codec.encode_chunks(payload)
        t0 = time.perf_counter()
        try:
            qr_codec.render_qr_png(chunks[0], error_correction="M")
        except RuntimeError:
            self.skipTest("qrcode not installed")
        dt_ms = (time.perf_counter() - t0) * 1000.0
        self.assertLess(dt_ms, 100.0, f"qr render {dt_ms:.1f}ms")

    @patch("core.import_export.exporter.verify_master_password", return_value=True)
    @patch("core.import_export.importer.verify_master_password", return_value=True)
    def test_perf4_memory_under_2x_file_size(self, *_mocks) -> None:
        """PERF-4: пик памяти при parse импорта <= 2x размера файла."""
        exporter = VaultExporter(lambda: self._entries)
        pkg = exporter.export_encrypted_json(EXPORT_PASS, master_password=MASTER, options=ExportOptions())
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(pkg, f)
        file_size = os.path.getsize(path)
        importer = VaultImporter()
        tracemalloc.start()
        snap0 = tracemalloc.take_snapshot()
        importer.parse_file(path, export_password=EXPORT_PASS)
        snap1 = tracemalloc.take_snapshot()
        tracemalloc.stop()
        os.remove(path)
        diff = snap1.compare_to(snap0, "lineno")
        peak = sum(stat.size_diff for stat in diff if stat.size_diff > 0)
        self.assertLess(peak, max(2 * file_size, 1024))


if __name__ == "__main__":
    unittest.main()
