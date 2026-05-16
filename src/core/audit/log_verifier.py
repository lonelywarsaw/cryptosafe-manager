# проверка подписей и цепочки хешей журнала аудита (спринт 5, VER)

import hashlib
import json
from typing import Any, Dict, List, Optional

from .log_signer import AuditLogSigner


def _entry_hash(entry_data: bytes, signature: str) -> str:
    return hashlib.sha256(entry_data + (signature or "").encode("utf-8")).hexdigest()


def verify_audit_chain(rows: List[Dict[str, Any]], signer: Optional[AuditLogSigner]) -> Dict[str, Any]:
    breaks: List[Dict[str, Any]] = []
    skipped = signer is None
    ordered = sorted(rows, key=lambda r: int(r.get("sequence_number") or r.get("id") or 0))
    prev_chain_hash = "0" * 64
    valid = 0

    for row in ordered:
        seq = row.get("sequence_number")
        ph = row.get("previous_hash") or ""
        payload = row.get("entry_data") or b""
        if isinstance(payload, memoryview):
            payload = payload.tobytes()
        if isinstance(payload, str):
            payload = payload.encode("utf-8")
        sig = row.get("signature") or ""

        if ph != prev_chain_hash:
            breaks.append({"sequence": seq, "reason": "previous_hash_mismatch"})
        elif payload and sig and signer and not signer.verify(ph.encode("utf-8") + b"|" + payload, sig):
            breaks.append({"sequence": seq, "reason": "bad_signature"})
        else:
            valid += 1

        if payload:
            prev_chain_hash = _entry_hash(payload, sig)
        else:
            prev_chain_hash = hashlib.sha256((ph + sig).encode("utf-8")).hexdigest()

    return {
        "verified": not breaks,
        "breaks": breaks,
        "valid_entries": valid,
        "total_entries": len(ordered),
        "skipped": skipped,
    }


def summarize_entry(row: Dict[str, Any]) -> Dict[str, str]:
    payload = row.get("entry_data") or b""
    if isinstance(payload, memoryview):
        payload = payload.tobytes()
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    try:
        data = json.loads(payload.decode("utf-8"))
    except Exception:
        data = {}
    return {
        "timestamp": str(data.get("timestamp", row.get("timestamp", ""))),
        "event_type": str(data.get("event_type", row.get("action", ""))),
        "severity": str(data.get("severity", "")),
        "details": str(data.get("details", row.get("details", ""))),
    }
