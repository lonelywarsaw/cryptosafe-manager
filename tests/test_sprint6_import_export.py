# Спринт 6 — TEST-1..TEST-5 (TRD §10)

import pytest

import json
import os
import sqlite3
import tempfile
import tracemalloc
import unittest
from unittest.mock import patch

import database.db as db_module
from core.import_export.exporter import ExportOptions, VaultExporter
from core.import_export.importer import VaultImporter
from core.import_export.key_exchange import generate_rsa_keypair
from core.import_export.sharing_service import SharingService
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
            "title": f"Site-{i}",
            "username": f"user{i}",
            "password": f"Secret{i}!",
            "url": f"https://site{i}.example.com",
            "notes": f"note {i}",
            "category": "work",
        }
        for i in range(count)
    ]


class TestSprint6Validation(unittest.TestCase):
    def setUp(self) -> None:
        fd, self._db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        db_module.set_db_path(self._db_path)
        db_module.init_db()
        _apply_fast_sqlite_pragmas(self._db_path)
        set_encryption_key(b"x" * 32)
        self._entries = _sample_entries(5)
        self._created: list = []

    def tearDown(self) -> None:
        db_module.set_db_path(None)
        try:
            os.remove(self._db_path)
        except OSError:
            pass

    def _exporter(self) -> VaultExporter:
        return VaultExporter(lambda: list(self._entries))

    def _importer(self) -> VaultImporter:
        def create(entry):
            row = dict(entry)
            row["id"] = len(self._created) + 1
            self._created.append(row)
            return row

        def delete_all():
            conn = sqlite3.connect(self._db_path)
            try:
                conn.execute("DELETE FROM vault_entries")
                conn.commit()
            finally:
                conn.close()
            self._created.clear()

        return VaultImporter(create_entry=create, list_entries=lambda: list(self._created), delete_all=delete_all)

    @patch("core.import_export.exporter.verify_master_password", return_value=True)
    @patch("core.import_export.importer.verify_master_password", return_value=True)
    def test_test1_roundtrip_all_formats(self, *_mocks) -> None:
        """TEST-1: экспорт форматов → импорт → целостность данных."""
        exporter = self._exporter()
        importer = self._importer()
        options = ExportOptions(include_notes=True)

        cases = []

        pkg = exporter.export_encrypted_json(EXPORT_PASS, master_password=MASTER, options=options)
        path = self._write_json(pkg)
        cases.append(("encrypted_json", path, EXPORT_PASS, None))

        bw_enc = exporter.export_bitwarden_encrypted_json(EXPORT_PASS, master_password=MASTER, options=options)
        path = self._write_json(bw_enc)
        cases.append(("bitwarden_encrypted_json", path, EXPORT_PASS, None))

        lp_enc = exporter.export_lastpass_encrypted_json(EXPORT_PASS, master_password=MASTER, options=options)
        path = self._write_json(lp_enc)
        cases.append(("lastpass_encrypted_json", path, EXPORT_PASS, None))

        priv, pub = generate_rsa_keypair()
        rsa_pkg = exporter.export_encrypted_json(
            EXPORT_PASS,
            master_password=MASTER,
            options=ExportOptions(include_notes=True, recipient_public_key_pem=pub),
        )
        path = self._write_json(rsa_pkg)
        cases.append(("encrypted_json_rsa", path, EXPORT_PASS, priv))

        csv_text = exporter.export_csv(encrypt=False, options=options)
        path = self._write_text(csv_text, ".csv")
        cases.append(("csv", path, "", None))

        bw_text = exporter.export_bitwarden(options=options)
        path = self._write_text(bw_text, ".json")
        cases.append(("bitwarden", path, "", None))

        lp_text = exporter.export_lastpass_csv(options=options)
        path = self._write_text(lp_text, ".txt")
        cases.append(("lastpass_csv", path, "", None))

        for _name, file_path, exp_pass, priv in cases:
            preview = importer.parse_file(file_path, export_password=exp_pass, private_key_pem=priv)
            self.assertEqual(len(preview), len(self._entries))
            self._assert_entries_match(preview, self._entries)
            self._created.clear()
            result = importer.import_file(
                file_path,
                "merge",
                master_password=MASTER,
                export_password=exp_pass,
                private_key_pem=priv,
            )
            self.assertEqual(len(result.added), len(self._entries))
            self.assertEqual(result.added[0]["title"], self._entries[0]["title"])
            self.assertEqual(result.added[0]["password"], self._entries[0]["password"])

    @patch("core.import_export.exporter.verify_master_password", return_value=True)
    @patch("core.import_export.importer.verify_master_password", return_value=True)
    def test_test2_interoperability_bitwarden_lastpass(self, *_mocks) -> None:
        """TEST-2: импорт Bitwarden/LastPass и обратный экспорт."""
        exporter = self._exporter()
        importer = self._importer()
        options = ExportOptions()

        bw_src = (
            '{"encrypted": false, "items": [{"type": 1, "name": "BW", "login": '
            '{"username": "bwuser", "password": "bwpass", "uris": [{"uri": "https://bw.example"}]}, '
            '"notes": "n", "folder": "f"}]}'
        )
        bw_path = self._write_text(bw_src, ".json")
        bw_entries = importer.parse_file(bw_path)
        self.assertEqual(bw_entries[0]["title"], "BW")
        self.assertEqual(bw_entries[0]["password"], "bwpass")
        bw_exporter = VaultExporter(lambda: bw_entries)
        out_bw = bw_exporter.export_bitwarden(options=options)
        self.assertIn('"BW"', out_bw)

        lp_src = "url,username,password,extra,name,grouping,fav\nhttps://lp.example,lpuser,lppass,extra,LP,grp,0\n"
        lp_path = self._write_text(lp_src, ".txt")
        lp_entries = importer.parse_file(lp_path)
        self.assertEqual(lp_entries[0]["title"], "LP")
        lp_exporter = VaultExporter(lambda: lp_entries)
        out_lp = lp_exporter.export_lastpass_csv(options=options)
        self.assertIn("lpuser", out_lp)

        enc_bw = bw_exporter.export_bitwarden_encrypted_json(EXPORT_PASS, master_password=MASTER, options=options)
        enc_path = self._write_json(enc_bw)
        roundtrip = importer.parse_file(enc_path, export_password=EXPORT_PASS)
        self.assertEqual(roundtrip[0]["username"], "bwuser")

    def test_test3_sharing_security_tamper_rejected(self) -> None:
        """TEST-3: share по паролю/RSA + отклонение подмены."""
        svc = SharingService()
        entry = self._entries[0]

        pwd_pkg = svc.create_password_share(entry, "share-secret", expires_days=2, permission="read_only")
        decoded = svc.import_share(pwd_pkg, share_password="share-secret")
        self.assertEqual(decoded["username"], entry["username"])

        priv, pub = generate_rsa_keypair()
        rsa_pkg = svc.create_public_key_share(entry, pub, expires_days=3, permission="editable")
        decoded_rsa = svc.import_share(rsa_pkg, private_key_pem=priv)
        self.assertEqual(decoded_rsa["password"], entry["password"])

        tampered = json.loads(json.dumps(pwd_pkg))
        tampered["integrity"]["hmac"] = "00" * 64
        with self.assertRaises(ValueError):
            svc.import_share(tampered, share_password="share-secret")

    def test_test4_qr_1kb_integrity(self) -> None:
        """TEST-4: QR ~1KB payload, encode/decode, целостность."""
        payload_data = {"blob": "x" * 1000, "meta": "qr-test"}
        built = qr_codec.build_payload("share_package", payload_data)
        chunks = qr_codec.encode_chunks(built)
        self.assertGreaterEqual(len(chunks), 1)
        decoded = qr_codec.decode_chunks(chunks)
        self.assertEqual(decoded["type"], "share_package")
        self.assertEqual(decoded["data"]["blob"], "x" * 1000)

        try:
            png = qr_codec.render_qr_png(chunks[0], error_correction="M")
            self.assertGreater(len(png), 100)
        except RuntimeError:
            self.skipTest("qrcode not installed")

    @patch("core.import_export.exporter.verify_master_password", return_value=True)
    @patch("core.import_export.importer.verify_master_password", return_value=True)
    @pytest.mark.slow
    def test_test5_export_import_1000_entries(self, *_mocks) -> None:
        """TEST-5: экспорт/импорт 1000 записей, замер памяти."""
        big = _sample_entries(1000)
        exporter = VaultExporter(lambda: big)
        importer = self._importer()

        pkg = exporter.export_encrypted_json(EXPORT_PASS, master_password=MASTER, options=ExportOptions())
        path = self._write_json(pkg)
        parsed = importer.parse_file(path, export_password=EXPORT_PASS)
        self.assertEqual(len(parsed), 1000)
        file_size = os.path.getsize(path)
        tracemalloc.start()
        snap0 = tracemalloc.take_snapshot()
        result = importer.import_file(path, "dry_run", master_password=MASTER, export_password=EXPORT_PASS)
        snap1 = tracemalloc.take_snapshot()
        tracemalloc.stop()
        self.assertEqual(len(result.added), 1000)
        self._assert_memory_within_2x_file(snap0, snap1, file_size)

    def _assert_memory_within_2x_file(self, snap0, snap1, file_size: int) -> None:
        diff = snap1.compare_to(snap0, "lineno")
        peak = sum(stat.size_diff for stat in diff if stat.size_diff > 0)
        self.assertLess(peak, max(2 * file_size, 1024))

    def _assert_entries_match(self, got, expected) -> None:
        by_title = {(e.get("title"), e.get("username")): e for e in got}
        for exp in expected:
            key = (exp.get("title"), exp.get("username"))
            self.assertIn(key, by_title)
            self.assertEqual(by_title[key].get("password"), exp.get("password"))

    def _write_json(self, data) -> str:
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return path

    def _write_text(self, text: str, suffix: str = ".txt") -> str:
        fd, path = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path


if __name__ == "__main__":
    unittest.main()
