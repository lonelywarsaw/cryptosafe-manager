import os
import tempfile
import unittest

import database.db as db
from core.vault.entry_manager import EntryManager

try:
    import cryptography  # noqa: F401
    _HAS_CRYPTO = True
except Exception:
    _HAS_CRYPTO = False


class _FakeKeyManager:
    def __init__(self, key: bytes):
        self._key = key

    def get_encryption_key(self):
        return self._key


class _FakeEvents:
    EntryAdded = "EntryAdded"
    EntryCreated = "EntryCreated"
    EntryUpdated = "EntryUpdated"
    EntryDeleted = "EntryDeleted"

    def __init__(self):
        self.published = []

    def publish(self, event_type, sync=True, **kwargs):
        self.published.append((event_type, kwargs))


@unittest.skipUnless(_HAS_CRYPTO, "Пакет 'cryptography' не установлен — AES-GCM тесты пропускаются")
class TestSprint3Vault(unittest.TestCase):
    def setUp(self):
        fd, self._db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        db.set_db_path(self._db_path)
        db.init_db()

    def tearDown(self):
        db.set_db_path(None)
        if os.path.exists(self._db_path):
            try:
                os.unlink(self._db_path)
            except OSError:
                pass

    def test_crud_integration(self):
        # (TEST-2) CRUD через EntryManager: create/get/update/delete
        key = b"x" * 32
        km = _FakeKeyManager(key)
        ev = _FakeEvents()
        manager = EntryManager(db, km, ev)

        pwd = "Password_123!"
        entry = manager.create_entry(
            {
                "title": "T1",
                "username": "user@example.com",
                "password": pwd,
                "url": "https://example.com/path",
                "notes": "n1",
                "category": "Work",
            }
        )
        self.assertIsNotNone(entry.get("id"))

        all_entries = manager.get_all_entries()
        self.assertEqual(len(all_entries), 1)
        self.assertIn("username_masked", all_entries[0])
        self.assertIn("url_domain", all_entries[0])

        entry_id = entry["id"]
        got = manager.get_entry(entry_id)
        self.assertEqual(got["password"], pwd)
        self.assertEqual(got["title"], "T1")

        # update
        manager.update_entry(
            entry_id,
            {
                "title": "T1-upd",
                "username": "user@example.com",
                "password": "NewPassword_456!",
                "url": "https://example.com/other",
                "notes": "n2",
                "category": "Work",
            },
        )
        got2 = manager.get_entry(entry_id)
        self.assertEqual(got2["title"], "T1-upd")
        self.assertEqual(got2["password"], "NewPassword_456!")

        # delete
        manager.delete_entry(entry_id, soft_delete=True)
        self.assertIsNone(db.get_vault_entry(entry_id))

        # events publish (CRUD-3)
        event_types = [e[0] for e in ev.published]
        self.assertIn(_FakeEvents.EntryAdded, event_types)
        self.assertIn(_FakeEvents.EntryCreated, event_types)
        self.assertIn(_FakeEvents.EntryUpdated, event_types)
        self.assertIn(_FakeEvents.EntryDeleted, event_types)

