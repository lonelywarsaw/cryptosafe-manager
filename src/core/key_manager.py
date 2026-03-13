# работа с ключом шифрования: вывод через PBKDF2, кэш в памяти (KeyManager + key_storage) (спринт 2)

from core.crypto.key_derivation import derive_key_pbkdf2
from core.crypto import key_storage


def derive_key(password: str, salt: bytes, iterations: int = None) -> bytes:
    # из пароля и соли получается ключ 32 байта через PBKDF2-HMAC-SHA256
    return derive_key_pbkdf2(password, salt, iterations)


def get_encryption_key():
    # возвращается ключ из кэша после успешного входа или None, если сессия заблокирована
    return key_storage.get_cached_key()


def set_encryption_key(key: bytes):
    # после успешного входа ключ кладётся в кэш для быстрого доступа при шифровании
    key_storage.set_cached_key(key)


def clear_encryption_key():
    # при выходе или авто-блокировке ключ удаляется и обнуляется в памяти
    key_storage.clear_cached_key()


def store_key():
    # запись в key_store делается в setup_wizard и change_password через database.set_key_store; здесь заглушка API
    pass


def load_key():
    # загрузка из key_store делается в unlock_dialog через database.get_key_store; здесь заглушка API
    return None


_key_manager_instance = None


def get_key_manager():
    # возвращается один общий экземпляр KeyManager для всего приложения
    global _key_manager_instance
    if _key_manager_instance is None:
        _key_manager_instance = KeyManager()
    return _key_manager_instance


class KeyManager:
    # объект-обёртка: тут собраны derive_key и работа с кэшем ключа
    def derive_key(self, password: str, salt: bytes, iterations: int = None) -> bytes:
        return derive_key(password, salt, iterations)

    def get_encryption_key(self):
        return get_encryption_key()

    def set_encryption_key(self, key: bytes):
        set_encryption_key(key)

    def clear_encryption_key(self):
        clear_encryption_key()

    def store_key(self):
        store_key()

    def load_key(self):
        return load_key()

