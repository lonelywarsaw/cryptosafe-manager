# проверка подписей записей аудита (спринт 5, заготовка VER)

from typing import Any, Dict, List, Optional

from .log_signer import AuditLogSigner


def verify_audit_chain(rows: List[Dict[str, Any]], signer: Optional[AuditLogSigner]) -> Dict[str, Any]:
    breaks: List[Dict[str, Any]] = []
    if not signer:
        return {"verified": True, "breaks": [], "skipped": True}
    for row in rows:
        seq = row.get("sequence_number")
        ph = (row.get("previous_hash") or "").encode("utf-8")
        payload = row.get("entry_data") or b""
        if isinstance(payload, memoryview):
            payload = payload.tobytes()
        if isinstance(payload, str):
            payload = payload.encode("utf-8")
        sig = row.get("signature") or ""
        if not payload or not sig:
            continue
        data = ph + b"|" + payload
        if not signer.verify(data, sig):
            breaks.append({"sequence": seq, "reason": "bad_signature"})
    return {"verified": not breaks, "breaks": breaks}
