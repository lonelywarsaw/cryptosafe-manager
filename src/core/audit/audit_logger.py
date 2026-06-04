"""Контроллер аудита: подписка на события, цепочка хешей, HMAC-подпись."""

import hashlib
import json
import threading
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from core import config, events
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


_tls = threading.local()


def _get_signer() -> AuditLogSigner:
    signer = getattr(_tls, "signer", None)
    if signer is not None:
        return signer
    ek = get_encryption_key()
    sk = derive_audit_signing_key(ek)
    signer = AuditLogSigner(sk if sk else b"__no_session_audit_hmac_dev_only__")
    _tls.signer = signer
    return signer


def clear_chain_cache() -> None:
    """Drop cached chain tip and signer so the next log reads the DB tail."""
    _tls.chain_tip = None
    if hasattr(_tls, "signer"):
        delattr(_tls, "signer")


def _resolve_chain_tip() -> tuple[str, int]:
    from .integrity import entry_hash_for_chain

    tip = getattr(_tls, "chain_tip", None)
    if tip is not None:
        return tip["prev_hash"], int(tip["seq"]) + 1

    prev_row = db.get_audit_tail()
    if prev_row and prev_row.get("entry_data"):
        ed = prev_row["entry_data"]
        if not isinstance(ed, bytes):
            ed = b""
        prev_hash = entry_hash_for_chain(ed, str(prev_row.get("signature") or ""))
        seq = int(prev_row.get("sequence_number") or prev_row.get("id") or 0) + 1
    else:
        prev_hash = "0" * 64
        seq = 1
    return prev_hash, seq


def _schedule_log(event_type: str, entry_id=None, details=None) -> None:
    # PERF-5: некритичные события пишутся в фоне, publish/sync не блокируется
    threading.Thread(
        target=_log_event,
        args=(event_type,),
        kwargs={"entry_id": entry_id, "details": details},
        daemon=True,
    ).start()


def _log_event(event_type: str, entry_id=None, details=None):
    try:
        from .integrity import AUDIT_MAX_ENTRIES, entry_hash_for_chain, maybe_prune_audit_log

        signer = _get_signer()
        prev_hash, seq = _resolve_chain_tip()

        payload = _build_payload(event_type, entry_id, details, prev_hash, seq)
        signature = signer.sign(prev_hash.encode("utf-8") + b"|" + payload)

        max_entries = int(config.get(AUDIT_MAX_ENTRIES, "10000") or "10000")
        db.insert_audit_log(
            event_type,
            entry_id,
            details or "",
            previous_hash=prev_hash,
            entry_data=payload,
            signature=signature,
            sequence_number=seq,
            prune_max_entries=max_entries if seq >= max_entries else None,
        )

        _tls.chain_tip = {
            "prev_hash": entry_hash_for_chain(payload, signature),
            "seq": seq,
        }
        maybe_prune_audit_log(current_sequence=seq)
    except Exception:
        clear_chain_cache()


def register():
    """Подписывает обработчики core.events на запись в журнал аудита."""
    def _sub(event_type: str, builder: Callable[..., str], *, async_log: bool = False):
        def handler(**kw):
            details = builder(kw)
            if async_log:
                _schedule_log(event_type, entry_id=kw.get("entry_id"), details=details)
            else:
                _log_event(event_type, entry_id=kw.get("entry_id"), details=details)

        events.subscribe(event_type, handler)

    _sub(events.EntryAdded, lambda kw: f"entry_id={kw.get('entry_id')}")
    _sub(events.EntryCreated, lambda kw: f"entry_id={kw.get('entry_id')}")
    _sub(events.EntryUpdated, lambda kw: f"entry_id={kw.get('entry_id')}")
    _sub(events.EntryDeleted, lambda kw: f"entry_id={kw.get('entry_id')}")
    _sub(events.UserLoggedIn, lambda kw: f"user={kw.get('username')}")
    _sub(events.UserLoggedOut, lambda kw: "user_logged_out")
    _sub(
        events.ClipboardCopied,
        lambda kw: f"kind={kw.get('kind')}",
        async_log=True,
    )
    _sub(events.ClipboardCleared, lambda kw: f"reason={kw.get('reason')}", async_log=True)
    _sub(
        events.VaultExported,
        lambda kw: f"format={kw.get('format')} count={kw.get('entry_count')}",
        async_log=True,
    )
    _sub(
        events.VaultImported,
        lambda kw: f"mode={kw.get('mode')} added={kw.get('added')}",
        async_log=True,
    )
    _sub(events.EntryShared, lambda kw: f"permission={kw.get('permission')}", async_log=True)
    _sub(events.VaultLocked, lambda kw: f"reason={kw.get('reason', 'unknown')}")
    _sub(events.PanicModeActivated, lambda kw: f"method={kw.get('method', 'unknown')}")
    _sub(events.SecurityProfileChanged, lambda kw: f"profile={kw.get('profile')}")
    _sub(events.BackupCreated, lambda kw: f"path={kw.get('path')} entries={kw.get('entries')}", async_log=True)
    _sub(events.BackupRestored, lambda kw: f"path={kw.get('path')}", async_log=True)
