# Тут только работа с БД. Шифруют в другом месте, сюда приходит уже зашифрованное.

import os
import sqlite3
import time

from . import models

_db_path = None

def set_db_path(path):
    global _db_path
    _db_path = path

def _path():
    if _db_path:
        return _db_path
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, "vault.db")

def get_connection():
    return sqlite3.connect(_path())

def init_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("PRAGMA user_version")
    version = cur.fetchone()[0]
    if version == 0:
        for sql in models.DDL:
            cur.execute(sql)
        cur.execute("PRAGMA user_version = %d" % models.SCHEMA_VERSION)
        conn.commit()
    conn.close()

def insert_vault_entry(title, username, encrypted_password, url=None, notes=None, tags=None):
    conn = get_connection()
    cur = conn.cursor()
    now = str(int(time.time()))
    cur.execute(
        """INSERT INTO vault_entries
           (title, username, encrypted_password, url, notes, created_at, updated_at, tags)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (title, username, encrypted_password, url or "", notes or "", now, now, tags or ""),
    )
    conn.commit()
    rowid = cur.lastrowid
    conn.close()
    return rowid

def get_all_vault_entries():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, title, username, encrypted_password, url, notes FROM vault_entries ORDER BY id"
    )
    rows = cur.fetchall()
    conn.close()
    return rows

def get_vault_entry(entry_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, title, username, encrypted_password, url, notes FROM vault_entries WHERE id=?",
        (entry_id,),
    )
    row = cur.fetchone()
    conn.close()
    return row

def update_vault_entry(entry_id, title, username, encrypted_password, url=None, notes=None, tags=None):
    conn = get_connection()
    cur = conn.cursor()
    now = str(int(time.time()))
    cur.execute(
        """UPDATE vault_entries SET title=?, username=?, encrypted_password=?, url=?, notes=?, updated_at=?, tags=? WHERE id=?""",
        (title, username, encrypted_password, url or "", notes or "", now, tags or "", entry_id),
    )
    conn.commit()
    conn.close()

def delete_vault_entry(entry_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM vault_entries WHERE id=?", (entry_id,))
    conn.commit()
    conn.close()

def insert_audit_log(action, entry_id=None, details=None):
    conn = get_connection()
    cur = conn.cursor()
    now = str(int(time.time()))
    cur.execute(
        "INSERT INTO audit_log (action, timestamp, entry_id, details, signature) VALUES (?, ?, ?, ?, ?)",
        (action, now, entry_id, details or "", ""),
    )
    conn.commit()
    conn.close()

def backup():
    pass

def restore(path):
    pass
