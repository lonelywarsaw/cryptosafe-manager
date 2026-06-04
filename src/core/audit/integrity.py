"""Проверка целостности журнала аудита при старте и по запросу."""

import hashlib
from typing import Any, Dict, List, Optional

from core import config
from core.key_manager import get_encryption_key
from database import db

from .log_signer import AuditLogSigner, derive_audit_signing_key
from .log_verifier import verify_audit_chain


AUDIT_MAX_ENTRIES = "audit_max_entries"


def _signer() -> AuditLogSigner:
    ek = get_encryption_key()
    sk = derive_audit_signing_key(ek)
    return AuditLogSigner(sk if sk else b"__no_session_audit_hmac_dev_only__")


def _fetch_rows_for_verify(total: int, sample_limit: Optional[int]) -> List[Dict[str, Any]]:
    """Load chronological slice for chain verification (with optional chain anchor row)."""
    if total <= 0:
        return []

    if sample_limit is None or sample_limit >= total:
        offset = 0
        limit = total
        anchor = False
    else:
        limit = int(sample_limit)
        offset = total - limit
        anchor = offset > 0

    fetch_offset = offset - 1 if anchor else offset
    fetch_limit = limit + (1 if anchor else 0)
    return db.list_audit_logs_chronological(limit=fetch_limit, offset=fetch_offset)


def verify_integrity(sample_limit: Optional[int] = None) -> Dict[str, Any]:
    """Проверяет цепочку и подписи журнала (с опциональной выборкой хвоста).

    Args:
        sample_limit: Макс. число последних записей; None — весь журнал.

    Returns:
        Словарь verified, breaks, valid_entries, total_in_db, checked, partial.
    """
    total = db.count_audit_logs()
    if total <= 0:
        return {
            "verified": True,
            "total_entries": 0,
            "total_in_db": 0,
            "checked": 0,
            "breaks": [],
            "valid_entries": 0,
            "partial": False,
        }

    rows = _fetch_rows_for_verify(total, sample_limit)
    partial = sample_limit is not None and sample_limit < total
    result = verify_audit_chain(rows, _signer())
    result["total_in_db"] = total
    result["checked"] = len(rows)
    result["partial"] = partial
    return result


def entry_hash_for_chain(entry_data: bytes, signature: str) -> str:
    """Хеш звена цепочки: SHA256(entry_data || signature)."""
    return hashlib.sha256(entry_data + (signature or "").encode("utf-8")).hexdigest()


def maybe_prune_audit_log(current_sequence: Optional[int] = None) -> int:
    """Trim audit log after append if over configured limit. Call after insert, not on verify."""
    max_entries = int(config.get(AUDIT_MAX_ENTRIES, "10000") or "10000")
    if current_sequence is not None and current_sequence < max_entries:
        return 0
    return db.prune_audit_logs(max_entries)


def clear_audit_chain_cache() -> None:
    """Invalidate in-process chain tip cache (e.g. after restore)."""
    from . import audit_logger

    audit_logger.clear_chain_cache()
