# контроллер аудита: события → структурированная запись + цепочка + подпись (спринт 5, ARC/LOG)

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from core import events
from core.key_manager import get_encryption_key
from database import db

from .log_signer import AuditLogSigner, derive_audit_signing_key


def _iso_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _severity_for_event(event_name: str) -> str:
    if "Failed" in event_name or "Error" in event_name:
        return "ERROR"
    return "INFO"


def _sanitize(details: Optional[str]) -> str:
    s = details or ""
    for token in ("password=", "secret=", "key=", "token="):
        if token in s.lower():
            return "[REDACTED]"
    return s


def _build_payload(
    event_type: str,
    entry_id: Optional[int],
    details: Optional[str],
    previous_hash: str,
    sequence_number: int,
) -> bytes:
    body: Dict[str, Any] = {
        "timestamp": _iso_utc(),
        "event_type": event_type,
        "severity": _severity_for_event(event_type),
        "user_id": "local",
        "source": "cryptosafe",
        "details": _sanitize(details),
        "entry_id": entry_id,
        "sequence_number": sequence_number,
        "previous_hash": previous_hash,
    }
    return json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")


def _log_event(event_type: str, entry_id=None, details=None):
    try:
        ek = get_encryption_key()
        sk = derive_audit_signing_key(ek)
        signer = AuditLogSigner(sk if sk else b"__no_session_audit_hmac_dev_only__")

        from .integrity import entry_hash_for_chain

        prev_row = db.get_audit_tail()
        if prev_row and prev_row.get("entry_data"):
            prev_hash = entry_hash_for_chain(
                prev_row["entry_data"] if isinstance(prev_row["entry_data"], bytes) else b"",
                str(prev_row.get("signature") or ""),
            )
            seq = int(prev_row.get("sequence_number") or prev_row.get("id") or 0) + 1
        else:
            prev_hash = "0" * 64
            seq = 1

        payload = _build_payload(event_type, entry_id, details, prev_hash, seq)
        signature = signer.sign(prev_hash.encode("utf-8") + b"|" + payload)

        db.insert_audit_log(
            event_type,
            entry_id,
            details or "",
            previous_hash=prev_hash,
            entry_data=payload,
            signature=signature,
            sequence_number=seq,
        )
    except Exception:
        pass


def register():
    events.subscribe(
        events.EntryAdded,
        lambda **kw: _log_event(events.EntryAdded, entry_id=kw.get("entry_id"), details=f"entry_id={kw.get('entry_id')}"),
    )
    events.subscribe(
        events.EntryCreated,
        lambda **kw: _log_event(events.EntryCreated, entry_id=kw.get("entry_id"), details=f"entry_id={kw.get('entry_id')}"),
    )
    events.subscribe(
        events.EntryUpdated,
        lambda **kw: _log_event(events.EntryUpdated, entry_id=kw.get("entry_id"), details=f"entry_id={kw.get('entry_id')}"),
    )
    events.subscribe(
        events.EntryDeleted,
        lambda **kw: _log_event(events.EntryDeleted, entry_id=kw.get("entry_id"), details=f"entry_id={kw.get('entry_id')}"),
    )
    events.subscribe(
        events.UserLoggedIn,
        lambda **kw: _log_event(events.UserLoggedIn, details=f"user={kw.get('username')}"),
    )
    events.subscribe(
        events.UserLoggedOut,
        lambda **kw: _log_event(events.UserLoggedOut, details="user_logged_out"),
    )
    events.subscribe(
        events.ClipboardCopied,
        lambda **kw: _log_event(
            events.ClipboardCopied,
            entry_id=kw.get("entry_id"),
            details=f"kind={kw.get('kind')}",
        ),
    )
    events.subscribe(
        events.ClipboardCleared,
        lambda **kw: _log_event(events.ClipboardCleared, details=f"reason={kw.get('reason')}"),
    )
