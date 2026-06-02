# Windows: GetLastInputInfo для авто-блокировки (спринт 7, PLAT-1)

import ctypes
import sys
import time
from typing import Optional

from .fallback_activity import FallbackActivityDetector


class WindowsActivityDetector(FallbackActivityDetector):
    def __init__(self) -> None:
        self._last_input_ms: Optional[int] = None
        if sys.platform == "win32":
            try:
                class LASTINPUTINFO(ctypes.Structure):
                    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

                self._LASTINPUTINFO = LASTINPUTINFO
                self._user32 = ctypes.windll.user32
            except Exception:
                self._user32 = None
        else:
            self._user32 = None

    def has_recent_activity(self, threshold_sec: float = 2.0) -> bool:
        if self._user32 is None:
            return super().has_recent_activity(threshold_sec)
        try:
            lii = self._LASTINPUTINFO()
            lii.cbSize = ctypes.sizeof(self._LASTINPUTINFO)
            if not self._user32.GetLastInputInfo(ctypes.byref(lii)):
                return super().has_recent_activity(threshold_sec)
            tick = ctypes.windll.kernel32.GetTickCount()
            idle_ms = tick - lii.dwTime
            return idle_ms < int(threshold_sec * 1000)
        except Exception:
            return super().has_recent_activity(threshold_sec)
