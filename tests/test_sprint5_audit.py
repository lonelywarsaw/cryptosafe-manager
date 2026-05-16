import os
import tempfile
import unittest

import database.db as db
from core.audit.audit_logger import _log_event
from core.audit.integrity import verify_integrity
from core.key_manager import set_encryption_key


class TestSprint5Audit(unittest.TestCase):
    def setUp(self):
        fd, self._db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        db.set_db_path(self._db_path)
        db.init_db()
        set_encryption_key(b"x" * 32)

    def tearDown(self):
        db.set_db_path(None)
        if os.path.exists(self._db_path):
            try:
                os.unlink(self._db_path)
            except OSError:
                pass

    def test_signed_audit_chain(self):
        _log_event("EntryCreated", entry_id=1, details="entry_id=1")
        _log_event("ClipboardCopied", entry_id=1, details="kind=password")
        result = verify_integrity()
        self.assertTrue(result["verified"])
        self.assertGreaterEqual(result["valid_entries"], 2)

    def test_list_and_prune(self):
        for i in range(5):
            _log_event("EntryCreated", entry_id=i, details=f"entry_id={i}")
        rows = db.list_audit_logs(limit=10)
        self.assertGreaterEqual(len(rows), 5)
        removed = db.prune_audit_logs(3)
        self.assertGreaterEqual(removed, 0)
        self.assertLessEqual(db.count_audit_logs(), 5)
