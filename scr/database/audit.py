from src.core.events import (
    clipboard_cleared,
    clipboard_copied,
    entry_added,
    entry_deleted,
    entry_updated,
    user_logged_in,
    user_logged_out,
    event_bus,
)
from src.database.db import Database

def _now():
    from datetime import datetime
    return datetime.utcnow().isoformat() + "Z"

def _write_log(db, action, entry_id, details):
    try:
        with db.cursor() as cur:
            cur.execute(
                "INSERT INTO audit_log (action, timestamp, entry_id, details, signature) VALUES (?, ?, ?, ?, ?)",
                (action, _now(), entry_id, (details or "")[:2000], ""),
            )
    except Exception:
        pass

def _make_handler(db):
    def on_event(event, payload):
        _write_log(db, event, payload.get("entry_id"), str(payload.get("details", "")))
    return on_event

def register_audit_handlers(db):
    handler = _make_handler(db)
    for event in (entry_added, entry_updated, entry_deleted, user_logged_in, user_logged_out, clipboard_copied, clipboard_cleared):
        event_bus.subscribe(event, handler)
