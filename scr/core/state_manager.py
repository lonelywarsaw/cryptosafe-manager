# Тут храним: залогинен ли юзер, таймер буфера обмена, когда последний раз шевелился.

import time

class StateManager:

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
        self._locked = bool(locked)

    def is_locked(self):
        return self._locked

    def set_clipboard_timeout(self, seconds):
        self._clipboard_timeout_sec = max(0, int(seconds))

    def reset_clipboard_timer(self):
        self._clipboard_seconds_left = self._clipboard_timeout_sec
        self._clipboard_has_content = True

    def tick_clipboard_timer(self):
        if self._clipboard_seconds_left > 0:
            self._clipboard_seconds_left -= 1
        return self._clipboard_seconds_left

    def get_clipboard_seconds_left(self):
        return self._clipboard_seconds_left

    def clipboard_has_content(self):
        return self._clipboard_has_content

    def touch_activity(self):
        self._last_activity_time = time.time()

    def get_inactivity_seconds(self):
        return int(time.time() - self._last_activity_time)

    def get_state(self):
        return {
            "locked": self._locked,
            "session": "locked" if self._locked else "unlocked",
            "clipboard_seconds_left": self._clipboard_seconds_left,
            "clipboard_timeout": self._clipboard_timeout_sec,
            "inactivity_seconds": self.get_inactivity_seconds(),
        }


def get_state_manager():
    return StateManager()
