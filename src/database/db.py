# vault db: записи хранилища (пароли и поля приходят уже зашифрованными, шифрование в core/vault)

import os
import sqlite3
import threading
import queue
import time

from . import models

# путь к vault.db задаётся снаружи из конфига; по умолчанию — рядом с проектом
_db_path = None
# один поток в момент работает с бд — иначе sqlite может ругаться при одновременной записи
_lock = threading.Lock()

# connection pooling (спринт3: для конкурентных операций GUI)
_POOL_SIZE = 5
_pool_queue = queue.Queue(maxsize=_POOL_SIZE)
_pool_total = 0
_pool_path = None
_pool_lock = threading.Lock()


def _normalize_db_path(path):
    if not path:
        return None
    # SQLite не создаёт директории сам; также приводим к абсолютному пути (важно для Windows).
    path = os.path.expandvars(os.path.expanduser(str(path).strip()))
    return os.path.abspath(path)


def _ensure_parent_dir(file_path):
    parent = os.path.dirname(file_path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def set_db_path(path):
    # задаётся путь к vault.db (при открытии или создании хранилища)
    global _db_path, _pool_total, _pool_path
    with _lock:
        _db_path = _normalize_db_path(path)
        # пул пересоздаётся при смене пути к БД (тесты используют разные временные файлы)
        _pool_total = 0
        _pool_path = None
        # очистка очереди доступных коннектов
        try:
            while True:
                c = _pool_queue.get_nowait()
                try:
                    c.close()
                except Exception:
                    pass
        except Exception:
            pass


def _path():
    # путь к файлу бд: либо заданный через set_db_path, либо дефолтный vault.db
    if _db_path:
        return _db_path
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, "vault.db")


def get_connection():
    # открывается соединение с sqlite; после использования его нужно закрыть
    path = _normalize_db_path(_path()) or _path()
    _ensure_parent_dir(path)
    return sqlite3.connect(path)


def _get_pooled_connection():
    # возвращает sqlite connection из пула или создаёт новый (до _POOL_SIZE)
    global _pool_total, _pool_path

    path = _normalize_db_path(_path()) or _path()
    _ensure_parent_dir(path)

    with _pool_lock:
        # если вдруг путь поменялся без вызова set_db_path
        if _pool_path != path:
            _pool_total = 0
            _pool_path = path
            try:
                while True:
                    _pool_queue.get_nowait()
            except Exception:
                pass

        try:
            return _pool_queue.get_nowait()
        except queue.Empty:
            if _pool_total < _POOL_SIZE:
                _pool_total += 1
                # check_same_thread=False: пул может обслуживать разные потоки GUI
                return sqlite3.connect(path, check_same_thread=False)

    # если пул пуст и лимит достигнут — ждём свободный connection
    return _pool_queue.get()


def _return_pooled_connection(conn):
    # возвращаем коннект в пул; если очередь переполнена — закрываем
    try:
        _pool_queue.put_nowait(conn)
    except Exception:
        try:
            conn.close()
        except Exception:
            pass


def _with_connection(operation):
    # одна точка входа: блокировка, взятие conn из пула, вызов operation(conn)
    with _lock:
        conn = _get_pooled_connection()
        try:
            result = operation(conn)
            return result
        except Exception:
            # откат транзакции при ошибке
            try:
                conn.rollback()
            except Exception:
                pass
            raise
        finally:
            _return_pooled_connection(conn)


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

            # (ARC-3, спринт2) переносим данные из старого key_store без потерь.
            # Ожидаемые поля (из sprint1/sprint2 описания): salt, hash, params.
            # Если какие-то поля отсутствуют в конкретной старой схеме — выбираем первый доступный непустой кандидат.
            cols = [r[1] for r in cur.execute("PRAGMA table_info(key_store)").fetchall()]
            col_set = set(cols)
            extra_cols = [c for c in ("salt", "hash", "params") if c in col_set]

            if extra_cols:
                sel = "SELECT id, key_type, %s FROM key_store" % ", ".join(extra_cols)
            else:
                sel = "SELECT id, key_type FROM key_store"

            rows = cur.execute(sel).fetchall()
            # индекс в row для выбранных extra_cols: row = (id, key_type, <extra...>)
            extra_index = {name: 2 + i for i, name in enumerate(extra_cols)}

            for row in rows:
                key_type = row[1]

                key_data = None
                if key_type == "auth_hash" and "hash" in col_set:
                    key_data = row[extra_index.get("hash")]
                elif key_type == "enc_salt" and "salt" in col_set:
                    key_data = row[extra_index.get("salt")]
                elif key_type == "params" and "params" in col_set:
                    key_data = row[extra_index.get("params")]

                if key_data is None and extra_cols:
                    # берём первое непустое поле из набора
                    for c in extra_cols:
                        v = row[extra_index[c]]
                        if v is not None:
                            key_data = v
                            break

                if key_data is not None:
                    cur.execute(
                        "INSERT INTO key_store_new (key_type, key_data, version, created_at) VALUES (?, ?, ?, ?)",
                        (key_type, key_data, 1, _timestamp()),
                    )

            cur.execute("DROP TABLE IF EXISTS key_store")
            cur.execute("ALTER TABLE key_store_new RENAME TO key_store")
            cur.execute("PRAGMA user_version = 2")
            conn.commit()

        # спринт3: меняется схема vault_entries (encrypted_password -> encrypted_data)
        if ver == 2:
            # ВАЖНО: мы не можем корректно перешифровать старые XOR-данные в AES-GCM,
            # потому что для этого нужен ключ (PBKDF2 доступен только после разблокировки).
            # Поэтому делаем безопасную перестройку схемы без переноса старых секретов.
            cur.execute("DROP TABLE IF EXISTS vault_entries")
            for sql in models.DDL:
                cur.execute(sql)
            cur.execute("PRAGMA user_version = %d" % models.SCHEMA_VERSION)
            conn.commit()

    _with_connection(apply)


def _timestamp():
    # текущее время в секундах (для created_at, updated_at, audit)
    return str(int(time.time()))


def insert_vault_entry(encrypted_data, tags=None):
    # в хранилище добавляется одна запись; encrypted_data уже зашифрован (nonce||ciphertext||tag)
    def apply(conn):
        cur = conn.cursor()
        now = _timestamp()
        cur.execute(
            """INSERT INTO vault_entries
               (encrypted_data, created_at, updated_at, tags)
               VALUES (?, ?, ?, ?)""",
            (encrypted_data, now, now, tags or ""),
        )
        conn.commit()
        return cur.lastrowid

    return _with_connection(apply)


def get_all_vault_entries():
    # возвращаются все записи хранилища (id, encrypted_data, created_at, updated_at, tags)
    def apply(conn):
        cur = conn.cursor()
        cur.execute(
            "SELECT id, encrypted_data, created_at, updated_at, tags FROM vault_entries ORDER BY id"
        )
        return cur.fetchall()

    return _with_connection(apply)


def get_vault_entry(entry_id):
    # возвращается одна запись по id или None
    def apply(conn):
        cur = conn.cursor()
        cur.execute(
            "SELECT id, encrypted_data, created_at, updated_at, tags FROM vault_entries WHERE id=?",
            (entry_id,),
        )
        return cur.fetchone()

    return _with_connection(apply)


def update_vault_entry(entry_id, encrypted_data, tags=None):
    # запись с указанным id обновляется; encrypted_data передаётся уже зашифрованным
    def apply(conn):
        cur = conn.cursor()
        now = _timestamp()
        cur.execute(
            """UPDATE vault_entries SET encrypted_data=?, updated_at=?, tags=? WHERE id=?""",
            (encrypted_data, now, tags or "", entry_id),
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