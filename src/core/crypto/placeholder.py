# временное шифрование (xor); ключ берётся через KeyManager и обнуляется после использования (спринт 1 и 2)

import ctypes
from .abstract import EncryptionService


def _secure_zero(buf):
    # байты в памяти обнуляются, чтобы ключ не оставался в ram после операции
    if isinstance(buf, bytearray) and len(buf) > 0:
        arr = (ctypes.c_char * len(buf)).from_buffer(buf)
        ctypes.memset(ctypes.addressof(arr), 0, len(buf))


class AES256Placeholder(EncryptionService):
    # xor каждого байта с ключом; ключ берётся из key_manager, затем копия ключа обнуляется
    def encrypt(self, data: bytes, key_manager) -> bytes:
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
        # xor симметричен — расшифровка та же операция, что и шифрование
        return self.encrypt(ciphertext, key_manager)
