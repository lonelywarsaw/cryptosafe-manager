"""Криптография экспорта/шаринга: HKDF, AES-GCM, HMAC (отдельно от ключа vault)."""

import hashlib
import hmac
import os
import secrets
from typing import Optional, Tuple

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from core.crypto.key_derivation import derive_key_pbkdf2
from core.key_manager import get_encryption_key

EXPORT_INFO = b"cryptosafe-export-v1"
SHARE_INFO = b"cryptosafe-share-v1"
PBKDF2_EXPORT_ITERATIONS = 100_000


def derive_export_material(master_key: Optional[bytes] = None, purpose: bytes = EXPORT_INFO) -> bytes:
    """Выводит 32-байтный материал HKDF из ключа хранилища для export/share.

    Args:
        master_key: Явный ключ; иначе из key_manager.
        purpose: info-байты HKDF (EXPORT_INFO или SHARE_INFO).

    Returns:
        Производный ключ.
    """
    mk = master_key if master_key else get_encryption_key()
    if not mk:
        raise ValueError("Хранилище заблокировано")
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"cryptosafe-ie-salt-v1",
        info=purpose,
    )
    return hkdf.derive(mk)


def derive_key_from_export_password(password: str, salt: bytes, iterations: int = PBKDF2_EXPORT_ITERATIONS) -> bytes:
    """Выводит ключ из пароля экспорта через PBKDF2-HMAC-SHA256."""
    return derive_key_pbkdf2(password, salt, iterations)


def encrypt_blob(data: bytes, key: bytes) -> Tuple[bytes, bytes]:
    """Шифрует данные AES-GCM.

    Returns:
        Пара (nonce, ciphertext).
    """
    nonce = os.urandom(12)
    ciphertext = AESGCM(key).encrypt(nonce, data, None)
    return nonce, ciphertext


def decrypt_blob(nonce: bytes, ciphertext: bytes, key: bytes) -> bytes:
    """Расшифровывает blob AES-GCM."""
    return AESGCM(key).decrypt(nonce, ciphertext, None)


def integrity_digest(data: bytes, key: bytes) -> str:
    """HMAC-SHA256 от данных в hex для поля integrity."""
    return hmac.new(key, data, hashlib.sha256).hexdigest()


def verify_integrity(data: bytes, key: bytes, expected_hex: str) -> bool:
    """Сравнивает HMAC целостности в постоянное время."""
    if not expected_hex:
        return False
    return hmac.compare_digest(integrity_digest(data, key), expected_hex)
