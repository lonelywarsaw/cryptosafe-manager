"""Краткоживущий буфер секретов: bytearray и затирание после использования."""

import hashlib
from typing import Optional


def digest_text(value: str) -> str:
    """SHA256 hex от текста (для сравнения без хранения plaintext)."""
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()


def text_to_secure(data: str) -> bytearray:
    """Кодирует строку в изменяемый bytearray."""
    raw = bytearray((data or "").encode("utf-8"))
    return raw


def secure_to_text(buf: bytearray) -> str:
    """Декодирует bytearray в str и затирает buf."""
    try:
        return buf.decode("utf-8")
    finally:
        wipe_bytearray(buf)


def wipe_bytearray(buf: Optional[bytearray]) -> None:
    """Обнуляет байты и очищает bytearray."""
    if not buf:
        return
    for i in range(len(buf)):
        buf[i] = 0
    buf.clear()
