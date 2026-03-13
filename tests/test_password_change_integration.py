# TEST-5 спринт 2: создаём хранилище с паролем A, 10 записей, меняем пароль на B, проверяем доступ

import base64
import os
import secrets
import tempfile
import unittest

import database.db as db
from core.crypto.key_derivation import hash_password_argon2, derive_key_pbkdf2
from core.crypto.placeholder import AES256Placeholder
from core.crypto import key_storage


class _FakeKeyManager:
    def __init__(self, key):
        self._key = key

    def get_encryption_key(self):
        return self._key


class TestPasswordChangeIntegration(unittest.TestCase):
    def setUp(self):
        fd, self._db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        db.set_db_path(self._db_path)
        db.init_db()

    def tearDown(self):
        key_storage.clear_cached_key()
        db.set_db_path(None)
        if os.path.exists(self._db_path):
            try:
                os.unlink(self._db_path)
            except OSError:
                pass

    def test_change_password_all_entries_accessible(self):
        # пароли проходят валидатор силы (12+ символов, регистр, цифра, спецсимвол)
        pwd_a = "PasswordA123!"
        pwd_b = "PasswordB456!"
        salt_a = secrets.token_bytes(16)
        auth_hash_a = hash_password_argon2(pwd_a)
        db.set_key_store("auth_hash", auth_hash_a.encode("utf-8"))
        db.set_key_store("enc_salt", salt_a)
        key_a = derive_key_pbkdf2(pwd_a, salt_a)
        key_storage.set_cached_key(key_a)
        cipher = AES256Placeholder()
        km_a = _FakeKeyManager(key_a)
        # добавляем 10 записей с разными паролями
        plain_passwords = []
        for i in range(10):
            plain = "secret_%d_xyz" % i
            plain_passwords.append(plain)
            enc = cipher.encrypt(plain.encode("utf-8"), km_a)
            enc_b64 = base64.b64encode(enc).decode("ascii")
            db.insert_vault_entry("Title%d" % i, "user%d" % i, enc_b64, url="https://%d.example.com" % i)
        # смена пароля на B: новый ключ, перешифровка, обновление key_store
        salt_b = secrets.token_bytes(16)
        key_b = derive_key_pbkdf2(pwd_b, salt_b)
        auth_hash_b = hash_password_argon2(pwd_b)
        km_b = _FakeKeyManager(key_b)
        rows = db.get_all_vault_entries()
        for r in rows:
            eid, title, username, enc_b64, url, notes = r[0], r[1], r[2], r[3], r[4], r[5]
            raw = base64.b64decode(enc_b64.encode("ascii"))
            plain = cipher.decrypt(raw, km_a)
            new_enc = cipher.encrypt(plain, km_b)
            new_b64 = base64.b64encode(new_enc).decode("ascii")
            db.update_vault_entry(eid, title, username, new_b64, url=url or "", notes=notes or "")
        db.set_key_store("auth_hash", auth_hash_b.encode("utf-8"))
        db.set_key_store("enc_salt", salt_b)
        key_storage.set_cached_key(key_b)
        # проверяем: все 10 записей расшифровываются новым ключом и совпадают с исходными
        rows_after = db.get_all_vault_entries()
        self.assertEqual(len(rows_after), 10)
        for idx, r in enumerate(rows_after):
            enc_b64 = r[3]
            raw = base64.b64decode(enc_b64.encode("ascii"))
            dec = cipher.decrypt(raw, km_b)
            self.assertEqual(dec.decode("utf-8"), plain_passwords[idx])
