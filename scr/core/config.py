# Настройки лежат в отдельной БД, не в той где пароли.

import os
import sqlite3
import base64

def _config_path():
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, "config.db")

def _connect():
    path = _config_path()
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.execute(
        "CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)"
    )
    conn.commit()
    return conn

def get(key, default=None):
    conn = _connect()
    cur = conn.cursor()
    cur.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cur.fetchone()
    conn.close()
    if row is None:
        return default
    return row[0]

def set(key, value):
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        (key, str(value)),
    )
    conn.commit()
    conn.close()

DB_PATH = "db_path"
MASTER_PASSWORD_HASH = "master_password_hash"
VAULT_SALT = "vault_salt"
ENCRYPTION_ITERATIONS = "encryption_iterations"
CLIPBOARD_TIMEOUT = "clipboard_timeout"
AUTO_LOCK_MINUTES = "auto_lock_minutes"
THEME = "theme"
LANGUAGE = "language"

def get_vault_salt():
    # Соль берём из переменной окружения или из того что уже сохранили.
    env_salt = os.environ.get("CRYPTO_VAULT_SALT")
    if env_salt:
        try:
            return base64.b64decode(env_salt)
        except Exception:
            pass
    stored = get(VAULT_SALT)
    if stored:
        try:
            return base64.b64decode(stored)
        except Exception:
            pass
    default = b"vault"
    set(VAULT_SALT, base64.b64encode(default).decode("ascii"))
    return default
