from src.core.crypto.abstract import EncryptionService

def _xor_bytes(data, key):
    if not key:
        return bytes(data)
    key_len = len(key)
    return bytes(b ^ key[i % key_len] for i, b in enumerate(data))

class AES256Placeholder(EncryptionService):
    def encrypt(self, data, key):
        if not key:
            raise ValueError("Key must not be empty")
        return _xor_bytes(data, key)

    def decrypt(self, ciphertext, key):
        if not key:
            raise ValueError("Key must not be empty")
        return _xor_bytes(ciphertext, key)
