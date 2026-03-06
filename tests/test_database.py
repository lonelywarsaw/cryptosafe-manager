# Тесты БД — подключение, создание таблиц, CRUD, audit_log.
import os
import unittest

from tests.fixtures import TestDatabaseFixture
import database.db as db
import database.models as models


class TestDatabaseConnectivityAndSchema(TestDatabaseFixture):
    # Подключаемся, создаём таблицы, проверяем что всё на месте.

    def test_connection_works(self):
        conn = db.get_connection()
        self.assertIsNotNone(conn)
        cur = conn.cursor()
        cur.execute("SELECT 1")
        self.assertEqual(cur.fetchone()[0], 1)
        conn.close()

    def test_schema_tables_exist(self):
        conn = db.get_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        names = {row[0] for row in cur.fetchall()}
        conn.close()
        self.assertIn("vault_entries", names)
        self.assertIn("audit_log", names)
        self.assertIn("settings", names)
        self.assertIn("key_store", names)

    def test_user_version_set(self):
        conn = db.get_connection()
        cur = conn.cursor()
        cur.execute("PRAGMA user_version")
        version = cur.fetchone()[0]
        conn.close()
        self.assertEqual(version, models.SCHEMA_VERSION)

    def test_insert_and_get_vault_entry(self):
        row_id = db.insert_vault_entry(
            "Test", "user", "encrypted_pwd", url="https://x.com", notes="n"
        )
        self.assertIsNotNone(row_id)
        entry = db.get_vault_entry(row_id)
        self.assertIsNotNone(entry)
        self.assertEqual(entry[1], "Test")
        self.assertEqual(entry[2], "user")
        self.assertEqual(entry[4], "https://x.com")
        self.assertEqual(entry[5], "n")

    def test_get_all_vault_entries(self):
        db.insert_vault_entry("A", "u1", "p1")
        db.insert_vault_entry("B", "u2", "p2")
        rows = db.get_all_vault_entries()
        self.assertEqual(len(rows), 2)

    def test_update_vault_entry(self):
        row_id = db.insert_vault_entry("Old", "u", "p")
        db.update_vault_entry(row_id, "New", "u2", "p", url="", notes="")
        entry = db.get_vault_entry(row_id)
        self.assertEqual(entry[1], "New")
        self.assertEqual(entry[2], "u2")

    def test_delete_vault_entry(self):
        row_id = db.insert_vault_entry("X", "u", "p")
        db.delete_vault_entry(row_id)
        self.assertIsNone(db.get_vault_entry(row_id))

    def test_insert_audit_log(self):
        db.insert_audit_log("TestAction", entry_id=1, details="d")
        conn = db.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT action, entry_id, details FROM audit_log")
        row = cur.fetchone()
        conn.close()
        self.assertEqual(row[0], "TestAction")
        self.assertEqual(row[1], 1)
        self.assertEqual(row[2], "d")
