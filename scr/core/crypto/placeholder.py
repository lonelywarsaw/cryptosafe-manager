# XOR-шифрование. Ключ после использования зануляем в памяти.

import ctypes
from .abstract import EncryptionService

def _secure_zero(buf):
    if isinstance(buf, bytearray) and len(buf) > 0:
        arr = (ctypes.c_char * len(buf)).from_buffer(buf)
        ctypes.memset(ctypes.addressof(arr), 0, len(buf))


class AES256Placeholder(EncryptionService):

    def encrypt(self, data: bytes, key: bytes) -> bytes:
        key_arr = bytearray(key)
        try:
            out = bytearray(len(data))
            for i in range(len(data)):
                out[i] = data[i] ^ key_arr[i % len(key_arr)]
            return bytes(out)
        finally:
            _secure_zero(key_arr)

    def decrypt(self, ciphertext: bytes, key: bytes) -> bytes:
        return self.encrypt(ciphertext, key)
