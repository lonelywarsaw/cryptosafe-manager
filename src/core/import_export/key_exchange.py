# обмен ключами RSA/ECC, контакты, отпечатки (спринт 6, QR-3)

import base64
import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
from cryptography.hazmat.primitives.asymmetric.types import PrivateKeyTypes, PublicKeyTypes
from cryptography.hazmat.primitives.serialization import load_pem_private_key, load_pem_public_key

from core import config

CONTACTS_CONFIG_KEY = "ie_contact_public_keys"


def generate_rsa_keypair(bits: int = 2048) -> Tuple[str, str]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=bits)
    return _pem_private(private_key), _pem_public(private_key.public_key())


def generate_ecc_keypair() -> Tuple[str, str]:
    private_key = ec.generate_private_key(ec.SECP256R1())
    return _pem_private(private_key), _pem_public(private_key.public_key())


def _pem_private(key: PrivateKeyTypes) -> str:
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")


def _pem_public(key: PublicKeyTypes) -> str:
    return key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")


def public_key_fingerprint(public_key_pem: str) -> str:
    pub = load_pem_public_key(public_key_pem.encode("ascii"))
    der = pub.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return hashlib.sha256(der).hexdigest()[:16]


def wrap_key_for_public(data_key: bytes, public_key_pem: str) -> Dict[str, str]:
    pub = load_pem_public_key(public_key_pem.encode("ascii"))
    if not isinstance(pub, rsa.RSAPublicKey):
        raise ValueError("Для обёртки ключа поддерживается RSA-2048")
    wrapped = pub.encrypt(
        data_key,
        padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
    )
    return {"algorithm": "RSA-OAEP-SHA256", "ciphertext": base64.b64encode(wrapped).decode("ascii")}


def unwrap_key_with_private(wrapped: Dict[str, str], private_key_pem: str) -> bytes:
    priv = load_pem_private_key(private_key_pem.encode("ascii"), password=None)
    if not isinstance(priv, rsa.RSAPrivateKey):
        raise ValueError("Нужен RSA закрытый ключ")
    cipher = base64.b64decode(wrapped.get("ciphertext", "").encode("ascii"))
    return priv.decrypt(
        cipher,
        padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
    )


def _load_contacts() -> List[Dict[str, Any]]:
    raw = config.get(CONTACTS_CONFIG_KEY)
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return list(data.get("contacts") or [])
    except (json.JSONDecodeError, TypeError):
        return []


def _save_contacts(contacts: List[Dict[str, Any]]) -> None:
    config.set(CONTACTS_CONFIG_KEY, json.dumps({"contacts": contacts}, ensure_ascii=False))


def add_contact(name: str, public_key_pem: str) -> Dict[str, Any]:
    fp = public_key_fingerprint(public_key_pem)
    contacts = _load_contacts()
    for c in contacts:
        if c.get("fingerprint") == fp:
            c["revoked"] = False
            c["name"] = name
            c["public_key"] = public_key_pem
            c["updated_at"] = _now()
            _save_contacts(contacts)
            return c
    entry = {
        "name": name,
        "public_key": public_key_pem,
        "fingerprint": fp,
        "revoked": False,
        "created_at": _now(),
    }
    contacts.append(entry)
    _save_contacts(contacts)
    return entry


def list_contacts(include_revoked: bool = False) -> List[Dict[str, Any]]:
    contacts = _load_contacts()
    if include_revoked:
        return contacts
    return [c for c in contacts if not c.get("revoked")]


def revoke_contact(fingerprint: str) -> bool:
    contacts = _load_contacts()
    changed = False
    for c in contacts:
        if c.get("fingerprint") == fingerprint:
            c["revoked"] = True
            c["revoked_at"] = _now()
            changed = True
    if changed:
        _save_contacts(contacts)
    return changed


def rotate_contact_keys(fingerprint: str, new_public_key_pem: str) -> Optional[Dict[str, Any]]:
    revoke_contact(fingerprint)
    return add_contact(f"rotated-{fingerprint[:8]}", new_public_key_pem)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
