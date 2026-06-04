"""Fallback activity detector via StateManager. / Резервный детектор активности через StateManager."""

import time

from core.state_manager import get_state_manager


class FallbackActivityDetector:
    """Detect idle time from app state when OS APIs are unavailable."""

    def has_recent_activity(self, threshold_sec: float = 2.0) -> bool:
        """Return True if user was active within threshold_sec. / True, если активность была недавно."""
        sm = get_state_manager()
        return sm.get_inactivity_seconds() < threshold_sec

    def is_screen_locked(self) -> bool:
        """Screen lock detection (not available in fallback). / Блокировка экрана (в fallback недоступна)."""
        return False
