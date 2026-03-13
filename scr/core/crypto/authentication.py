# проверка мастер-пароля через Argon2, валидатор силы пароля и учёт сессии входа (спринт 2)

import re
from typing import Tuple

from .key_derivation import verify_password_argon2

# требования к мастер-паролю: длина и разнообразие символов (HASH-4, спринт 2)
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
    # проверка силы пароля: не короче 12 символов, есть все типы символов, не из популярных (спринт 2)
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

# данные сессии: время входа, последняя активность, количество неудачных попыток (AUTH-4, спринт 2)
_login_timestamp = None
_last_activity_timestamp = None
_failed_attempt_count = 0


def verify_password(stored_hash: str, password: str) -> bool:
    # проверка пароля через Argon2; сравнение делается библиотекой в постоянное время (спринт 2)
    return verify_password_argon2(stored_hash, password)


def record_login_success():
    # после успешного входа запоминается время входа, активность и обнуляется счётчик ошибок (спринт 2)
    global _login_timestamp, _last_activity_timestamp, _failed_attempt_count
    import time

    _login_timestamp = time.time()
    _last_activity_timestamp = _login_timestamp
    _failed_attempt_count = 0


def record_login_failure():
    # при каждом неверном вводе увеличивается счётчик неудачных попыток (AUTH-3, спринт 2)
    global _failed_attempt_count
    _failed_attempt_count += 1


def get_failed_attempt_count():
    # сколько подряд было неудачных попыток входа (для backoff) (спринт 2)
    return _failed_attempt_count


def record_activity():
    # любое действие пользователя обновляет время последней активности (AUTH-4, спринт 2)
    global _last_activity_timestamp
    import time

    _last_activity_timestamp = time.time()


def get_login_timestamp():
    # время успешного входа (спринт 2)
    return _login_timestamp


def get_last_activity_timestamp():
    # время последнего действия (спринт 2)
    return _last_activity_timestamp

