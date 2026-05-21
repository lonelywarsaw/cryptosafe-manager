import json
import os
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat

import database.db as db_module
from core.audit.integrity import verify_integrity
from core.audit import audit_logger
from core.audit.log_verifier import verify_audit_chain
from core.audit.log_signer import AuditLogSigner


class TestAuditSprint5Validation(unittest.TestCase):
    """Приемочные тесты журнала аудита (Спринт 5)"""

    def setUp(self) -> None:
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)

        db_module.set_db_path(self.path)
        db_module.init_db()

        private_key = Ed25519PrivateKey.generate()
        self.seed = private_key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
        self.password = "test-password"

    def tearDown(self) -> None:
        try:
            os.remove(self.path)
        except OSError:
            pass
        db_module.set_db_path(None)

    def _patches(self):
        return [
            patch("core.audit.audit_logger.derive_audit_signing_key", return_value=self.seed),
            patch("core.audit.audit_logger.get_encryption_key", return_value=b"test_key_32_bytes_long!!"),
            patch("core.config.get", return_value="10000", create=True),
        ]

    def _start_patches(self, patches):
        for p in patches:
            p.start()

    def _stop_patches(self, patches):
        for p in reversed(patches):
            p.stop()

    def _write_logs(self, count: int) -> None:
        patches = self._patches()
        self._start_patches(patches)
        try:
            for i in range(count):
                audit_logger._log_event("ClipboardCopied", entry_id=i, details=f"source=test, n={i}")
            time.sleep(0.05)
        finally:
            self._stop_patches(patches)

    def test_test1_integrity_tamper_detected(self) -> None:
        """TEST-1: вмешательство в журнал обнаруживается"""
        self._write_logs(1000)

        conn = sqlite3.connect(self.path)
        try:
            conn.execute("UPDATE audit_log SET signature = 'tampered' WHERE id = 500")
            conn.commit()
        finally:
            conn.close()

        patches = self._patches()
        self._start_patches(patches)
        try:
            result = verify_integrity()
        finally:
            self._stop_patches(patches)

        self.assertFalse(result["verified"], "verify_integrity должен обнаружить tampering")

    def test_test2_performance_throughput(self) -> None:
        """TEST-2: throughput записи и время проверки цепочки"""
        patches = self._patches()
        self._start_patches(patches)
        try:
            t0 = time.perf_counter()
            for i in range(10000):
                audit_logger._log_event("ClipboardCopied", entry_id=i, details=f"source=perf, n={i}")
            log_time = time.perf_counter() - t0
            time.sleep(0.1)

            rows = db_module.list_audit_logs(limit=10000)
            rows_asc = list(reversed(rows))

            t1 = time.perf_counter()
            signer = AuditLogSigner(self.seed)
            res = verify_audit_chain(rows_asc, signer)
            verify_time = time.perf_counter() - t1
        finally:
            self._stop_patches(patches)

        throughput = 10000.0 / log_time if log_time > 0 else 0.0
        self.assertGreater(throughput, 0.0)
        self.assertTrue(res["verified"], f"Цепочка нарушена: {res['breaks']}")
        self.assertLess(verify_time, 10.0, "Проверка 10000 записей должна занять < 10 с")

    def test_test3_export_import_verify(self) -> None:
        """TEST-3: экспорт/импорт с проверкой подписи"""
        self._write_logs(50)
        rows = db_module.list_audit_logs(limit=50)
        rows_asc = list(reversed(rows))

        patches = self._patches()
        self._start_patches(patches)
        try:
            signer = AuditLogSigner(self.seed)
            res = verify_audit_chain(rows_asc, signer)
            self.assertTrue(res["verified"], f"Подписи не совпали: {res['breaks']}")

            # Симуляция экспорта/импорта через JSON
            export_data = json.dumps([dict(r) for r in rows], default=str)
            imported = json.loads(export_data)
            self.assertEqual(len(imported), 50)

            for row in imported:
                self.assertIn("signature", row)
                self.assertTrue(len(row["signature"]) > 0)
        finally:
            self._stop_patches(patches)

    def test_test4_failure_recovery(self) -> None:
        """TEST-4: порча БД → обнаружение → восстановление"""
        self._write_logs(10)
        conn = sqlite3.connect(self.path)
        try:
            conn.execute("UPDATE audit_log SET entry_data = ? WHERE id = 1", (b"broken",))
            conn.commit()
        finally:
            conn.close()

        patches = self._patches()
        self._start_patches(patches)
        try:
            result = verify_integrity()
            self.assertFalse(result["verified"], "Порча entry_data должна ломать проверку")
        finally:
            self._stop_patches(patches)

        conn = sqlite3.connect(self.path)
        try:
            conn.execute("DELETE FROM audit_log")
            conn.commit()
        finally:
            conn.close()

        for p in patches: p.start()
        try:
            result2 = verify_integrity()
            self.assertTrue(result2["verified"], "После очистки журнал должен быть валиден")
        finally:
            for p in reversed(patches): p.stop()

    def test_test5_security_sql_and_tamper(self) -> None:
        """TEST-5: SQL injection и tampering блокируются"""
        patches = self._patches()
        self._start_patches(patches)
        try:
            sql_attack = "'; DROP TABLE audit_log; --"
            audit_logger._log_event("UserLoggedIn", details=f"comment={sql_attack}, password=secret")
            time.sleep(0.05)

            conn = sqlite3.connect(self.path)
            try:
                cur = conn.cursor()
                cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='audit_log'")
                self.assertIsNotNone(cur.fetchone(), "SQL injection не должен удалять таблицу")
            finally:
                conn.close()

            rows = db_module.list_audit_logs(limit=1)
            self.assertEqual(len(rows), 1)
            entry_data = rows[0].get("entry_data") or b""
            if isinstance(entry_data, memoryview):
                entry_data = entry_data.tobytes()
            parsed = json.loads(entry_data.decode("utf-8"))
            details_str = parsed.get("details", "")
            self.assertIn("[REDACTED]", details_str, "details должен содержать [REDACTED]")

            conn = sqlite3.connect(self.path)
            try:
                conn.execute("UPDATE audit_log SET signature = 'hack' WHERE id = ?", (rows[0]["id"],))
                conn.commit()
            finally:
                conn.close()

            result = verify_integrity()
            self.assertFalse(result["verified"], "Подмена подписи должна обнаруживаться")
        finally:
            self._stop_patches(patches)


if __name__ == "__main__":
    unittest.main()