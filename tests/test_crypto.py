# Тесты шифрования — XOR туда-обратно, разные ключи.
import unittest

from core.crypto.placeholder import AES256Placeholder


class TestPlaceholderEncryption(unittest.TestCase):
    # Проверяем что encrypt/decrypt работают, ключ не теряется.

    def test_encrypt_decrypt_roundtrip(self):
        cipher = AES256Placeholder()
        key = b"x" * 32
        data = b"secret password"
        enc = cipher.encrypt(data, key)
        self.assertNotEqual(enc, data)
        dec = cipher.decrypt(enc, key)
        self.assertEqual(dec, data)

    def test_different_keys_different_ciphertext(self):
        cipher = AES256Placeholder()
        data = b"data"
        enc1 = cipher.encrypt(data, b"key1_________________________")
        enc2 = cipher.encrypt(data, b"key2_________________________")
        self.assertNotEqual(enc1, enc2)

    def test_empty_data(self):
        cipher = AES256Placeholder()
        key = b"k" * 32
        enc = cipher.encrypt(b"", key)
        self.assertEqual(enc, b"")
        dec = cipher.decrypt(b"", key)
        self.assertEqual(dec, b"")

    def test_decrypt_restores_plaintext(self):
        cipher = AES256Placeholder()
        key = bytes(32)
        plain = b"hello"
        self.assertEqual(cipher.decrypt(cipher.encrypt(plain, key), key), plain)
