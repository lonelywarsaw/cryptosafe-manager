# vault db: записи хранилища (пароли приходят уже зашифрованными, шифрование в core/crypto)

import os
import sqlite3
import threading
import time

from . import models

# путь к vault.db задаётся снаружи из конфига; по умолчанию — рядом с проектом
_db_path = None
# один поток в момент работает с бд — иначе sqlite может ругаться при одновременной записи
_lock = threading.Lock()


def set_db_path(path):
    # задаётся путь к vault.db (при открытии или создании хранилища)
    global _db_path
    with _lock:
        _db_path = path


def _path():
    # путь к файлу бд: либо заданный через set_db_path, либо дефолтный vault.db
    if _db_path:
        return _db_path
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, "vault.db")


def get_connection():
    # открывается соединение с sqlite; после использования его нужно закрыть
    return sqlite3.connect(_path())


def _with_connection(operation):
    # одна точка входа: блокировка, открытие соединения, вызов operation(conn), закрытие соединения
    with _lock:
        conn = get_connection()
        try:
            return operation(conn)
        finally:
            conn.close()


def init_db():
    # таблицы создаются, если их ещё нет; user_version хранит версию схемы для миграций (спринт 2: миграция key_store)
    def apply(conn):
        cur = conn.cursor()
        cur.execute("PRAGMA user_version")
        ver = cur.fetchone()[0]
        if ver == 0:
            for sql in models.DDL:
                cur.execute(sql)
            cur.execute("PRAGMA user_version = %d" % models.SCHEMA_VERSION)
            conn.commit()
            return
        # с версии 1 переходим на key_store с key_data, version, created_at (спринт 2)
        if ver == 1:
            cur.execute(
                "CREATE TABLE IF NOT EXISTS key_store_new (id INTEGER PRIMARY KEY AUTOINCREMENT, key_type TEXT, key_data BLOB, version INTEGER DEFAULT 1, created_at TEXT)"
            )
            cur.execute("DROP TABLE IF EXISTS key_store")
            cur.execute("ALTER TABLE key_store_new RENAME TO key_store")
            cur.execute("PRAGMA user_version = 2")
            conn.commit()

    _with_connection(apply)


def _timestamp():
    # текущее время в секундах (для created_at, updated_at, audit)
    return str(int(time.time()))


def insert_vault_entry(title, username, encrypted_password, url=None, notes=None, tags=None):
    # в хранилище добавляется одна запись; encrypted_password уже зашифрован
    def apply(conn):
        cur = conn.cursor()
        now = _timestamp()
        cur.execute(
            """INSERT INTO vault_entries
               (title, username, encrypted_password, url, notes, created_at, updated_at, tags)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (title, username, encrypted_password, url or "", notes or "", now, now, tags or ""),
        )
        conn.commit()
        return cur.lastrowid

    return _with_connection(apply)


def get_all_vault_entries():
    # возвращаются все записи хранилища (id, title, username, encrypted_password, url, notes)
    def apply(conn):
        cur = conn.cursor()
        cur.execute(
            "SELECT id, title, username, encrypted_password, url, notes FROM vault_entries ORDER BY id"
        )
        return cur.fetchall()

    return _with_connection(apply)


def get_vault_entry(entry_id):
    # возвращается одна запись по id или None
    def apply(conn):
        cur = conn.cursor()
        cur.execute(
            "SELECT id, title, username, encrypted_password, url, notes FROM vault_entries WHERE id=?",
            (entry_id,),
        )
        return cur.fetchone()

    return _with_connection(apply)


def update_vault_entry(entry_id, title, username, encrypted_password, url=None, notes=None, tags=None):
    # запись с указанным id обновляется; пароль передаётся уже зашифрованным
    def apply(conn):
        cur = conn.cursor()
        now = _timestamp()
        cur.execute(
            """UPDATE vault_entries SET title=?, username=?, encrypted_password=?, url=?, notes=?, updated_at=?, tags=? WHERE id=?""",
            (title, username, encrypted_password, url or "", notes or "", now, tags or "", entry_id),
        )
        conn.commit()

    _with_connection(apply)


def delete_vault_entry(entry_id):
    # запись с указанным id удаляется из хранилища
    def apply(conn):
        cur = conn.cursor()
        cur.execute("DELETE FROM vault_entries WHERE id=?", (entry_id,))
        conn.commit()

    _with_connection(apply)


def insert_audit_log(action, entry_id=None, details=None):
    # в журнал аудита добавляется строка (action, timestamp, details); signature пока пустой
    def apply(conn):
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO audit_log (action, timestamp, entry_id, details, signature) VALUES (?, ?, ?, ?, ?)",
            (action, _timestamp(), entry_id, details or "", ""),
        )
        conn.commit()

    _with_connection(apply)


def backup():
    # заглушка: резервная копия бд (спринте 8)
    pass


def restore(path):
    # заглушка: восстановление из резервной копии (спринт 8)
    pass


def get_key_store(key_type):
    # чтение из key_store по key_type (auth_hash или enc_salt), возвращаются байты key_data или None (спринт 2)
    def apply(conn):
        cur = conn.cursor()
        cur.execute("SELECT key_data FROM key_store WHERE key_type = ? ORDER BY id DESC LIMIT 1", (key_type,))
        row = cur.fetchone()
        return row[0] if row and row[0] is not None else None

    return _with_connection(apply)


def set_key_store(key_type, key_data, version=1):
    # запись в key_store (key_type, key_data blob, version); для смены пароля перезаписываем по key_type (спринт 2)
    def apply(conn):
        cur = conn.cursor()
        cur.execute("DELETE FROM key_store WHERE key_type = ?", (key_type,))
        now = _timestamp()
        cur.execute(
            "INSERT INTO key_store (key_type, key_data, version, created_at) VALUES (?, ?, ?, ?)",
            (key_type, key_data, version, now),
        )
        conn.commit()

    _with_connection(apply)
