# HMAC-подпись записей аудита (спринт 5, CRY-1 fallback); ключ отдельно от AES через HKDF

import hashlib
import hmac
from typing import Optional

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


def derive_audit_signing_key(encryption_key: Optional[bytes]) -> bytes:
    # отдельный материал для подписи логов — не совпадает с ключом шифрования записей
    if not encryption_key:
        return b""
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"cryptosafe-audit-salt-v1",
        info=b"audit-signing",
    )
    return hkdf.derive(encryption_key)


class AuditLogSigner:
    def __init__(self, signing_key: bytes):
        self._key = signing_key

    def sign(self, data: bytes) -> str:
        if not self._key:
            return ""
        return hmac.new(self._key, data, hashlib.sha256).hexdigest()

    def verify(self, data: bytes, signature_hex: str) -> bool:
        if not signature_hex or not self._key:
            return False
        try:
            expected = hmac.new(self._key, data, hashlib.sha256).hexdigest()
            return hmac.compare_digest(expected, signature_hex)
        except Exception:
            return False
