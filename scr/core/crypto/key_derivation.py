# вывод ключей и хеша пароля: Argon2id для проверки пароля и PBKDF2-HMAC-SHA256 для ключа шифрования (спринт 2)

import hashlib
import secrets
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

# безопасные дефолты для Argon2id; при желании параметры можно задать через config
DEFAULT_TIME_COST = 3
DEFAULT_MEMORY_MIB = 64
DEFAULT_PARALLELISM = 4
DEFAULT_HASH_LEN = 32

# параметры PBKDF2 для ключа шифрования (AES-256)
PBKDF2_ITERATIONS = 100_000
PBKDF2_KEY_LEN = 32
PBKDF2_SALT_LEN = 16


def _get_hasher(time_cost=None, memory_cost=None, parallelism=None, hash_len=None):
    # создаётся объект Argon2id с заданными параметрами: либо из config, либо дефолты
    from core import config

    time_cost = time_cost or int(config.get("argon2_time_cost", DEFAULT_TIME_COST))
    memory_cost = memory_cost or int(config.get("argon2_memory_mib", DEFAULT_MEMORY_MIB)) * 1024
    parallelism = parallelism or int(config.get("argon2_parallelism", DEFAULT_PARALLELISM))
    hash_len = hash_len or int(config.get("argon2_hash_len", DEFAULT_HASH_LEN))
    return PasswordHasher(
        time_cost=time_cost,
        memory_cost=memory_cost,
        parallelism=parallelism,
        hash_len=hash_len,
    )


def hash_password_argon2(password: str) -> str:
    # пароль хешируется Argon2id; строка содержит соль и параметры, её сохраняем в config
    hasher = _get_hasher()
    return hasher.hash(password)


def verify_password_argon2(stored_hash: str, password: str) -> bool:
    # проверка пароля против сохранённого Argon2-хеша; при ошибке — фиктивное сравнение чтобы не светить тайминг
    if not stored_hash or not password:
        secrets.compare_digest(b"x", b"x")
        return False
    try:
        hasher = _get_hasher()
        hasher.verify(stored_hash, password)
        return True
    except VerifyMismatchError:
        secrets.compare_digest(b"x", b"x")
        return False


def derive_key_pbkdf2(password: str, salt: bytes, iterations: int = None) -> bytes:
    # из пароля и соли выводится ключ 32 байта (AES-256) через PBKDF2-HMAC-SHA256
    from core import config

    iter_count = iterations or int(config.get("pbkdf2_iterations", PBKDF2_ITERATIONS))
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iter_count,
        dklen=PBKDF2_KEY_LEN,
    )
    return key

