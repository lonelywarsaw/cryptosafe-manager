schema_version = 1
vault_entries_sql = """
CREATE TABLE IF NOT EXISTS vault_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    username TEXT,
    encrypted_password BLOB NOT NULL,
    url TEXT,
    notes TEXT,
    tags TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_vault_entries_title ON vault_entries(title);
CREATE INDEX IF NOT EXISTS idx_vault_entries_updated_at ON vault_entries(updated_at);
"""
audit_log_sql = """
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    entry_id INTEGER,
    details TEXT,
    signature TEXT
);
CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_log_entry_id ON audit_log(entry_id);
"""
settings_sql = """
CREATE TABLE IF NOT EXISTS settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    setting_key TEXT UNIQUE NOT NULL,
    setting_value BLOB,
    encrypted INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_settings_key ON settings(setting_key);
"""
key_store_sql = """
CREATE TABLE IF NOT EXISTS key_store (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key_type TEXT NOT NULL,
    salt BLOB,
    hash BLOB,
    params TEXT
);
"""
all_tables = [vault_entries_sql, audit_log_sql, settings_sql, key_store_sql]
