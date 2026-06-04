"""Временное XOR-шифрование; ключ из KeyManager обнуляется после операции."""

import ctypes
from .abstract import EncryptionService


def _secure_zero(buf):
    # байты в памяти обнуляются, чтобы ключ не оставался в ram после операции
    if isinstance(buf, bytearray) and len(buf) > 0:
        arr = (ctypes.c_char * len(buf)).from_buffer(buf)
        ctypes.memset(ctypes.addressof(arr), 0, len(buf))


class AES256Placeholder(EncryptionService):
    """XOR-шифрование байтов с ключом из key_manager (заглушка AES-256)."""

    def encrypt(self, data: bytes, key_manager) -> bytes:
        """Шифрует data XOR с ключом; копия ключа обнуляется в finally."""
        key = key_manager.get_encryption_key()
        if key is None:
            raise ValueError("Ключ не задан (хранилище заблокировано)")
        key_arr = bytearray(key)
        try:
            out = bytearray(len(data))
            for i in range(len(data)):
                out[i] = data[i] ^ key_arr[i % len(key_arr)]
            return bytes(out)
        finally:
            _secure_zero(key_arr)

    def decrypt(self, ciphertext: bytes, key_manager) -> bytes:
        """Расшифровка совпадает с encrypt (XOR симметричен)."""
        return self.encrypt(ciphertext, key_manager)
