from __future__ import annotations

import os
import sqlite3
import statistics
import tempfile
import time
import tracemalloc
import unittest
from unittest.mock import patch

import database.db as db_module
from core import events
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


class TestSprint5AuditPerformance(unittest.TestCase):
    """PERF-1..5 (Спринт 5)."""

    _rows_10k: list[dict] | None = None

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

    def _db_patches(self):
        return [
            patch("core.audit.audit_logger.derive_audit_signing_key", return_value=self.signing_key),
            patch("core.audit.log_signer.derive_audit_signing_key", return_value=self.signing_key),
            patch("core.key_manager.get_encryption_key", return_value=ENC_KEY),
        ]

    def _start_patches(self, patches):
        for p in patches:
            p.start()

    def _stop_patches(self, patches):
        for p in reversed(patches):
            p.stop()

    def _write_logs(self, count: int) -> None:
        patches = self._db_patches()
        self._start_patches(patches)
        try:
            for i in range(count):
                audit_logger._log_event("ClipboardCopied", entry_id=i, details=f"source=perf, n={i}")
        finally:
            self._stop_patches(patches)

    def _load_10k_rows(self) -> list[dict]:
        if TestSprint5AuditPerformance._rows_10k is None:
            self._write_logs(10000)
            rows = db_module.list_audit_logs(limit=10000)
            self.assertEqual(len(rows), 10000)
            TestSprint5AuditPerformance._rows_10k = rows
        return TestSprint5AuditPerformance._rows_10k

    def test_perf1_log_under_10ms(self) -> None:
        """PERF-1: медиана одной записи < 10 ms (после прогрева)."""
        patches = self._db_patches()
        self._start_patches(patches)
        try:
            for _ in range(20):
                audit_logger._log_event("ClipboardCopied", details="warmup")
            samples = []
            for _ in range(7):
                t0 = time.perf_counter()
                audit_logger._log_event("ClipboardCopied", details="source=perf")
                samples.append((time.perf_counter() - t0) * 1000.0)
            median_ms = statistics.median(samples)
        finally:
            self._stop_patches(patches)
        self.assertLess(median_ms, 10.0, f"median={median_ms:.2f}ms samples={samples}")

    def test_perf2_verify_1000_under_1s(self) -> None:
        """PERF-2: verify 1000 с проверкой подписей < 1 с."""
        patches = self._db_patches()
        self._start_patches(patches)
        try:
            for i in range(1000):
                audit_logger._log_event("ClipboardCopied", entry_id=i, details=f"n={i}")
            rows = db_module.list_audit_logs(limit=1000)
            rows_asc = list(reversed(rows))
            signer = AuditLogSigner(self.signing_key)

            t0 = time.perf_counter()
            result = verify_audit_chain(rows_asc, signer)
            dt = time.perf_counter() - t0
        finally:
            self._stop_patches(patches)

        self.assertTrue(result["verified"], result.get("breaks"))
        self.assertFalse(result.get("skipped"))
        self.assertLess(dt, 1.0)

    def test_perf3_filter_10000_under_500ms(self) -> None:
        """PERF-3: SQL filter 10k по event_type < 500 ms."""
        self._load_10k_rows()
        t0 = time.perf_counter()
        filtered = db_module.list_audit_logs(limit=10000, event_type="ClipboardCopied")
        dt_ms = (time.perf_counter() - t0) * 1000.0
        self.assertEqual(len(filtered), 10000)
        self.assertLess(dt_ms, 500.0)

    def test_perf4_viewer_memory_under_50mb(self) -> None:
        """PERF-4: загрузка 10k в память viewer < 50 MB."""
        rows = self._load_10k_rows()
        tracemalloc.start()
        items = [dict(r) for r in rows]
        filtered = [i for i in items if i.get("action") == "ClipboardCopied"]
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        self.assertEqual(len(filtered), 10000)
        self.assertLess(peak, 50 * 1024 * 1024)

    def test_perf5_async_logging(self) -> None:
        """PERF-5: publish(sync=False) + фоновый audit не блокирует caller."""
        patches = self._db_patches()
        self._start_patches(patches)
        try:
            audit_logger.register()
            before = db_module.count_audit_logs()

            t0 = time.perf_counter()
            events.publish(events.ClipboardCopied, sync=False, kind="perf", entry_id=99)
            publish_ms = (time.perf_counter() - t0) * 1000.0

            deadline = time.time() + 3.0
            after = before
            while time.time() < deadline:
                after = db_module.count_audit_logs()
                if after > before:
                    break
                time.sleep(0.01)
        finally:
            self._stop_patches(patches)

        self.assertLess(publish_ms, 10.0, "очередь событий должна принимать publish быстро")
        self.assertGreater(after, before, "запись должна появиться асинхронно")


if __name__ == "__main__":
    unittest.main()