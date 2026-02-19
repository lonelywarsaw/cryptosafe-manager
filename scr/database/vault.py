from datetime import datetime
from src.core.crypto.abstract import EncryptionService
from src.database.db import Database

def _now():
    return datetime.utcnow().isoformat() + "Z"

def insert_entry(db, crypto, key, title, username="", password="", url="", notes="", tags=""):
    if not title or not title.strip():
        raise ValueError("Title is required")
    title = title.strip()[:500]
    username = (username or "").strip()[:500]
    url = (url or "").strip()[:2000]
    notes = (notes or "").strip()[:10000]
    tags = (tags or "").strip()[:1000]
    enc_password = crypto.encrypt(password.encode("utf-8"), key)
    enc_notes = crypto.encrypt(notes.encode("utf-8"), key) if notes else b""
    now = _now()
    with db.cursor() as cur:
        cur.execute(
            """INSERT INTO vault_entries
               (title, username, encrypted_password, url, notes, tags, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (title, username, enc_password, url, enc_notes, tags, now, now),
        )
        cur.execute("SELECT last_insert_rowid()")
        row = cur.fetchone()
        return row[0] if row else 0

def update_entry(db, crypto, key, entry_id, title=None, username=None, password=None, url=None, notes=None, tags=None):
    row = db.fetchone("SELECT * FROM vault_entries WHERE id = ?", (entry_id,))
    if not row:
        raise ValueError("Entry not found")
    row = dict(row)
    if title is not None:
        row["title"] = title.strip()[:500]
    if username is not None:
        row["username"] = username.strip()[:500]
    if url is not None:
        row["url"] = url.strip()[:2000]
    if tags is not None:
        row["tags"] = tags.strip()[:1000]
    if password is not None:
        row["encrypted_password"] = crypto.encrypt(password.encode("utf-8"), key)
    if notes is not None:
        row["notes"] = crypto.encrypt(notes.encode("utf-8"), key) if notes else b""
    now = _now()
    with db.cursor() as cur:
        cur.execute(
            """UPDATE vault_entries SET
               title=?, username=?, encrypted_password=?, url=?, notes=?, tags=?, updated_at=?
               WHERE id=?""",
            (
                row["title"],
                row["username"],
                row["encrypted_password"],
                row.get("url") or "",
                row.get("notes") or b"",
                row.get("tags") or "",
                now,
                entry_id,
            ),
        )

def delete_entry(db, entry_id):
    with db.cursor() as cur:
        cur.execute("DELETE FROM vault_entries WHERE id = ?", (entry_id,))

def get_entries(db):
    rows = db.fetchall(
        "SELECT id, title, username, url, tags, created_at, updated_at FROM vault_entries ORDER BY updated_at DESC"
    )
    return [dict(r) for r in rows]
