# TEST-5 спринт 2 (обновлён под спринт 3): создаём хранилище с паролем A, 10 записей,
# меняем пароль на B, проверяем что все записи доступны с новым ключом AES-256-GCM.

import os
import secrets
import tempfile
import unittest

import database.db as db
from core.crypto.key_derivation import hash_password_argon2, derive_key_pbkdf2
from core.crypto import key_storage
from core.vault.encryption_service import EncryptionServiceAESGCM


try:
    import cryptography  # noqa: F401
    _HAS_CRYPTO = True
except Exception:
    _HAS_CRYPTO = False


class _FakeKeyManager:
    def __init__(self, key):
        self._key = key

    def get_encryption_key(self):
        return self._key


@unittest.skipUnless(_HAS_CRYPTO, "Пакет 'cryptography' не установлен — AES-GCM тесты пропускаются")
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
        cipher_a = EncryptionServiceAESGCM(_FakeKeyManager(key_a))
        # добавляем 10 записей с разными паролями
        plain_passwords = []
        for i in range(10):
            plain = "secret_%d_xyz" % i
            plain_passwords.append(plain)
            payload = {
                "title": "Title%d" % i,
                "username": "user%d" % i,
                "password": plain,
                "url": "https://%d.example.com" % i,
                "notes": "",
                "category": "",
                "created_at": str(1000 + i),
                "version": 1,
            }
            encrypted_blob = cipher_a.encrypt_entry_payload(payload).encrypted_blob
            db.insert_vault_entry(encrypted_data=encrypted_blob, tags="")
        # смена пароля на B: новый ключ, перешифровка, обновление key_store
        salt_b = secrets.token_bytes(16)
        key_b = derive_key_pbkdf2(pwd_b, salt_b)
        auth_hash_b = hash_password_argon2(pwd_b)
        cipher_b = EncryptionServiceAESGCM(_FakeKeyManager(key_b))
        rows = db.get_all_vault_entries()
        for r in rows:
            eid, encrypted_data, created_at, updated_at, tags = r
            plain_payload = cipher_a.decrypt_entry_payload(encrypted_data)
            created_at_use = created_at or plain_payload.get("created_at") or cipher_a.now_timestamp()
            payload_new = EncryptionServiceAESGCM.build_payload_for_encrypt(plain_payload, created_at=created_at_use)
            encrypted_new = cipher_b.encrypt_entry_payload(payload_new).encrypted_blob
            db.update_vault_entry(eid, encrypted_data=encrypted_new, tags=tags)

        db.set_key_store("auth_hash", auth_hash_b.encode("utf-8"))
        db.set_key_store("enc_salt", salt_b)
        key_storage.set_cached_key(key_b)
        # проверяем: все 10 записей расшифровываются новым ключом и совпадают с исходными
        rows_after = db.get_all_vault_entries()
        self.assertEqual(len(rows_after), 10)
        for idx, r in enumerate(rows_after):
            enc_blob = r[1]
            dec = cipher_b.decrypt_entry_payload(enc_blob)
            self.assertEqual(dec.get("password"), plain_passwords[idx])
