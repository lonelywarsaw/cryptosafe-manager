"""App settings store (paths, salt, UI). / Настройки приложения в config.db."""

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
    """Read setting by key or default. / Читает настройку по ключу."""
    conn = _connect()
    cur = conn.cursor()
    cur.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else default


def set(key, value):
    """Write or replace setting value. / Записывает настройку."""
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
CLIPBOARD_NOTIFICATIONS = "clipboard_notifications"
CLIPBOARD_SECURITY_LEVEL = "clipboard_security_level"
CLIPBOARD_APP_WHITELIST = "clipboard_app_whitelist"
SECURITY_PROFILE = "security_profile"
ACTIVITY_SENSITIVITY = "activity_sensitivity"
MEMORY_LOCK_ENABLED = "memory_lock_enabled"
MINIMIZE_TO_TRAY = "minimize_to_tray"
START_MINIMIZED_TRAY = "start_minimized_tray"
PANIC_HOTKEY_ENABLED = "panic_hotkey_enabled"
PANIC_STEALTH_MODE = "panic_stealth_mode"
DEVICE_PROFILE = "device_profile"


def _try_decode_salt(value):
    # попытка декодировать строку из base64 в байты; при ошибке возвращается None
    if not value:
        return None
    try:
        return base64.b64decode(value)
    except Exception:
        return None


def get_vault_salt():
    """Return vault salt (env, config, or default). / Возвращает соль для шифрования."""
    salt = _try_decode_salt(os.environ.get("CRYPTO_VAULT_SALT"))
    if salt:
        return salt
    salt = _try_decode_salt(get(VAULT_SALT))
    if salt:
        return salt
    default = b"vault"
    set(VAULT_SALT, base64.b64encode(default).decode("ascii"))
    return default
