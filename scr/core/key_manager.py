import hashlib
import secrets
from pathlib import Path

class KeyManager:
    def __init__(self, key_file=None):
        self._key_file = key_file or Path.home() / ".cryptosafe" / "key.dat"

    def derive_key(self, password, salt):
        if not password:
            raise ValueError("Password must not be empty")
        if not salt or len(salt) < 8:
            raise ValueError("Salt at least 8 bytes")
        return hashlib.sha256(password.encode("utf-8") + salt).digest()

    def store_key(self, key):
        self._key_file.parent.mkdir(parents=True, exist_ok=True)

    def load_key(self):
        return None

    @staticmethod
    def generate_salt(size=32):
        return secrets.token_bytes(size)
