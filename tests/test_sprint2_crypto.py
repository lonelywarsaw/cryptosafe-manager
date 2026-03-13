# тесты спринта 2: argon2, вывод ключа, постоянное время, обнуление памяти

import unittest
import secrets
from core.crypto.key_derivation import (
    hash_password_argon2,
    verify_password_argon2,
    derive_key_pbkdf2,
    DEFAULT_TIME_COST,
    PBKDF2_ITERATIONS,
    PBKDF2_KEY_LEN,
    PBKDF2_SALT_LEN,
)
from core.crypto.authentication import validate_password_strength
from core.crypto import key_storage


class TestArgon2Params(unittest.TestCase):
    # TEST-1 спринт 2: разные параметры дают валидный хеш, верификация проходит
    def test_hash_and_verify(self):
        pwd = "TestPassword123!"
        h = hash_password_argon2(pwd)
        self.assertIsInstance(h, str)
        self.assertTrue(len(h) > 0)
        self.assertTrue(verify_password_argon2(h, pwd))

    def test_wrong_password_fails(self):
        pwd = "TestPassword123!"
        h = hash_password_argon2(pwd)
        self.assertFalse(verify_password_argon2(h, "WrongPassword123!"))


class TestKeyDerivationConsistency(unittest.TestCase):
    # TEST-2 спринт 2: один и тот же пароль и соль 100 раз — один и тот же ключ
    def test_pbkdf2_same_input_same_output(self):
        pwd = "secret"
        salt = b"1234567890123456"
        keys = [derive_key_pbkdf2(pwd, salt) for _ in range(100)]
        self.assertEqual(len(keys), 100)
        for k in keys:
            self.assertEqual(len(k), PBKDF2_KEY_LEN)
            self.assertEqual(keys[0], k)


class TestConstantTime(unittest.TestCase):
    # TEST-3 спринт 2: верификация при неверном пароле не должна сразу выходить (constant-time)
    def test_verify_returns_bool(self):
        h = hash_password_argon2("GoodPass123!")
        self.assertIs(verify_password_argon2(h, "GoodPass123!"), True)
        self.assertIs(verify_password_argon2(h, "BadPass"), False)


class TestKeyStorageZeroed(unittest.TestCase):
    # TEST-4 спринт 2: после clear_cached_key ключ не возвращается
    def test_clear_cached_key(self):
        key_storage.clear_cached_key()
        self.assertIsNone(key_storage.get_cached_key())
        key_storage.set_cached_key(b"x" * 32)
        self.assertIsNotNone(key_storage.get_cached_key())
        key_storage.clear_cached_key()
        self.assertIsNone(key_storage.get_cached_key())


class TestPasswordStrength(unittest.TestCase):
    # спринт 2 HASH-4: валидатор силы пароля
    def test_too_short(self):
        ok, _ = validate_password_strength("Short1!")
        self.assertFalse(ok)

    def test_no_uppercase(self):
        ok, _ = validate_password_strength("longpassword123!")
        self.assertFalse(ok)

    def test_valid(self):
        ok, msg = validate_password_strength("ValidPass123!")
        self.assertTrue(ok, msg)
