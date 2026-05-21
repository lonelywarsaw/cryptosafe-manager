from __future__ import annotations

import os
import tempfile
import time
import tracemalloc
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat

import database.db as db_module

from core.audit.log_verifier import verify_audit_chain
from core.audit import audit_logger


class TestSprint5AuditPerformance(unittest.TestCase):
    """Тесты производительности журнала аудита (Спринт 5)"""
    _rows_10k: list[dict] | None = None  # кэш для PERF-3 и PERF-4

    def setUp(self) -> None:
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)

        db_module.set_db_path(self.path)
        db_module.init_db()

        private_key = Ed25519PrivateKey.generate()
        self.seed = private_key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())

    def tearDown(self) -> None:
        try:
            os.remove(self.path)
        except OSError:
            pass
        db_module.set_db_path(None)

    def _db_patches(self):
        return [
            patch("core.audit.log_signer.derive_audit_signing_key", return_value=self.seed),
            patch("core.key_manager.get_encryption_key", return_value=b"test_key_32_bytes_long!!"),
        ]

    def _start_patches(self, patches):
        for p in patches:
            p.start()

    def _stop_patches(self, patches):
        for p in reversed(patches):
            p.stop()

    def _write_logs(self, count: int) -> None:
        """Записывает count событий в тестовую БД"""
        db_module.set_db_path(self.path)
        patches = self._db_patches()
        self._start_patches(patches)
        try:
            for i in range(count):
                audit_logger._log_event(
                    "ClipboardCopied",
                    entry_id=i,
                    details=f"source=perf, n={i}"
                )
        finally:
            self._stop_patches(patches)

    def _load_10k_rows(self) -> list[dict]:
        """Загружает 10000 записей (лениво, один раз)"""
        if TestSprint5AuditPerformance._rows_10k is None:
            self._write_logs(10000)
            # Гарантируем, что SQLite успел закоммитить
            time.sleep(0.05)

            rows = db_module.list_audit_logs(limit=10000)
            if not rows:
                rows = db_module.list_audit_logs()[:10000]

            TestSprint5AuditPerformance._rows_10k = rows
            self.assertGreater(len(rows), 0, "БД пуста! Проверьте патчи и передачу string в details")
        return TestSprint5AuditPerformance._rows_10k

    def test_perf1_log_under_10ms(self) -> None:
        """PERF-1: одна запись в журнал < 10 ms"""
        db_module.set_db_path(self.path)
        patches = self._db_patches()
        self._start_patches(patches)
        try:
            t0 = time.perf_counter()
            audit_logger._log_event("ClipboardCopied", details="source=perf")
            dt_ms = (time.perf_counter() - t0) * 1000.0
        finally:
            self._stop_patches(patches)
        self.assertLess(dt_ms, 10.0)

    def test_perf2_verify_1000_under_1s(self) -> None:
        """PERF-2: проверка 1000 записей < 1 с"""
        db_module.set_db_path(self.path)
        patches = self._db_patches()
        self._start_patches(patches)
        try:
            for i in range(1000):
                audit_logger._log_event("ClipboardCopied", entry_id=i, details=f"source=perf, n={i}")

            rows = db_module.list_audit_logs(limit=1000)
            if not rows: rows = db_module.list_audit_logs()[:1000]

            t0 = time.perf_counter()
            # Ваша реальная функция: возвращает dict {"verified": bool, "breaks": list, ...}
            result = verify_audit_chain(rows, signer=None)
            dt = time.perf_counter() - t0
        finally:
            self._stop_patches(patches)

        self.assertTrue(result["verified"], f"Цепочка нарушена: {result['breaks']}")
        self.assertLess(dt, 1.0)

    def test_perf3_filter_10000_under_500ms(self) -> None:
        """PERF-3: фильтр 10000 записей < 500 ms"""
        rows = self._load_10k_rows()
        t0 = time.perf_counter()
        filtered = [r for r in rows if "clipboard" in (r.get("action", "") or "").lower()]
        dt_ms = (time.perf_counter() - t0) * 1000.0
        self.assertLess(dt_ms, 500.0)

    def test_perf4_viewer_memory_under_50mb(self) -> None:
        """PERF-4: загрузка 10000 записей, память < 50 MB"""
        rows = self._load_10k_rows()
        tracemalloc.start()
        items = [dict(r) for r in rows]
        filtered = [i for i in items if "clipboard" in (i.get("action", "") or "").lower()]
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        self.assertEqual(len(items), 10000)
        self.assertLess(peak, 50 * 1024 * 1024)

    def test_perf5_async_logging(self) -> None:
        """PERF-5: publish не ждёт асинхронной записи"""
        db_module.set_db_path(self.path)
        patches = self._db_patches()
        self._start_patches(patches)
        try:
            t0 = time.perf_counter()
            audit_logger._log_event("ClipboardCopied", details="source=perf")
            dt_ms = (time.perf_counter() - t0) * 1000.0
            time.sleep(0.3)
            rows = db_module.list_audit_logs(limit=10)
            if not rows: rows = db_module.list_audit_logs()[:10]
        finally:
            self._stop_patches(patches)
        self.assertLess(dt_ms, 10.0)
        self.assertGreaterEqual(len(rows), 1)


if __name__ == "__main__":
    unittest.main()