# описание схемы vault db: версия и список sql-команд для создания таблиц
# таблицы создаются в db.init_db() при первом запуске

SCHEMA_VERSION = 3
DDL = [
    """CREATE TABLE IF NOT EXISTS vault_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        encrypted_data BLOB,
        created_at TEXT,
        updated_at TEXT,
        tags TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS idx_vault_created_at ON vault_entries(created_at)",
    "CREATE INDEX IF NOT EXISTS idx_vault_updated_at ON vault_entries(updated_at)",
    "CREATE INDEX IF NOT EXISTS idx_vault_tags ON vault_entries(tags)",
    """CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        action TEXT,
        timestamp TEXT,
        entry_id INTEGER,
        details TEXT,
        signature TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp)",
    """CREATE TABLE IF NOT EXISTS settings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        setting_key TEXT UNIQUE,
        setting_value TEXT,
        encrypted INTEGER
    )""",
    # key_store с key_data (blob), version, created_at для хранения auth_hash и enc_salt (спринт 2)
    """CREATE TABLE IF NOT EXISTS key_store (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key_type TEXT,
        key_data BLOB,
        version INTEGER DEFAULT 1,
        created_at TEXT
    )""",
]
