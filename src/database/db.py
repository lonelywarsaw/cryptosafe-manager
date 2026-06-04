"""Vault database API: encrypted entries, audit log, keys. / API БД хранилища: записи, аудит, ключи."""

import os
import sqlite3
import threading
import queue
import time
from datetime import datetime
from typing import Optional

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
    """Set path to vault.db. / Задаёт путь к vault.db."""
    global _db_path, _pool_total, _pool_path
    with _lock:
        _db_path = _normalize_db_path(path)
        # пул пересоздаётся при смене пути к БД (тесты используют разные временные файлы)
        _pool_total = 0
        _pool_path = None
        try:
            from core.audit.audit_logger import clear_chain_cache

            clear_chain_cache()
        except Exception:
            pass
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


def get_vault_path() -> str:
    """Absolute path to the active vault.db file. / Абсолютный путь к vault.db."""
    return _normalize_db_path(_path()) or _path()


def close_all_connections() -> None:
    """Close pooled SQLite connections (e.g. before restore). / Закрывает пул соединений."""
    global _pool_total, _pool_path
    with _pool_lock:
        while True:
            try:
                conn = _pool_queue.get_nowait()
                try:
                    conn.close()
                except Exception:
                    pass
            except queue.Empty:
                break
        _pool_total = 0
        _pool_path = None


def backup_vault_to(dest_path: str) -> None:
    """Copy vault.db via SQLite backup API (safe while the app is running). / Копия vault через backup API."""
    _ensure_parent_dir(dest_path)

    def apply(src_conn):
        dest_conn = sqlite3.connect(dest_path)
        try:
            src_conn.backup(dest_conn)
            dest_conn.commit()
        finally:
            dest_conn.close()

    _with_connection(apply)


def get_connection():
    """Open a SQLite connection (caller must close). / Открывает соединение с SQLite."""
    path = get_vault_path()
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


def _ensure_audit_log_columns(cur):
    # спринт 5: дополняем audit_log, если база создана старой миграцией без новых полей
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='audit_log'")
    if not cur.fetchone():
        return
    cols = {r[1] for r in cur.execute("PRAGMA table_info(audit_log)").fetchall()}
    for name, decl in (
        ("sequence_number", "INTEGER"),
        ("previous_hash", "TEXT"),
        ("entry_data", "BLOB"),
        ("public_key", "TEXT"),
    ):
        if name not in cols:
            cur.execute("ALTER TABLE audit_log ADD COLUMN %s %s" % (name, decl))
    cur.execute("UPDATE audit_log SET sequence_number = id WHERE sequence_number IS NULL")


def _ensure_sprint6_tables(cur):
    cur.execute(
        """CREATE TABLE IF NOT EXISTS shared_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shared_id TEXT UNIQUE,
            original_entry_id INTEGER,
            encryption_method TEXT,
            recipient_info TEXT,
            permissions TEXT,
            shared_at TEXT,
            expires_at TEXT
        )"""
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_shared_entries_shared_at ON shared_entries(shared_at)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_shared_entries_expires_at ON shared_entries(expires_at)")
    cur.execute(
        """CREATE TABLE IF NOT EXISTS import_export_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            operation_type TEXT,
            format TEXT,
            encryption_used TEXT,
            entry_count INTEGER,
            file_size INTEGER,
            checksum TEXT,
            verification_status TEXT,
            created_at TEXT
        )"""
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ie_history_created_at ON import_export_history(created_at)")


def init_db():
    """Create tables and run schema migrations. / Создаёт таблицы и выполняет миграции схемы."""
    def apply(conn):
        cur = conn.cursor()
        cur.execute("PRAGMA user_version")
        ver = cur.fetchone()[0]
        if ver == 0:
            for sql in models.DDL:
                cur.execute(sql)
            cur.execute("PRAGMA user_version = %d" % models.SCHEMA_VERSION)
        # с версии 1 переходим на key_store с key_data, version, created_at (спринт 2)
        elif ver == 1:
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

        # спринт3: меняется схема vault_entries (encrypted_password -> encrypted_data)
        elif ver == 2:
            # ВАЖНО: мы не можем корректно перешифровать старые XOR-данные в AES-GCM,
            # потому что для этого нужен ключ (PBKDF2 доступен только после разблокировки).
            # Поэтому делаем безопасную перестройку схемы без переноса старых секретов.
            cur.execute("DROP TABLE IF EXISTS vault_entries")
            for sql in models.DDL:
                cur.execute(sql)
            cur.execute("PRAGMA user_version = %d" % models.SCHEMA_VERSION)

        elif ver == 3:
            _ensure_audit_log_columns(cur)
            cur.execute("PRAGMA user_version = 4")

        elif ver == 4:
            _ensure_sprint6_tables(cur)
            cur.execute("PRAGMA user_version = 5")

        _ensure_audit_log_columns(cur)
        _ensure_sprint6_tables(cur)
        conn.commit()

    _with_connection(apply)


def _timestamp():
    # единый формат даты в БД: YYYY-MM-DD (спринт4/полировка UI)
    # Хранение времени отдельно не требуется для текущих задач проекта.
    return datetime.now().strftime("%Y-%m-%d")


def insert_vault_entry(encrypted_data, tags=None):
    """Insert one encrypted vault row; returns new id. / Добавляет зашифрованную запись."""
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
    """Return all vault rows ordered by id. / Возвращает все записи хранилища."""
    def apply(conn):
        cur = conn.cursor()
        cur.execute(
            "SELECT id, encrypted_data, created_at, updated_at, tags FROM vault_entries ORDER BY id"
        )
        return cur.fetchall()

    return _with_connection(apply)


def get_vault_entry(entry_id):
    """Return one vault row by id or None. / Возвращает запись по id или None."""
    def apply(conn):
        cur = conn.cursor()
        cur.execute(
            "SELECT id, encrypted_data, created_at, updated_at, tags FROM vault_entries WHERE id=?",
            (entry_id,),
        )
        return cur.fetchone()

    return _with_connection(apply)


def update_vault_entry(entry_id, encrypted_data, tags=None):
    """Update encrypted vault row by id. / Обновляет зашифрованную запись по id."""
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
    """Delete vault row by id. / Удаляет запись хранилища по id."""
    def apply(conn):
        cur = conn.cursor()
        cur.execute("DELETE FROM vault_entries WHERE id=?", (entry_id,))
        conn.commit()

    _with_connection(apply)


def get_audit_tail():
    """Return last audit_log row for signature chain. / Последняя строка журнала аудита."""
    def apply(conn):
        cur = conn.cursor()
        cur.execute(
            """SELECT id, signature, details, COALESCE(sequence_number, id), previous_hash, entry_data
               FROM audit_log ORDER BY id DESC LIMIT 1"""
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "signature": row[1],
            "details": row[2],
            "sequence_number": row[3],
            "previous_hash": row[4],
            "entry_data": row[5],
        }

    return _with_connection(apply)


def list_audit_logs(limit: int = 500, offset: int = 0, event_type: Optional[str] = None):
    """List audit log entries (newest first). / Список записей журнала аудита."""
    def apply(conn):
        cur = conn.cursor()
        if event_type:
            cur.execute(
                """SELECT id, action, timestamp, entry_id, details, signature,
                          sequence_number, previous_hash, entry_data
                   FROM audit_log WHERE action = ?
                   ORDER BY COALESCE(sequence_number, id) DESC LIMIT ? OFFSET ?""",
                (event_type, limit, offset),
            )
        else:
            cur.execute(
                """SELECT id, action, timestamp, entry_id, details, signature,
                          sequence_number, previous_hash, entry_data
                   FROM audit_log ORDER BY COALESCE(sequence_number, id) DESC LIMIT ? OFFSET ?""",
                (limit, offset),
            )
        rows = cur.fetchall()
        out = []
        for r in rows:
            out.append(
                {
                    "id": r[0],
                    "action": r[1],
                    "timestamp": r[2],
                    "entry_id": r[3],
                    "details": r[4],
                    "signature": r[5],
                    "sequence_number": r[6],
                    "previous_hash": r[7],
                    "entry_data": r[8],
                }
            )
        return out

    return _with_connection(apply)


def list_audit_logs_chronological(limit: int = 500, offset: int = 0, event_type: Optional[str] = None):
    """List audit log entries oldest first (for chain verification). / Журнал аудита от старых к новым."""
    def apply(conn):
        cur = conn.cursor()
        if event_type:
            cur.execute(
                """SELECT id, action, timestamp, entry_id, details, signature,
                          sequence_number, previous_hash, entry_data
                   FROM audit_log WHERE action = ?
                   ORDER BY COALESCE(sequence_number, id) ASC LIMIT ? OFFSET ?""",
                (event_type, limit, offset),
            )
        else:
            cur.execute(
                """SELECT id, action, timestamp, entry_id, details, signature,
                          sequence_number, previous_hash, entry_data
                   FROM audit_log ORDER BY COALESCE(sequence_number, id) ASC LIMIT ? OFFSET ?""",
                (limit, offset),
            )
        rows = cur.fetchall()
        out = []
        for r in rows:
            out.append(
                {
                    "id": r[0],
                    "action": r[1],
                    "timestamp": r[2],
                    "entry_id": r[3],
                    "details": r[4],
                    "signature": r[5],
                    "sequence_number": r[6],
                    "previous_hash": r[7],
                    "entry_data": r[8],
                }
            )
        return out

    return _with_connection(apply)


def count_audit_logs():
    """Return total number of audit log rows. / Число записей в журнале аудита."""
    def apply(conn):
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM audit_log")
        return int(cur.fetchone()[0])

    return _with_connection(apply)


def prune_audit_logs(max_entries: int):
    """Trim audit log to max_entries; returns rows removed. / Обрезает журнал до лимита."""
    def apply(conn):
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM audit_log")
        total = int(cur.fetchone()[0])
        if total <= max_entries:
            return 0
        to_remove = total - max_entries
        cur.execute(
            """DELETE FROM audit_log WHERE id IN (
                SELECT id FROM audit_log ORDER BY id ASC LIMIT ?
            )""",
            (to_remove,),
        )
        conn.commit()
        return to_remove

    return _with_connection(apply)


def insert_audit_log(
    action,
    entry_id=None,
    details=None,
    previous_hash=None,
    entry_data=None,
    signature=None,
    public_key=None,
    sequence_number=None,
    *,
    prune_max_entries: Optional[int] = None,
):
    """Append signed row to audit log. / Добавляет строку в журнал аудита."""
    seq_arg = sequence_number

    def apply(conn):
        cur = conn.cursor()
        sn = seq_arg
        if sn is None:
            cur.execute("SELECT COALESCE(MAX(COALESCE(sequence_number, id)), 0) FROM audit_log")
            sn = int(cur.fetchone()[0] or 0) + 1
        ph = "" if previous_hash is None else previous_hash
        sig = "" if signature is None else signature
        cur.execute(
            """INSERT INTO audit_log
               (action, timestamp, entry_id, details, signature, sequence_number, previous_hash, entry_data, public_key)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                action,
                _timestamp(),
                entry_id,
                details or "",
                sig,
                sn,
                ph,
                entry_data,
                public_key,
            ),
        )
        if prune_max_entries is not None and prune_max_entries > 0:
            cur.execute("SELECT COUNT(*) FROM audit_log")
            total = int(cur.fetchone()[0])
            if total > prune_max_entries:
                to_remove = total - prune_max_entries
                cur.execute(
                    """DELETE FROM audit_log WHERE id IN (
                        SELECT id FROM audit_log ORDER BY id ASC LIMIT ?
                    )""",
                    (to_remove,),
                )
        conn.commit()

    _with_connection(apply)


def insert_shared_entry(
    shared_id: str,
    original_entry_id: Optional[int],
    encryption_method: str,
    recipient_info: str,
    permissions: str,
    expires_at: Optional[str] = None,
):
    """Insert or replace shared entry metadata. / Сохраняет метаданные общей записи."""
    def apply(conn):
        cur = conn.cursor()
        cur.execute(
            """INSERT OR REPLACE INTO shared_entries
               (shared_id, original_entry_id, encryption_method, recipient_info, permissions, shared_at, expires_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                shared_id,
                original_entry_id,
                encryption_method,
                recipient_info,
                permissions,
                _timestamp(),
                expires_at or "",
            ),
        )
        conn.commit()

    _with_connection(apply)


def list_shared_entries(limit: int = 200):
    """List shared entry records. / Список общих записей."""
    def apply(conn):
        cur = conn.cursor()
        cur.execute(
            """SELECT shared_id, original_entry_id, encryption_method, recipient_info, permissions, shared_at, expires_at
               FROM shared_entries ORDER BY id DESC LIMIT ?""",
            (limit,),
        )
        rows = cur.fetchall()
        out = []
        for r in rows:
            out.append(
                {
                    "shared_id": r[0],
                    "original_entry_id": r[1],
                    "encryption_method": r[2],
                    "recipient_info": r[3],
                    "permissions": r[4],
                    "shared_at": r[5],
                    "expires_at": r[6],
                }
            )
        return out

    return _with_connection(apply)


def insert_import_export_history(
    operation_type: str,
    format: str,
    encryption_used: str,
    entry_count: int,
    file_size: int,
    checksum: str,
    verification_status: str,
):
    """Record import/export operation in history. / Записывает операцию импорта/экспорта."""
    def apply(conn):
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO import_export_history
               (operation_type, format, encryption_used, entry_count, file_size, checksum, verification_status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                operation_type,
                format,
                encryption_used,
                int(entry_count or 0),
                int(file_size or 0),
                checksum or "",
                verification_status or "",
                _timestamp(),
            ),
        )
        conn.commit()

    _with_connection(apply)


def list_import_export_history(limit: int = 200):
    """List import/export history rows. / История операций импорта/экспорта."""
    def apply(conn):
        cur = conn.cursor()
        cur.execute(
            """SELECT operation_type, format, encryption_used, entry_count, file_size, checksum, verification_status, created_at
               FROM import_export_history ORDER BY id DESC LIMIT ?""",
            (limit,),
        )
        rows = cur.fetchall()
        out = []
        for r in rows:
            out.append(
                {
                    "operation_type": r[0],
                    "format": r[1],
                    "encryption_used": r[2],
                    "entry_count": r[3],
                    "file_size": r[4],
                    "checksum": r[5],
                    "verification_status": r[6],
                    "created_at": r[7],
                }
            )
        return out

    return _with_connection(apply)


def backup(dest_path: str, *, include_config: bool = True):
    """Create backup archive at dest_path. / Создаёт резервную копию."""
    from core.backup_service import create_backup

    return create_backup(dest_path, include_config=include_config)


def restore(path: str, *, restore_config: bool = False):
    """Restore vault from backup archive. / Восстанавливает хранилище из копии."""
    from core.backup_service import restore_backup

    return restore_backup(path, restore_config=restore_config)


def get_key_store(key_type):
    """Read key_data blob by key_type or None. / Читает ключ из key_store."""
    def apply(conn):
        cur = conn.cursor()
        cur.execute("SELECT key_data FROM key_store WHERE key_type = ? ORDER BY id DESC LIMIT 1", (key_type,))
        row = cur.fetchone()
        return row[0] if row and row[0] is not None else None

    return _with_connection(apply)


def set_key_store(key_type, key_data, version=1):
    """Replace key_store row for key_type. / Записывает ключ в key_store."""
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