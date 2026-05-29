import base64
import json
import os
import sqlite3
import tempfile
import time
import unittest
from typing import Any, Dict, List
from unittest.mock import patch

import database.db as db_module
from core.audit.integrity import verify_integrity
from core.audit import audit_logger
from core.audit.log_signer import AuditLogSigner
from core.audit.log_verifier import verify_audit_chain

SIGNING_KEY = b"test_audit_signing_key_32bytes!!"
ENC_KEY = b"test_key_32_bytes_long!!"


def _apply_fast_sqlite_pragmas(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA journal_mode=MEMORY")
        conn.execute("PRAGMA synchronous=OFF")
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.commit()
    finally:
        conn.close()


def _row_to_export_dict(row: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(row)
    ed = out.get("entry_data")
    if isinstance(ed, memoryview):
        ed = ed.tobytes()
    if isinstance(ed, bytes):
        out["entry_data"] = base64.b64encode(ed).decode("ascii")
    return out


def _row_from_export_dict(row: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(row)
    ed = out.get("entry_data")
    if isinstance(ed, str):
        out["entry_data"] = base64.b64decode(ed.encode("ascii"))
    return out


def _export_signed_audit_json(rows: List[Dict[str, Any]], signing_key: bytes) -> str:
    rows_asc = sorted(rows, key=lambda r: int(r.get("sequence_number") or r.get("id") or 0))
    signer = AuditLogSigner(signing_key)
    check = verify_audit_chain(rows_asc, signer)
    if not check["verified"]:
        raise ValueError(f"export refused: {check['breaks']}")
    payload = {
        "cryptosafe_audit_export": True,
        "version": "1.0",
        "entry_count": len(rows_asc),
        "entries": [_row_to_export_dict(r) for r in rows_asc],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _import_signed_audit_json(text: str) -> List[Dict[str, Any]]:
    data = json.loads(text)
    if not data.get("cryptosafe_audit_export"):
        raise ValueError("not an audit export")
    return [_row_from_export_dict(r) for r in (data.get("entries") or [])]


def _verify_export_independent(export_text: str, signing_key: bytes) -> Dict[str, Any]:
    rows = _import_signed_audit_json(export_text)
    return verify_audit_chain(rows, AuditLogSigner(signing_key))


def _reimport_rows_to_db(db_path: str, rows: List[Dict[str, Any]]) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("DELETE FROM audit_log")
        for row in rows:
            conn.execute(
                """INSERT INTO audit_log
                   (action, timestamp, entry_id, details, signature, sequence_number, previous_hash, entry_data, public_key)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    row.get("action"),
                    row.get("timestamp"),
                    row.get("entry_id"),
                    row.get("details"),
                    row.get("signature"),
                    row.get("sequence_number"),
                    row.get("previous_hash"),
                    row.get("entry_data"),
                    row.get("public_key"),
                ),
            )
        conn.commit()
    finally:
        conn.close()


class TestAuditSprint5Validation(unittest.TestCase):
    """Приемочные тесты журнала аудита (Спринт 5, TEST-1..5)."""

    def setUp(self) -> None:
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        db_module.set_db_path(self.path)
        db_module.init_db()
        _apply_fast_sqlite_pragmas(self.path)
        self.signing_key = SIGNING_KEY

    def tearDown(self) -> None:
        try:
            os.remove(self.path)
        except OSError:
            pass
        db_module.set_db_path(None)

    def _patches(self):
        return [
            patch("core.audit.audit_logger.derive_audit_signing_key", return_value=self.signing_key),
            patch("core.audit.log_signer.derive_audit_signing_key", return_value=self.signing_key),
            patch("core.audit.integrity.derive_audit_signing_key", return_value=self.signing_key),
            patch("core.audit.audit_logger.get_encryption_key", return_value=ENC_KEY),
            patch("core.audit.integrity.get_encryption_key", return_value=ENC_KEY),
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
        finally:
            self._stop_patches(patches)

    def test_test1_integrity_tamper_detected(self) -> None:
        """TEST-1: 1000 записей → tamper → detect."""
        self._write_logs(1000)

        conn = sqlite3.connect(self.path)
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM audit_log ORDER BY id LIMIT 1 OFFSET 499")
            row = cur.fetchone()
            self.assertIsNotNone(row)
            cur.execute("UPDATE audit_log SET signature = 'tampered' WHERE id = ?", (row[0],))
            conn.commit()
        finally:
            conn.close()

        patches = self._patches()
        self._start_patches(patches)
        try:
            result = verify_integrity()
        finally:
            self._stop_patches(patches)

        self.assertFalse(result["verified"])
        self.assertGreater(len(result.get("breaks") or []), 0)

    def test_test2_performance_throughput(self) -> None:
        """TEST-2: 10 000 событий, throughput и verify < 10 с."""
        patches = self._patches()
        self._start_patches(patches)
        try:
            t0 = time.perf_counter()
            for i in range(10000):
                audit_logger._log_event("ClipboardCopied", entry_id=i, details=f"source=perf, n={i}")
            log_time = time.perf_counter() - t0

            rows = db_module.list_audit_logs(limit=10000)
            rows_asc = list(reversed(rows))

            t1 = time.perf_counter()
            signer = AuditLogSigner(self.signing_key)
            res = verify_audit_chain(rows_asc, signer)
            verify_time = time.perf_counter() - t1
        finally:
            self._stop_patches(patches)

        throughput = 10000.0 / log_time if log_time > 0 else 0.0
        self.assertGreaterEqual(throughput, 200.0, f"throughput={throughput:.0f} записей/с")
        self.assertTrue(res["verified"], f"цепочка: {res['breaks']}")
        self.assertLess(verify_time, 10.0)

    def test_test3_export_import_verify(self) -> None:
        """TEST-3: signed JSON export → independent verify → reimport → integrity."""
        self._write_logs(50)
        rows = db_module.list_audit_logs(limit=50)

        export_text = _export_signed_audit_json(rows, self.signing_key)
        independent = _verify_export_independent(export_text, self.signing_key)
        self.assertTrue(independent["verified"], independent.get("breaks"))

        imported_rows = _import_signed_audit_json(export_text)
        self.assertEqual(len(imported_rows), 50)

        conn = sqlite3.connect(self.path)
        try:
            conn.execute("DELETE FROM audit_log")
            conn.commit()
        finally:
            conn.close()

        _reimport_rows_to_db(self.path, imported_rows)

        patches = self._patches()
        self._start_patches(patches)
        try:
            result = verify_integrity()
        finally:
            self._stop_patches(patches)

        self.assertTrue(result["verified"], result.get("breaks"))

    def test_test4_failure_recovery(self) -> None:
        """TEST-4: corruption → detect → recovery из экспорта."""
        self._write_logs(10)
        rows = db_module.list_audit_logs(limit=10)
        backup = _export_signed_audit_json(rows, self.signing_key)

        conn = sqlite3.connect(self.path)
        try:
            conn.execute("UPDATE audit_log SET entry_data = ? WHERE id = (SELECT MIN(id) FROM audit_log)", (b"broken",))
            conn.commit()
        finally:
            conn.close()

        patches = self._patches()
        self._start_patches(patches)
        try:
            bad = verify_integrity()
        finally:
            self._stop_patches(patches)
        self.assertFalse(bad["verified"])

        conn = sqlite3.connect(self.path)
        try:
            conn.execute("DELETE FROM audit_log")
            conn.commit()
        finally:
            conn.close()

        _reimport_rows_to_db(self.path, _import_signed_audit_json(backup))

        patches = self._patches()
        self._start_patches(patches)
        try:
            recovered = verify_integrity()
        finally:
            self._stop_patches(patches)

        self.assertTrue(recovered["verified"])
        self.assertEqual(db_module.count_audit_logs(), 10)

    def test_test5_security_sql_and_tamper(self) -> None:
        """TEST-5: SQL injection, privilege escalation, tampering."""
        patches = self._patches()
        self._start_patches(patches)
        try:
            sql_attack = "'; DROP TABLE audit_log; --"
            audit_logger._log_event("UserLoggedIn", details=f"comment={sql_attack}, password=secret")

            conn = sqlite3.connect(self.path)
            try:
                cur = conn.cursor()
                cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='audit_log'")
                self.assertIsNotNone(cur.fetchone())
            finally:
                conn.close()

            rows = db_module.list_audit_logs(limit=1)
            self.assertEqual(len(rows), 1)
            entry_data = rows[0].get("entry_data") or b""
            if isinstance(entry_data, memoryview):
                entry_data = entry_data.tobytes()
            parsed = json.loads(entry_data.decode("utf-8"))
            self.assertEqual(parsed.get("details"), "[REDACTED]")

            conn = sqlite3.connect(self.path)
            try:
                conn.execute(
                    """INSERT INTO audit_log
                       (action, timestamp, entry_id, details, signature, sequence_number, previous_hash, entry_data)
                       VALUES ('PrivilegeEscalation', datetime('now'), NULL, 'bypass', 'fake', 99999, ?, ?)""",
                    ("0" * 64, b"{}"),
                )
                conn.commit()
            finally:
                conn.close()

            result = verify_integrity()
            self.assertFalse(result["verified"], "поддельная запись без валидной цепочки")

            conn = sqlite3.connect(self.path)
            try:
                conn.execute(
                    "UPDATE audit_log SET signature = 'hack' WHERE id = (SELECT MIN(id) FROM audit_log WHERE action = ?)",
                    ("UserLoggedIn",),
                )
                conn.commit()
            finally:
                conn.close()

            result2 = verify_integrity()
            self.assertFalse(result2["verified"])
        finally:
            self._stop_patches(patches)


if __name__ == "__main__":
    unittest.main()