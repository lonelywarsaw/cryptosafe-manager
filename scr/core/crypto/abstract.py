# Базовый класс для шифрования. Все реализации (XOR, AES и т.д.) наследуются отсюда.

class EncryptionService:
    # Два метода — зашифровать и расшифровать, ключ передаётся снаружи.

    def encrypt(self, data: bytes, key: bytes) -> bytes:
        raise NotImplementedError

    def decrypt(self, ciphertext: bytes, key: bytes) -> bytes:
        raise NotImplementedError
