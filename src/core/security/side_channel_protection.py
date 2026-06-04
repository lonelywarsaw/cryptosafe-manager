"""Защита от side-channel: сравнение строк и HMAC в постоянное время."""

import hmac
import secrets
from typing import Union


def constant_time_compare(a: Union[str, bytes], b: Union[str, bytes]) -> bool:
    """Сравнивает a и b через secrets.compare_digest (выравнивание длины)."""
    if isinstance(a, str):
        a = a.encode("utf-8")
    if isinstance(b, str):
        b = b.encode("utf-8")
    if len(a) != len(b):
        # выравниваем длину, чтобы не утекала информация о длине через время сравнения
        return secrets.compare_digest(a, a) and False
    return secrets.compare_digest(a, b)


def constant_time_equal_hex(a_hex: str, b_hex: str) -> bool:
    """Сравнивает hex-строки как байты в постоянное время."""
    try:
        a = bytes.fromhex(a_hex)
        b = bytes.fromhex(b_hex)
    except ValueError:
        return False
    return constant_time_compare(a, b)


def hmac_compare(digest: str, expected: str) -> bool:
    """Сравнивает hex-дайджесты через hmac.compare_digest."""
    return hmac.compare_digest(digest or "", expected or "")
