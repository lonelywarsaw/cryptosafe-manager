import unittest
import tempfile
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database.db import Database
from src.database.models import schema_version
from src.database import vault
from src.core.crypto.placeholder import AES256Placeholder
from src.core.key_manager import KeyManager

class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.db = Database(self.db_path)
        self.db.init_schema()
        self.crypto = AES256Placeholder()
        self.key_manager = KeyManager()
        self.sample_key = self.key_manager.derive_key("test_password", self.key_manager.generate_salt())

    def tearDown(self):
        self.db.close()

    def test_creates_schema(self):
        self.assertTrue(self.db_path.exists())
        self.assertEqual(self.db.get_schema_version(), schema_version)

    def test_tables_exist(self):
        for table in ("vault_entries", "audit_log", "settings", "key_store"):
            row = self.db.fetchone("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
            self.assertIsNotNone(row)

    def test_insert_and_fetch_entries(self):
        vault.insert_entry(
            self.db, self.crypto, self.sample_key,
            title="Test",
            username="user",
            password="secret",
            url="https://example.com",
        )
        rows = vault.get_entries(self.db)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["title"], "Test")
        self.assertEqual(rows[0]["username"], "user")
        self.assertNotIn("encrypted_password", rows[0])

    def test_thread_safe_cursor(self):
        with self.db.cursor() as cur:
            cur.execute("SELECT 1")
            self.assertEqual(cur.fetchone()[0], 1)

if __name__ == "__main__":
    unittest.main()
