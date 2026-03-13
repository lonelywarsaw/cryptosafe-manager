# подписка на события → при срабатывании запись в таблицу audit_log
# по логу видно, кто какое действие выполнил

from . import events
from database import db


def _log(action, entry_id=None, details=None):
    # одна строка записывается в audit_log; ошибки не пробрасываются наружу
    try:
        test_details = f"[TEST] {details}" if details else "[TEST]"
        db.insert_audit_log(action, entry_id=entry_id, details=test_details)
    except Exception:
        pass


def register():
    # при старте приложения все события подписываются на _log; при publish() выполняется запись в бд
    events.subscribe(events.EntryAdded, lambda **kw: _log(events.EntryAdded, entry_id=kw.get("entry_id"), details=f"entry_id={kw.get('entry_id')}"))
    events.subscribe(events.EntryUpdated, lambda **kw: _log(events.EntryUpdated, entry_id=kw.get("entry_id"), details=f"entry_id={kw.get('entry_id')}"))
    events.subscribe(events.EntryDeleted, lambda **kw: _log(events.EntryDeleted, entry_id=kw.get("entry_id"), details=f"entry_id={kw.get('entry_id')}"))
    events.subscribe(events.UserLoggedIn, lambda **kw: _log(events.UserLoggedIn, details=f"user={kw.get('username')}"))
    events.subscribe(events.UserLoggedOut, lambda **kw: _log(events.UserLoggedOut, details="user_logged_out"))
    events.subscribe(events.ClipboardCopied, lambda **kw: _log(events.ClipboardCopied, details="clipboard_copied"))
    events.subscribe(events.ClipboardCleared, lambda **kw: _log(events.ClipboardCleared, details="clipboard_cleared"))
