# безопасная работа с памятью: зануление, опциональная блокировка страниц (спринт 7, MEM-1/2)

import ctypes
import platform
import sys
from typing import Optional, Union


class SecureMemory:
    def __init__(self) -> None:
        self._system = platform.system()
        self._win = None
        if self._system == "Windows":
            try:
                self._win = ctypes.windll.kernel32
            except Exception:
                self._win = None

    def lock_page(self, buf: ctypes.Array) -> bool:
        if self._win is None:
            return False
        try:
            return bool(self._win.VirtualLock(ctypes.addressof(buf), ctypes.sizeof(buf)))
        except Exception:
            return False

    def unlock_page(self, buf: ctypes.Array) -> None:
        if self._win is None:
            return
        try:
            self._win.VirtualUnlock(ctypes.addressof(buf), ctypes.sizeof(buf))
        except Exception:
            pass

    def secure_zero(self, buf: ctypes.Array) -> None:
        size = ctypes.sizeof(buf)
        if self._win is not None:
            try:
                self._win.RtlSecureZeroMemory(ctypes.addressof(buf), size)
                return
            except Exception:
                pass
        ctypes.memset(ctypes.addressof(buf), 0, size)


def secure_wipe_bytes(data: Union[bytearray, memoryview, bytes]) -> None:
    if data is None:
        return
    if isinstance(data, bytes):
        return
    try:
        mv = memoryview(data)
        mv[:] = b"\x00" * len(mv)
    except TypeError:
        pass
    except Exception:
        pass


def secure_wipe_str(text: str) -> None:
    if not text:
        return
    buf = bytearray(text.encode("utf-8", errors="replace"))
    secure_wipe_bytes(buf)
    del buf


class SecretBuffer:
    """Кратковременное хранение секрета с занулением при выходе из контекста."""

    def __init__(self, data: bytes, *, lock: bool = False) -> None:
        self._mem = SecureMemory()
        self._size = len(data)
        self._buf = (ctypes.c_char * self._size)()
        ctypes.memmove(self._buf, data, self._size)
        if lock:
            self._mem.lock_page(self._buf)

    def get_copy(self) -> bytes:
        return bytes(self._buf)

    def close(self) -> None:
        if hasattr(self, "_buf") and self._buf is not None:
            self._mem.secure_zero(self._buf)
            self._mem.unlock_page(self._buf)
            self._buf = None

    def __enter__(self) -> "SecretBuffer":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass
