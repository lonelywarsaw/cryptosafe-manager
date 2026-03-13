# тесты шифрования (xor) с использованием key_manager
import unittest
from core.crypto.placeholder import AES256Placeholder


class _FakeKeyManager:
    # заглушка: get_encryption_key() возвращает заранее заданный ключ
    def __init__(self, key: bytes):
        self._key = key

    def get_encryption_key(self):
        return self._key


class TestPlaceholderEncryption(unittest.TestCase):
    def test_roundtrip(self):
        # после шифрования и расшифровки через один и тот же key_manager получаются исходные данные
        c = AES256Placeholder()
        key = b"x" * 32
        km = _FakeKeyManager(key)
        data = b"secret"
        self.assertEqual(c.decrypt(c.encrypt(data, km), km), data)

    def test_different_keys(self):
        # один и тот же текст с разными key_manager даёт разный шифротекст
        c = AES256Placeholder()
        data = b"data"
        km1 = _FakeKeyManager(b"1" * 32)
        km2 = _FakeKeyManager(b"2" * 32)
        self.assertNotEqual(c.encrypt(data, km1), c.encrypt(data, km2))

    def test_empty(self):
        # пустые данные шифруются и расшифровываются в пустую строку без ошибки
        c = AES256Placeholder()
        km = _FakeKeyManager(bytes(32))
        self.assertEqual(c.encrypt(b"", km), b"")
        self.assertEqual(c.decrypt(b"", km), b"")

