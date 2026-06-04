"""Обмен ключами RSA/ECC, контакты, отпечатки и обёртка data_key."""

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
    """Генерирует пару RSA в PEM (private, public)."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=bits)
    return _pem_private(private_key), _pem_public(private_key.public_key())


def generate_ecc_keypair() -> Tuple[str, str]:
    """Генерирует пару ECC P-256 в PEM (private, public)."""
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


def normalize_pem_block(pem_text: str) -> str:
    """Извлекает первый PEM-блок и нормализует переносы строк.

    Args:
        pem_text: Текст с одним или несколькими PEM-блоками.

    Returns:
        Один PEM-блок с завершающим переводом строки.
    """
    if not pem_text or not str(pem_text).strip():
        raise ValueError("Пустой PEM")
    text = str(pem_text).strip().replace("\r\n", "\n").replace("\r", "\n")
    if "-----BEGIN" not in text:
        raise ValueError("PEM должен содержать строки -----BEGIN ... -----")
    lines: List[str] = []
    in_block = False
    for raw in text.split("\n"):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("-----BEGIN"):
            if lines:
                break
            in_block = True
        if in_block:
            lines.append(line)
        if line.startswith("-----END"):
            break
    if len(lines) < 2 or not lines[0].startswith("-----BEGIN") or not lines[-1].startswith("-----END"):
        raise ValueError("Неполный PEM-блок")
    return "\n".join(lines) + "\n"


def optional_public_key_pem(pem_text: Optional[str]) -> Optional[str]:
    """Нормализует и проверяет PEM открытого ключа; пустая строка -> None."""
    if pem_text is None:
        return None
    stripped = str(pem_text).strip()
    if not stripped:
        return None
    normalized = normalize_pem_block(stripped)
    load_pem_public_key(normalized.encode("ascii"))
    return normalized


def optional_private_key_pem(pem_text: Optional[str]) -> Optional[str]:
    """Нормализует и проверяет PEM закрытого ключа; пустая строка -> None."""
    if pem_text is None:
        return None
    stripped = str(pem_text).strip()
    if not stripped:
        return None
    normalized = normalize_pem_block(stripped)
    load_pem_private_key(normalized.encode("ascii"), password=None)
    return normalized


def public_key_fingerprint(public_key_pem: str) -> str:
    """SHA256 от DER открытого ключа (первые 16 hex-символов)."""
    pem = normalize_pem_block(public_key_pem)
    pub = load_pem_public_key(pem.encode("ascii"))
    der = pub.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return hashlib.sha256(der).hexdigest()[:16]


def wrap_key_for_public(data_key: bytes, public_key_pem: str) -> Dict[str, str]:
    """Оборачивает data_key RSA-OAEP-SHA256 для получателя."""
    pem = normalize_pem_block(public_key_pem)
    pub = load_pem_public_key(pem.encode("ascii"))
    if not isinstance(pub, rsa.RSAPublicKey):
        raise ValueError("Для обёртки ключа поддерживается RSA-2048")
    wrapped = pub.encrypt(
        data_key,
        padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
    )
    return {"algorithm": "RSA-OAEP-SHA256", "ciphertext": base64.b64encode(wrapped).decode("ascii")}


def unwrap_key_with_private(wrapped: Dict[str, str], private_key_pem: str) -> bytes:
    """Снимает обёртку data_key закрытым RSA-ключом."""
    pem = normalize_pem_block(private_key_pem)
    priv = load_pem_private_key(pem.encode("ascii"), password=None)
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
    """Добавляет или обновляет контакт по отпечатку ключа в config."""
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
    """Возвращает список контактов (по умолчанию без отозванных)."""
    contacts = _load_contacts()
    if include_revoked:
        return contacts
    return [c for c in contacts if not c.get("revoked")]


def revoke_contact(fingerprint: str) -> bool:
    """Помечает контакт отозванным по отпечатку; True если найден."""
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
    """Отзывает старый ключ и регистрирует новый контакт."""
    revoke_contact(fingerprint)
    return add_contact(f"rotated-{fingerprint[:8]}", new_public_key_pem)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
