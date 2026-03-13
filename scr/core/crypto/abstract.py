# базовый класс для любого шифрования; ключ теперь берётся через KeyManager (спринт 2)


class EncryptionService:
    # интерфейс: шифрование и расшифрование получают key_manager и берут ключ из него (спринт 2)
    def encrypt(self, data: bytes, key_manager) -> bytes:
        # данные шифруются ключом из key_manager.get_encryption_key() (спринт 2)
        raise NotImplementedError

    def decrypt(self, ciphertext: bytes, key_manager) -> bytes:
        # шифротекст расшифровывается тем же ключом через key_manager (спринт 2)
        raise NotImplementedError
