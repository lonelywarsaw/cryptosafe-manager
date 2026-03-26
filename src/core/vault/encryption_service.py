import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict


# ВАЖНО (спринт3):
# - используется AES-256-GCM из `cryptography.hazmat.primitives.ciphers.aead.AESGCM`
# - уникальный nonce генерируется через os.urandom(12)
# - формат хранения: nonce (12B) || ciphertext || tag(16B) как один BLOB
#   (в библиотеке cryptography ciphertext+tag возвращаются одним буфером)
@dataclass(frozen=True)
class EncryptedEntry:
    # BLOB в формате nonce || ciphertext||tag
    encrypted_blob: bytes


class EncryptionServiceAESGCM:
    VERSION = 1
    NONCE_LEN = 12

    def __init__(self, key_manager):
        # key_manager — это KeyManager из спринт 2 (кэш ключа в памяти после логина)
        self._key_manager = key_manager

    def _get_aesgcm(self):
        # ленивый импорт: чтобы модуль можно было импортировать даже без установленного пакета cryptography
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        except Exception as e:
            raise RuntimeError(
                "Зависимость 'cryptography' не установлена, AES-256-GCM недоступен (спринт3)."
            ) from e

        key = self._key_manager.get_encryption_key()
        if not key:
            # общий текст ошибки: чтобы не раскрывать состояние конкретных id
            raise ValueError("Хранилище заблокировано или ключ недоступен (PBKDF2)")
        return AESGCM(key)

    def encrypt_entry_payload(self, payload: Dict[str, Any]) -> EncryptedEntry:
        # payload шифруется как JSON, чтобы внутри можно было версионировать поля
        aesgcm = self._get_aesgcm()

        nonce = os.urandom(self.NONCE_LEN)
        plaintext = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        # ciphertext_with_tag = ciphertext || tag(16B)
        ciphertext_with_tag = aesgcm.encrypt(nonce, plaintext, None)

        # nonce (12B) || ciphertext || tag(16B)
        encrypted_blob = nonce + ciphertext_with_tag
        return EncryptedEntry(encrypted_blob=encrypted_blob)

    def decrypt_entry_payload(self, encrypted_blob: bytes) -> Dict[str, Any]:
        if not encrypted_blob or len(encrypted_blob) < (self.NONCE_LEN + 16):
            raise ValueError("Повреждённый зашифрованный формат")

        aesgcm = self._get_aesgcm()

        nonce = encrypted_blob[: self.NONCE_LEN]
        ciphertext_with_tag = encrypted_blob[self.NONCE_LEN :]

        # AESGCM.decrypt проверяет authentication tag и выбрасывает исключение при подмене
        plaintext = aesgcm.decrypt(nonce, ciphertext_with_tag, None)
        return json.loads(plaintext.decode("utf-8"))

    @staticmethod
    def build_payload_for_encrypt(data_dict: Dict[str, Any], created_at: str) -> Dict[str, Any]:
        # data_dict ожидает plaintext поля (после валидации GUI).
        return {
            "title": data_dict.get("title", ""),
            "username": data_dict.get("username", ""),
            "password": data_dict.get("password", ""),
            "url": data_dict.get("url", ""),
            "notes": data_dict.get("notes", ""),
            "category": data_dict.get("category", ""),
            "created_at": created_at,  # timestamp внутри payload (для целостности формата)
            "version": EncryptionServiceAESGCM.VERSION,
        }

    @staticmethod
    def now_timestamp() -> str:
        # Везде используем простой timestamp как string (совместимо с существующим db.py)
        return str(int(time.time()))

