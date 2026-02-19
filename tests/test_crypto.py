import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.crypto.placeholder import AES256Placeholder
from src.core.key_manager import KeyManager

class TestCrypto(unittest.TestCase):
    def setUp(self):
        self.crypto = AES256Placeholder()
        self.key_manager = KeyManager()
        self.sample_key = self.key_manager.derive_key("test_password", self.key_manager.generate_salt())

    def test_encrypt_decrypt_roundtrip(self):
        data = b"secret password"
        enc = self.crypto.encrypt(data, self.sample_key)
        self.assertNotEqual(enc, data)
        dec = self.crypto.decrypt(enc, self.sample_key)
        self.assertEqual(dec, data)

    def test_empty_key_raises(self):
        with self.assertRaises(ValueError):
            self.crypto.encrypt(b"x", b"")
        with self.assertRaises(ValueError):
            self.crypto.decrypt(b"x", b"")

if __name__ == "__main__":
    unittest.main()
