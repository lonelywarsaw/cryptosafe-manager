# безопасный шаринг одной записи (спринт 6, SHR)

import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from core import events

from .export_crypto import SHARE_INFO, decrypt_blob, derive_export_material, encrypt_blob, integrity_digest, verify_integrity
from .formats.json_format import derive_key_from_export_password
from .key_exchange import wrap_key_for_public, unwrap_key_with_private

SHARE_FORMAT = "cryptosafe-share-v1"


class SharingService:
    def create_password_share(
        self,
        entry: Dict[str, Any],
        share_password: str,
        *,
        sharer: str = "local",
        expires_days: int = 7,
        permission: str = "read_only",
    ) -> Dict[str, Any]:
        if permission not in ("read_only", "editable"):
            raise ValueError("permission: read_only или editable")
        if not 1 <= expires_days <= 30:
            raise ValueError("expires_days: от 1 до 30")
        _ = derive_export_material(purpose=SHARE_INFO)
        salt = secrets.token_bytes(16)
        data_key = secrets.token_bytes(32)
        wrap_key = derive_key_from_export_password(share_password, salt)
        w_nonce, w_cipher = encrypt_blob(data_key, wrap_key)

        payload = {
            "entry": {
                "title": entry.get("title", ""),
                "username": entry.get("username", ""),
                "password": entry.get("password", ""),
                "url": entry.get("url", ""),
                "notes": entry.get("notes", ""),
                "category": entry.get("category", ""),
            }
        }
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        nonce, ciphertext = encrypt_blob(raw, data_key)
        expires_at = (datetime.now(timezone.utc) + timedelta(days=expires_days)).strftime("%Y-%m-%dT%H:%M:%SZ")

        package = {
            "format": SHARE_FORMAT,
            "metadata": {
                "sharer": sharer,
                "expires_at": expires_at,
                "permission": permission,
                "delivery": "file",
            },
            "kdf": {
                "mode": "password",
                "salt": _b64(salt),
                "wrapped_key": {"nonce": _b64(w_nonce), "ciphertext": _b64(w_cipher)},
            },
            "nonce": _b64(nonce),
            "ciphertext": _b64(ciphertext),
            "integrity": {"hmac": integrity_digest(raw, data_key)},
        }
        events.publish(events.EntryShared, sync=True, permission=permission, expires_days=expires_days)
        return package

    def create_public_key_share(
        self,
        entry: Dict[str, Any],
        recipient_public_key_pem: str,
        *,
        sharer: str = "local",
        expires_days: int = 7,
        permission: str = "read_only",
    ) -> Dict[str, Any]:
        _ = derive_export_material(purpose=SHARE_INFO)
        data_key = secrets.token_bytes(32)
        wrapped = wrap_key_for_public(data_key, recipient_public_key_pem)
        payload = {"entry": {k: entry.get(k, "") for k in ("title", "username", "password", "url", "notes", "category")}}
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        nonce, ciphertext = encrypt_blob(raw, data_key)
        expires_at = (datetime.now(timezone.utc) + timedelta(days=expires_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        package = {
            "format": SHARE_FORMAT,
            "metadata": {
                "sharer": sharer,
                "expires_at": expires_at,
                "permission": permission,
                "delivery": "public_key",
            },
            "kdf": {"mode": "rsa-oaep", "wrapped_key": wrapped},
            "nonce": _b64(nonce),
            "ciphertext": _b64(ciphertext),
            "integrity": {"hmac": integrity_digest(raw, data_key)},
        }
        events.publish(events.EntryShared, sync=True, permission=permission, delivery="public_key")
        return package

    def import_share(
        self,
        package: Dict[str, Any],
        *,
        share_password: str = "",
        private_key_pem: Optional[str] = None,
    ) -> Dict[str, Any]:
        if package.get("format") != SHARE_FORMAT:
            raise ValueError("Неверный формат share-пакета")
        meta = package.get("metadata") or {}
        expires_at = meta.get("expires_at")
        if expires_at:
            exp = datetime.strptime(expires_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > exp:
                raise ValueError("Срок действия share истёк")

        kdf = package.get("kdf") or {}
        if kdf.get("mode") == "rsa-oaep":
            data_key = unwrap_key_with_private(kdf.get("wrapped_key") or {}, private_key_pem or "")
        else:
            salt = _b64d(kdf.get("salt", ""))
            wrap_key = derive_key_from_export_password(share_password, salt)
            wrapped = kdf.get("wrapped_key") or {}
            data_key = decrypt_blob(_b64d(wrapped["nonce"]), _b64d(wrapped["ciphertext"]), wrap_key)

        nonce = _b64d(package.get("nonce", ""))
        ciphertext = _b64d(package.get("ciphertext", ""))
        raw = decrypt_blob(nonce, ciphertext, data_key)
        sig = (package.get("integrity") or {}).get("hmac")
        if sig and not verify_integrity(raw, data_key, sig):
            raise ValueError("Нарушена целостность share")
        data = json.loads(raw.decode("utf-8"))
        entry = data.get("entry") or {}
        entry["permission"] = meta.get("permission", "read_only")
        entry["temporary"] = True
        return entry

    def create_share_link_token(self, entry: Dict[str, Any], expires_days: int = 1) -> str:
        # опциональный «link» без сети: токен на локальную расшифровку из пакета
        pkg = self.create_password_share(entry, secrets.token_urlsafe(16), expires_days=expires_days)
        import base64

        return base64.urlsafe_b64encode(json.dumps(pkg, ensure_ascii=False).encode("utf-8")).decode("ascii")


def _b64(data: bytes) -> str:
    import base64

    return base64.b64encode(data).decode("ascii")


def _b64d(text: str) -> bytes:
    import base64

    return base64.b64decode(text.encode("ascii"))
