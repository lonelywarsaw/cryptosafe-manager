"""Базовый интерфейс шифрования; ключ берётся через KeyManager."""


class EncryptionService:
    """Абстрактный сервис шифрования записей хранилища."""

    def encrypt(self, data: bytes, key_manager) -> bytes:
        """Шифрует data ключом из key_manager.get_encryption_key()."""
        raise NotImplementedError

    def decrypt(self, ciphertext: bytes, key_manager) -> bytes:
        """Расшифровывает ciphertext тем же ключом."""
        raise NotImplementedError