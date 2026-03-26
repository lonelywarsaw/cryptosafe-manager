# базовый класс для любого шифрования; ключ берётся через KeyManager


class EncryptionService:
    # интерфейс: шифрование и расшифрование получают key_manager и берут ключ из него
    def encrypt(self, data: bytes, key_manager) -> bytes:
        # данные шифруются ключом из key_manager.get_encryption_key()
        raise NotImplementedError

    def decrypt(self, ciphertext: bytes, key_manager) -> bytes:
        # шифротекст расшифровывается тем же ключом через key_manager
        raise NotImplementedError