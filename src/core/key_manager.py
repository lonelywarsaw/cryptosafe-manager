"""Encryption key derivation and session cache. / Ключ шифрования: PBKDF2 и кэш в памяти."""

from core.crypto.key_derivation import derive_key_pbkdf2
from core.crypto import key_storage


def derive_key(password: str, salt: bytes, iterations: int = None) -> bytes:
    """Derive 32-byte key via PBKDF2-HMAC-SHA256. / Выводит ключ из пароля и соли."""
    return derive_key_pbkdf2(password, salt, iterations)


def get_encryption_key():
    """Return cached session key or None if locked. / Ключ из кэша или None."""
    return key_storage.get_cached_key()


def set_encryption_key(key: bytes):
    """Cache encryption key after unlock. / Сохраняет ключ в кэше после входа."""
    key_storage.set_cached_key(key)


def clear_encryption_key():
    """Clear cached key on lock or logout. / Очищает ключ при блокировке."""
    key_storage.clear_cached_key()


def store_key():
    """Persist key to DB (stub; use database.set_key_store). / Заглушка записи в key_store."""
    pass


def load_key():
    """Load key from DB (stub; use database.get_key_store). / Заглушка загрузки из key_store."""
    return None


_key_manager_instance = None


def get_key_manager():
    """Return singleton KeyManager instance. / Единый экземпляр KeyManager."""
    global _key_manager_instance
    if _key_manager_instance is None:
        _key_manager_instance = KeyManager()
    return _key_manager_instance


class KeyManager:
    """Facade for key derivation and session cache. / Обёртка над выводом ключа и кэшем."""

    def derive_key(self, password: str, salt: bytes, iterations: int = None) -> bytes:
        """Derive encryption key. / Выводит ключ шифрования."""
        return derive_key(password, salt, iterations)

    def get_encryption_key(self):
        """Return cached key. / Возвращает ключ из кэша."""
        return get_encryption_key()

    def set_encryption_key(self, key: bytes):
        """Cache key after unlock. / Кладёт ключ в кэш."""
        set_encryption_key(key)

    def clear_encryption_key(self):
        """Clear cached key. / Очищает кэш ключа."""
        clear_encryption_key()

    def store_key(self):
        """Persist key (stub). / Заглушка записи ключа."""
        store_key()

    def load_key(self):
        """Load key (stub). / Заглушка загрузки ключа."""
        return load_key()

