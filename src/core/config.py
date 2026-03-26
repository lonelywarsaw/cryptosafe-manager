# config: путь к хранилищу, соль, настройки интерфейса (отдельно от бд с паролями)

import os
import sqlite3
import base64


def _config_path():
    # путь к файлу config.db — рядом с корнем проекта
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, "config.db")


def _ensure_settings_table(conn):
    # создаётся таблица settings, если её ещё нет (ключ — значение)
    conn.cursor().execute(
        "CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)"
    )
    conn.commit()


def _connect():
    # открывается config.db, создаётся таблица при необходимости, возвращается соединение
    path = _config_path()
    conn = sqlite3.connect(path)
    _ensure_settings_table(conn)
    return conn


def get(key, default=None):
    # чтение настройки по ключу; при отсутствии возвращается default
    conn = _connect()
    cur = conn.cursor()
    cur.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else default


def set(key, value):
    # запись настройки в config; при существующем ключе выполняется перезапись
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        (key, str(value)),
    )
    conn.commit()
    conn.close()


# константы — имена ключей в config, чтобы не ошибаться в строках по коду
DB_PATH = "db_path"
MASTER_PASSWORD_HASH = "master_password_hash"
VAULT_SALT = "vault_salt"
ENCRYPTION_ITERATIONS = "encryption_iterations"
CLIPBOARD_TIMEOUT = "clipboard_timeout"
AUTO_LOCK_MINUTES = "auto_lock_minutes"
LOCK_ON_FOCUS_LOST = "lock_on_focus_lost"
LOCK_ON_MINIMIZE = "lock_on_minimize"
THEME = "theme"
LANGUAGE = "language"


def _try_decode_salt(value):
    # попытка декодировать строку из base64 в байты; при ошибке возвращается None
    if not value:
        return None
    try:
        return base64.b64decode(value)
    except Exception:
        return None


def get_vault_salt():
    # соль для шифрования: сначала из переменной окружения CRYPTO_VAULT_SALT,
    # иначе из config; если нигде нет — сохраняется дефолт и возвращается
    salt = _try_decode_salt(os.environ.get("CRYPTO_VAULT_SALT"))
    if salt:
        return salt
    salt = _try_decode_salt(get(VAULT_SALT))
    if salt:
        return salt
    default = b"vault"
    set(VAULT_SALT, base64.b64encode(default).decode("ascii"))
    return default
