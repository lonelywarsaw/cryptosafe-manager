# Спринт 8 — backup/restore (TRD integration)

import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import database.db as db_module
from core import config
from core.backup_service import create_backup, restore_backup, validate_backup
def _init_vault(path: str) -> None:
    db_module.set_db_path(path)
    db_module.init_db()
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "INSERT INTO vault_entries (encrypted_data, created_at, updated_at, tags) VALUES (?,?,?,?)",
            (b"enc", "2020-01-01", "2020-01-01", ""),
        )
        conn.commit()
    finally:
        conn.close()


class TestSprint8Backup(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self._vault = os.path.join(self._tmpdir, "vault.db")
        _init_vault(self._vault)
        db_module.set_db_path(self._vault)
        self._cfg_patch = patch.object(config, "get", side_effect=self._cfg_get)
        self._cfg_patch.start()

    def tearDown(self):
        self._cfg_patch.stop()
        db_module.set_db_path(None)

    def _cfg_get(self, key, default=None):
        if key == config.DB_PATH:
            return self._vault
        return default

    def test_backup_while_vault_connection_open(self):
        """Backup must work while GUI holds pooled SQLite connections (Windows)."""
        conn = db_module.get_connection()
        try:
            dest = os.path.join(self._tmpdir, "open-pool.csafe.zip")
            manifest = create_backup(dest, include_config=False)
            self.assertEqual(manifest.get("entry_count"), 1)
            self.assertTrue(os.path.isfile(manifest.get("archive_path", dest)))
        finally:
            conn.close()

    def test_backup_roundtrip(self):
        dest = os.path.join(self._tmpdir, "backup.csafe.zip")
        manifest = create_backup(dest, include_config=False)
        self.assertEqual(manifest.get("entry_count"), 1)
        validate_backup(dest)

        conn = sqlite3.connect(self._vault)
        conn.execute("DELETE FROM vault_entries")
        conn.commit()
        conn.close()

        restore_backup(dest)
        conn = sqlite3.connect(self._vault)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM vault_entries")
        count = cur.fetchone()[0]
        conn.close()
        self.assertEqual(count, 1)


if __name__ == "__main__":
    unittest.main()
