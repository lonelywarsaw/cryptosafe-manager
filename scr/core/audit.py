# Подписываемся на события и пишем их в audit_log.

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from . import events
from database import db


def _log(action, entry_id=None, details=None):
    try:
        db.insert_audit_log(action, entry_id=entry_id, details=details or "")
    except Exception:
        pass


def register():
    events.subscribe(events.EntryAdded, lambda **kw: _log(events.EntryAdded, entry_id=kw.get("entry_id"), details=str(kw)))
    events.subscribe(events.EntryUpdated, lambda **kw: _log(events.EntryUpdated, entry_id=kw.get("entry_id"), details=str(kw)))
    events.subscribe(events.EntryDeleted, lambda **kw: _log(events.EntryDeleted, entry_id=kw.get("entry_id"), details=str(kw)))
    events.subscribe(events.UserLoggedIn, lambda **kw: _log(events.UserLoggedIn, details=str(kw)))
    events.subscribe(events.UserLoggedOut, lambda **kw: _log(events.UserLoggedOut, details=str(kw)))
    events.subscribe(events.ClipboardCopied, lambda **kw: _log(events.ClipboardCopied, details=str(kw)))
    events.subscribe(events.ClipboardCleared, lambda **kw: _log(events.ClipboardCleared, details=str(kw)))
