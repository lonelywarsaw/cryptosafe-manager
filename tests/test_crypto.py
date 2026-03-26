# тесты шифрования AES-256-GCM с использованием key_manager (спринт 3)

import unittest

from core.vault.encryption_service import EncryptionServiceAESGCM


class _FakeKeyManager:
    # заглушка: get_encryption_key() возвращает заранее заданный ключ
    def __init__(self, key: bytes):
        self._key = key

    def get_encryption_key(self):
        return self._key


try:
    import cryptography  # noqa: F401
    _HAS_CRYPTO = True
except Exception:
    _HAS_CRYPTO = False


@unittest.skipUnless(_HAS_CRYPTO, "Пакет 'cryptography' не установлен — AES-GCM тесты пропускаются")
class TestAesGcmEncryption(unittest.TestCase):
    def test_roundtrip(self):
        # (спринт 3) зашифрованный BLOB формата nonce||ciphertext||tag можно расшифровать тем же ключом
        key = b"x" * 32
        km = _FakeKeyManager(key)
        cipher = EncryptionServiceAESGCM(km)

        payload = {
            "title": "T",
            "username": "u",
            "password": "secret",
            "url": "https://example.com",
            "notes": "n",
            "category": "c",
            "created_at": "123",
            "version": 1,
        }

        enc_blob = cipher.encrypt_entry_payload(payload).encrypted_blob
        self.assertIsInstance(enc_blob, (bytes, bytearray))
        # nonce — первые 12 байт; просто проверяем размер с запасом
        self.assertGreaterEqual(len(enc_blob), cipher.NONCE_LEN + 16)

        dec = cipher.decrypt_entry_payload(enc_blob)
        self.assertEqual(dec["password"], "secret")
        self.assertEqual(dec["title"], "T")

    def test_tampering_detected(self):
        # (ENC-5) при подмене ciphertext/auth tag расшифровка должна падать
        key = b"x" * 32
        km = _FakeKeyManager(key)
        cipher = EncryptionServiceAESGCM(km)

        payload = {
            "title": "T",
            "username": "u",
            "password": "secret",
            "url": "https://example.com",
            "notes": "n",
            "category": "",
            "created_at": "1",
            "version": 1,
        }
        enc_blob = bytearray(cipher.encrypt_entry_payload(payload).encrypted_blob)
        enc_blob[-1] ^= 0x01  # портим последний байт

        with self.assertRaises(Exception):
            cipher.decrypt_entry_payload(bytes(enc_blob))

    def test_different_keys_fail(self):
        # (безопасность) расшифровка другим ключом должна не проходить (InvalidTag)
        km1 = _FakeKeyManager(b"1" * 32)
        km2 = _FakeKeyManager(b"2" * 32)
        cipher1 = EncryptionServiceAESGCM(km1)
        cipher2 = EncryptionServiceAESGCM(km2)

        payload = {
            "title": "T",
            "username": "u",
            "password": "secret",
            "url": "https://example.com",
            "notes": "n",
            "category": "",
            "created_at": "1",
            "version": 1,
        }
        enc_blob = cipher1.encrypt_entry_payload(payload).encrypted_blob

        with self.assertRaises(Exception):
            cipher2.decrypt_entry_payload(enc_blob)

