# мониторинг активности и авто-блокировка (спринт 7, ACT-1..4)

import platform
import threading
import time
from typing import Callable, Optional


def _create_detector():
    system = platform.system()
    if system == "Windows":
        try:
            from .platform.windows_activity import WindowsActivityDetector

            return WindowsActivityDetector()
        except Exception:
            pass
    from .platform.fallback_activity import FallbackActivityDetector

    return FallbackActivityDetector()


class ActivityMonitor:
    def __init__(self, lock_callback: Callable[[], None], *, lock_timeout_sec: int = 300, check_interval: float = 1.0):
        self._lock_callback = lock_callback
        self._lock_timeout_sec = max(1, int(lock_timeout_sec))
        self._check_interval = max(0.25, float(check_interval))
        self._detector = _create_detector()
        self._monitoring = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._last_activity = time.time()

    def record_activity(self) -> None:
        with self._lock:
            self._last_activity = time.time()

    def start(self) -> None:
        with self._lock:
            if self._monitoring:
                return
            self._monitoring = True
            self._thread = threading.Thread(target=self._loop, daemon=True, name="activity-monitor")
            self._thread.start()

    def stop(self) -> None:
        with self._lock:
            self._monitoring = False
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

    def get_idle_seconds(self) -> float:
        with self._lock:
            return time.time() - self._last_activity

    def _loop(self) -> None:
        while True:
            with self._lock:
                if not self._monitoring:
                    break
            try:
                if self._detector.has_recent_activity(threshold_sec=self._check_interval * 2):
                    self.record_activity()
                if self._detector.is_screen_locked():
                    self._lock_callback()
                    self.record_activity()
                    time.sleep(self._check_interval)
                    continue
                idle = self.get_idle_seconds()
                if idle >= self._lock_timeout_sec:
                    self._lock_callback()
                    self.record_activity()
            except Exception:
                pass
            time.sleep(self._check_interval)
