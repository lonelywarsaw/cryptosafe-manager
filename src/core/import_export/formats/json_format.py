# зашифрованный JSON — основной формат экспорта (спринт 6, EXP-2)

import base64
import gzip
import hashlib
import json
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..export_crypto import (
    PBKDF2_EXPORT_ITERATIONS,
    decrypt_blob,
    derive_key_from_export_password,
    encrypt_blob,
    integrity_digest,
    verify_integrity,
)

FORMAT_ID = "cryptosafe-export-v1"
APP_NAME = "CryptoSafe Manager"


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _b64d(text: str) -> bytes:
    return base64.b64decode(text.encode("ascii"))


def build_encrypted_export(
    entries: List[Dict[str, Any]],
    export_password: str,
    *,
    include_notes: bool = True,
    compress: bool = False,
    data_key: Optional[bytes] = None,
    recipient_public_key_pem: Optional[str] = None,
) -> Dict[str, Any]:
    # data_key — одноразовый ключ данных (EXP-4); оборачивается паролем или RSA
    plain_entries = []
    for e in entries:
        item = {
            "title": e.get("title", "") or "",
            "username": e.get("username", "") or "",
            "password": e.get("password", "") or "",
            "url": e.get("url", "") or "",
            "category": e.get("category", "") or "",
        }
        if include_notes:
            item["notes"] = e.get("notes", "") or ""
        plain_entries.append(item)

    payload = {
        "entries": plain_entries,
        "exported_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    if compress:
        raw = gzip.compress(raw)

    if data_key is None:
        data_key = secrets.token_bytes(32)

    salt = secrets.token_bytes(16)
    wrap_mode = "password"
    if recipient_public_key_pem:
        from ..key_exchange import wrap_key_for_public

        wrapped = wrap_key_for_public(data_key, recipient_public_key_pem)
        kdf_meta = {"mode": "rsa-oaep", "wrapped_key": wrapped}
        wrap_mode = "rsa-oaep"
    else:
        wrap_key = derive_key_from_export_password(export_password, salt)
        w_nonce, w_cipher = encrypt_blob(data_key, wrap_key)
        kdf_meta = {
            "mode": "password",
            "salt": _b64(salt),
            "iterations": PBKDF2_EXPORT_ITERATIONS,
            "algorithm": "PBKDF2-HMAC-SHA256",
            "wrapped_key": {"nonce": _b64(w_nonce), "ciphertext": _b64(w_cipher)},
        }

    nonce, ciphertext = encrypt_blob(raw, data_key)
    sig = integrity_digest(raw, data_key)

    return {
        "format": FORMAT_ID,
        "metadata": {
            "app": APP_NAME,
            "version": 1,
            "entry_count": len(plain_entries),
            "compressed": compress,
            "wrap_mode": wrap_mode,
        },
        "kdf": kdf_meta,
        "nonce": _b64(nonce),
        "ciphertext": _b64(ciphertext),
        "integrity": {
            "sha256": hashlib.sha256(raw).hexdigest(),
            "hmac": sig,
        },
    }


def _unwrap_data_key(package: Dict[str, Any], export_password: str, private_key_pem: Optional[str]) -> bytes:
    kdf = package.get("kdf") or {}
    wrapped = kdf.get("wrapped_key") or {}
    mode = kdf.get("mode", "password")
    if mode == "rsa-oaep":
        if not private_key_pem:
            raise ValueError("Нужен закрытый ключ для расшифровки")
        from ..key_exchange import unwrap_key_with_private

        return unwrap_key_with_private(wrapped, private_key_pem)
    if mode == "password":
        salt = _b64d(kdf.get("salt", ""))
        iterations = int(kdf.get("iterations", PBKDF2_EXPORT_ITERATIONS))
        wrap_key = derive_key_from_export_password(export_password, salt, iterations)
        if wrapped:
            return decrypt_blob(_b64d(wrapped["nonce"]), _b64d(wrapped["ciphertext"]), wrap_key)
        return wrap_key
    raise ValueError("Неизвестный режим KDF")


def parse_encrypted_export(
    package: Dict[str, Any],
    export_password: str,
    *,
    private_key_pem: Optional[str] = None,
) -> List[Dict[str, Any]]:
    if package.get("format") != FORMAT_ID:
        raise ValueError("Неверный формат файла экспорта")

    key = _unwrap_data_key(package, export_password, private_key_pem)

    nonce = _b64d(package.get("nonce", ""))
    ciphertext = _b64d(package.get("ciphertext", ""))
    raw = decrypt_blob(nonce, ciphertext, key)

    integrity = package.get("integrity") or {}
    expected_sha = integrity.get("sha256")
    if expected_sha and hashlib.sha256(raw).hexdigest() != expected_sha:
        raise ValueError("Нарушена целостность экспорта (sha256)")

    hmac_sig = integrity.get("hmac")
    if hmac_sig and not verify_integrity(raw, key, hmac_sig):
        raise ValueError("Нарушена целостность экспорта (hmac)")

    if package.get("metadata", {}).get("compressed"):
        raw = gzip.decompress(raw)

    data = json.loads(raw.decode("utf-8"))
    return list(data.get("entries") or [])
