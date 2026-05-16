# проверка целостности журнала при старте и по запросу (спринт 5, VER-1/VER-3)

import hashlib
from typing import Any, Dict, Optional

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


def verify_integrity(sample_limit: Optional[int] = None) -> Dict[str, Any]:
    max_entries = int(config.get(AUDIT_MAX_ENTRIES, "10000") or "10000")
    db.prune_audit_logs(max_entries)

    total = db.count_audit_logs()
    limit = sample_limit if sample_limit is not None else total
    if limit <= 0:
        return {"verified": True, "total_entries": 0, "breaks": [], "valid_entries": 0}

    rows = db.list_audit_logs(limit=limit, offset=0)
    rows = list(reversed(rows))
    result = verify_audit_chain(rows, _signer())
    result["total_in_db"] = total
    result["checked"] = len(rows)
    return result


def entry_hash_for_chain(entry_data: bytes, signature: str) -> str:
    return hashlib.sha256(entry_data + (signature or "").encode("utf-8")).hexdigest()
