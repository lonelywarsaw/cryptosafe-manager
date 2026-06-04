"""Кэш ключа шифрования в памяти на время разблокированного хранилища."""

import ctypes

# ключ хранится только пока хранилище разблокировано; снаружи доступ через get/set/clear
_cached_key = None


def _zero_key(buf):
    # обнуление байтов в памяти, чтобы ключ не остался в ram после очистки
    if buf is None or len(buf) == 0:
        return
    if isinstance(buf, bytearray):
        arr = (ctypes.c_char * len(buf)).from_buffer(buf)
        ctypes.memset(ctypes.addressof(arr), 0, len(buf))
    elif isinstance(buf, bytes):
        # bytes неизменяемы — копируем в bytearray и обнуляем
        mutable = bytearray(buf)
        arr = (ctypes.c_char * len(mutable)).from_buffer(mutable)
        ctypes.memset(ctypes.addressof(arr), 0, len(mutable))


def set_cached_key(key: bytes):
    """Сохраняет копию ключа в кэше до clear_cached_key."""
    global _cached_key
    _cached_key = bytes(key) if key else None


def get_cached_key():
    """Возвращает ключ из кэша или None; сбрасывает после часа неактивности."""
    try:
        from core.state_manager import get_state_manager
        sm = get_state_manager()
        if sm.get_inactivity_seconds() >= 3600:
            clear_cached_key()
            return None
    except Exception:
        pass
    return _cached_key


def clear_cached_key():
    """Удаляет ключ из кэша и обнуляет буфер в памяти."""
    global _cached_key
    if _cached_key is not None:
        mutable = bytearray(_cached_key)
        _zero_key(mutable)
        _cached_key = None

