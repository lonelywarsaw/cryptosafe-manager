import time
from src.core.events import event_bus, user_logged_in, user_logged_out, clipboard_copied, clipboard_cleared

class StateManager:
    def __init__(self):
        self._session_locked = True
        self._clipboard_content = None
        self._clipboard_timer = None
        self._last_activity = 0.0
        self._inactivity_timeout_seconds = 300.0

    def is_locked(self):
        return self._session_locked

    def set_locked(self, locked):
        self._session_locked = locked
        self._last_activity = time.monotonic() if not locked else 0.0
        if locked:
            event_bus.publish(user_logged_out, {})
        else:
            event_bus.publish(user_logged_in, {})

    def get_clipboard_content(self):
        return self._clipboard_content

    def set_clipboard_content(self, content, timeout_seconds=30):
        self._clipboard_content = content
        self._clipboard_timer = time.monotonic() + timeout_seconds if content else None
        if content is not None:
            event_bus.publish(clipboard_copied, {"timeout_seconds": timeout_seconds})
        else:
            event_bus.publish(clipboard_cleared, {})

    def get_clipboard_timer_remaining(self):
        if self._clipboard_timer is None:
            return None
        remaining = self._clipboard_timer - time.monotonic()
        return max(0.0, remaining) if remaining > 0 else 0.0

    def touch_activity(self):
        self._last_activity = time.monotonic()

    def set_inactivity_timeout_seconds(self, seconds):
        self._inactivity_timeout_seconds = max(0, seconds)

    def is_inactivity_expired(self):
        if self._session_locked:
            return False
        if self._inactivity_timeout_seconds <= 0:
            return False
        return (time.monotonic() - self._last_activity) >= self._inactivity_timeout_seconds
