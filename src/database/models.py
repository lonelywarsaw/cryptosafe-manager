"""Схема vault.db: SCHEMA_VERSION и DDL для init_db()."""

SCHEMA_VERSION = 5
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
        signature TEXT,
        sequence_number INTEGER,
        previous_hash TEXT,
        entry_data BLOB,
        public_key TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_audit_sequence ON audit_log(sequence_number)",
    "CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action)",
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
    """CREATE TABLE IF NOT EXISTS shared_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        shared_id TEXT UNIQUE,
        original_entry_id INTEGER,
        encryption_method TEXT,
        recipient_info TEXT,
        permissions TEXT,
        shared_at TEXT,
        expires_at TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS idx_shared_entries_shared_at ON shared_entries(shared_at)",
    "CREATE INDEX IF NOT EXISTS idx_shared_entries_expires_at ON shared_entries(expires_at)",
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
    )""",
    "CREATE INDEX IF NOT EXISTS idx_ie_history_created_at ON import_export_history(created_at)",
]
