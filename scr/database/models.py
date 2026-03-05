# Описание таблиц — что создаём в БД.

SCHEMA_VERSION = 1
DDL = [
    """CREATE TABLE IF NOT EXISTS vault_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        username TEXT,
        encrypted_password TEXT,
        url TEXT,
        notes TEXT,
        created_at TEXT,
        updated_at TEXT,
        tags TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS idx_vault_title ON vault_entries(title)",
    """CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        action TEXT,
        timestamp TEXT,
        entry_id INTEGER,
        details TEXT,
        signature TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS settings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        setting_key TEXT UNIQUE,
        setting_value TEXT,
        encrypted INTEGER
    )""",
    """CREATE TABLE IF NOT EXISTS key_store (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key_type TEXT,
        salt TEXT,
        hash TEXT,
        params TEXT
    )""",
]
