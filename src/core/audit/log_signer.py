"""HMAC-подпись записей аудита; ключ подписи через HKDF от ключа шифрования."""

import hashlib
import hmac
from typing import Optional

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


def derive_audit_signing_key(encryption_key: Optional[bytes]) -> bytes:
    """Выводит 32-байтный ключ подписи журнала (отдельно от AES записей)."""
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
    """HMAC-SHA256 подпись и проверка payload журнала."""

    def __init__(self, signing_key: bytes):
        """Args:
            signing_key: Ключ HMAC (пустой — подпись отключена).
        """
        self._key = signing_key

    def sign(self, data: bytes) -> str:
        """Возвращает hex HMAC-SHA256 или пустую строку без ключа."""
        if not self._key:
            return ""
        return hmac.new(self._key, data, hashlib.sha256).hexdigest()

    def verify(self, data: bytes, signature_hex: str) -> bool:
        """Сравнивает подпись в постоянное время."""
        if not signature_hex or not self._key:
            return False
        try:
            expected = hmac.new(self._key, data, hashlib.sha256).hexdigest()
            return hmac.compare_digest(expected, signature_hex)
        except Exception:
            return False
