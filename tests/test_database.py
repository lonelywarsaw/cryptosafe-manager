# тесты БД

import os
import tempfile
import unittest
import database.db as db
import database.models as models


class TestDatabase(unittest.TestCase):
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

    def test_connect(self):
        # соединение с sqlite открывается и простой запрос выполняется (проверка что бд доступна)
        conn = db.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        self.assertEqual(cur.fetchone()[0], 1)
        conn.close()

    def test_tables(self):
        # после init_db в бд есть все нужные таблицы: хранилище, аудит, настройки, ключи
        conn = db.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        names = {r[0] for r in cur.fetchall()}
        conn.close()
        for t in ("vault_entries", "audit_log", "settings", "key_store"):
            self.assertIn(t, names)

    def test_version(self):
        # user_version совпадает с SCHEMA_VERSION из models (для будущих миграций)
        conn = db.get_connection()
        cur = conn.cursor()
        cur.execute("PRAGMA user_version")
        self.assertEqual(cur.fetchone()[0], models.SCHEMA_VERSION)
        conn.close()

    def test_insert_get(self):
        # вставка записи возвращает id; по этому id запись читается с теми же зашифрованными байтами
        row_id = db.insert_vault_entry(b"encrypted_data_1", tags="tag1")
        self.assertIsNotNone(row_id)
        entry = db.get_vault_entry(row_id)
        self.assertEqual(entry[1], b"encrypted_data_1")
        self.assertEqual(entry[4], "tag1")

    def test_get_all(self):
        # get_all_vault_entries возвращает все записи; после двух insert — ровно две строки
        db.insert_vault_entry(b"p1", tags="")
        db.insert_vault_entry(b"p2", tags="")
        rows = db.get_all_vault_entries()
        self.assertEqual(len(rows), 2)

    def test_update(self):
        # update меняет encrypted_data и tags записи по id
        row_id = db.insert_vault_entry(b"old", tags="t1")
        db.update_vault_entry(row_id, encrypted_data=b"new", tags="t2")
        entry = db.get_vault_entry(row_id)
        self.assertEqual(entry[1], b"new")
        self.assertEqual(entry[4], "t2")

    def test_delete(self):
        # после delete запись по id не находится (get_vault_entry возвращает None)
        row_id = db.insert_vault_entry(b"x", tags="")
        db.delete_vault_entry(row_id)
        self.assertIsNone(db.get_vault_entry(row_id))

    def test_audit_log(self):
        # insert_audit_log пишет в таблицу audit_log; действие и details читаются обратно
        db.insert_audit_log("Act", entry_id=1, details="d")
        conn = db.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT action, details FROM audit_log")
        row = cur.fetchone()
        conn.close()
        self.assertEqual(row[0], "Act")
        self.assertEqual(row[1], "d")
