# защита от side-channel: сравнение в постоянное время (спринт 7, SC-1)

import hmac
import secrets
from typing import Union


def constant_time_compare(a: Union[str, bytes], b: Union[str, bytes]) -> bool:
    if isinstance(a, str):
        a = a.encode("utf-8")
    if isinstance(b, str):
        b = b.encode("utf-8")
    if len(a) != len(b):
        # выравниваем длину, чтобы не утекала информация о длине через время сравнения
        return secrets.compare_digest(a, a) and False
    return secrets.compare_digest(a, b)


def constant_time_equal_hex(a_hex: str, b_hex: str) -> bool:
    try:
        a = bytes.fromhex(a_hex)
        b = bytes.fromhex(b_hex)
    except ValueError:
        return False
    return constant_time_compare(a, b)


def hmac_compare(digest: str, expected: str) -> bool:
    return hmac.compare_digest(digest or "", expected or "")
