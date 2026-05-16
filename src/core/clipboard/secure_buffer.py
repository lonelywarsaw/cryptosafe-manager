# краткоживущий буфер для секретов: plaintext только в bytearray, затем затирание

import hashlib
from typing import Optional


def digest_text(value: str) -> str:
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()


def text_to_secure(data: str) -> bytearray:
    raw = bytearray((data or "").encode("utf-8"))
    return raw


def secure_to_text(buf: bytearray) -> str:
    try:
        return buf.decode("utf-8")
    finally:
        wipe_bytearray(buf)


def wipe_bytearray(buf: Optional[bytearray]) -> None:
    if not buf:
        return
    for i in range(len(buf)):
        buf[i] = 0
    buf.clear()
