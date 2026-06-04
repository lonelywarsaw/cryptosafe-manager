"""Проверка мастер-пароля, валидация силы и учёт сессии входа."""

import re
from typing import Tuple

from .key_derivation import verify_password_argon2

# требования к мастер-паролю: длина и разнообразие символов
MIN_PASSWORD_LEN = 12
COMMON_PASSWORDS = frozenset(
    [
        "password",
        "password123",
        "123456",
        "12345678",
        "qwerty",
        "qwerty123",
        "admin",
        "letmein",
        "welcome",
        "monkey",
        "dragon",
        "master",
        "login",
    ]
)


def validate_password_strength(password: str) -> Tuple[bool, str]:
    """Проверяет силу мастер-пароля (длина, классы символов, не из списка простых).

    Returns:
        (успех, сообщение об ошибке или пустая строка).
    """
    if not password or len(password) < MIN_PASSWORD_LEN:
        return False, "Пароль не менее 12 символов"
    if password.lower().strip() in COMMON_PASSWORDS:
        return False, "Слишком простой пароль"
    if re.search(r"[a-z]", password) is None:
        return False, "Нужна строчная буква"
    if re.search(r"[A-Z]", password) is None:
        return False, "Нужна заглавная буква"
    if re.search(r"\d", password) is None:
        return False, "Нужна цифра"
    if re.search(r"[!@#$%^&*()_+\-=\[\]{};':\",.<>?/\\|`~]", password) is None:
        return False, "Нужен спецсимвол (!@#$ и т.д.)"
    return True, ""

# данные сессии: время входа, последняя активность, количество неудачных попыток
_login_timestamp = None
_last_activity_timestamp = None
_failed_attempt_count = 0


def verify_password(stored_hash: str, password: str) -> bool:
    """Проверяет пароль против сохранённого Argon2-хеша."""
    return verify_password_argon2(stored_hash, password)


def verify_master_password(password: str) -> bool:
    """Проверяет мастер-пароль по auth_hash из key_store."""
    from database import db as database_db

    auth_blob = database_db.get_key_store("auth_hash")
    if not auth_blob:
        return False
    stored_hash = auth_blob.decode("utf-8")
    return verify_password(stored_hash, password)


def record_login_success():
    """Фиксирует успешный вход: время входа, активность, сброс счётчика ошибок."""
    global _login_timestamp, _last_activity_timestamp, _failed_attempt_count
    import time

    _login_timestamp = time.time()
    _last_activity_timestamp = _login_timestamp
    _failed_attempt_count = 0


def record_login_failure():
    """Увеличивает счётчик неудачных попыток входа."""
    global _failed_attempt_count
    _failed_attempt_count += 1


def get_failed_attempt_count():
    """Возвращает число подряд неудачных попыток (для backoff)."""
    return _failed_attempt_count


def record_activity():
    """Обновляет время последней активности пользователя."""
    global _last_activity_timestamp
    import time

    _last_activity_timestamp = time.time()


def get_login_timestamp():
    """Возвращает время успешного входа (unix) или None."""
    return _login_timestamp


def get_last_activity_timestamp():
    """Возвращает время последней активности (unix) или None."""
    return _last_activity_timestamp

