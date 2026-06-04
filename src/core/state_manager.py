"""Global app state: lock, clipboard timer, inactivity. / Состояние: блокировка, буфер, неактивность."""

import time


class StateManager:
    """Singleton for vault lock and clipboard countdown. / Синглтон блокировки и таймера буфера."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized") and self._initialized:
            return
        self._locked = True
        self._clipboard_timeout_sec = 30
        self._clipboard_seconds_left = 0
        self._clipboard_has_content = False
        self._last_activity_time = time.time()
        self._initialized = True

    def set_locked(self, locked):
        """Set vault locked flag. / Устанавливает флаг блокировки хранилища."""
        self._locked = bool(locked)

    def is_locked(self):
        """Return whether vault is locked. / Хранилище заблокировано."""
        return self._locked

    def set_clipboard_timeout(self, seconds):
        """Set auto-clear delay for clipboard. / Таймаут очистки буфера обмена."""
        self._clipboard_timeout_sec = max(0, int(seconds))

    def reset_clipboard_timer(self):
        """Restart clipboard countdown after copy. / Сбрасывает таймер после копирования."""
        self._clipboard_seconds_left = self._clipboard_timeout_sec
        self._clipboard_has_content = True

    def clear_clipboard_timer(self):
        """Zero clipboard timer after clear. / Обнуляет таймер буфера."""
        self._clipboard_seconds_left = 0
        self._clipboard_has_content = False

    def tick_clipboard_timer(self):
        """Decrement clipboard timer by one second. / Уменьшает таймер на 1 с."""
        if self._clipboard_seconds_left > 0:
            self._clipboard_seconds_left -= 1
        return self._clipboard_seconds_left

    def get_clipboard_seconds_left(self):
        """Seconds until clipboard auto-clear. / Секунд до очистки буфера."""
        return self._clipboard_seconds_left

    def clipboard_has_content(self):
        """Whether staged clipboard secret is active. / В буфере есть секрет."""
        return self._clipboard_has_content

    def touch_activity(self):
        """Record user activity for auto-lock. / Обновляет время активности."""
        self._last_activity_time = time.time()

    def get_inactivity_seconds(self):
        """Seconds since last activity. / Секунд с последней активности."""
        return int(time.time() - self._last_activity_time)

    def get_state(self):
        """Snapshot of lock, clipboard, inactivity. / Снимок состояния для UI."""
        return {
            "locked": self._locked,
            "session": "locked" if self._locked else "unlocked",
            "clipboard_seconds_left": self._clipboard_seconds_left,
            "clipboard_timeout": self._clipboard_timeout_sec,
            "inactivity_seconds": self.get_inactivity_seconds(),
        }


def get_state_manager():
    """Return StateManager singleton. / Единый экземпляр StateManager."""
    return StateManager()
