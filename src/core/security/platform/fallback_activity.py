# резервный детектор: опирается на StateManager.touch_activity (спринт 7, ACT-1)

import time

from core.state_manager import get_state_manager


class FallbackActivityDetector:
    def has_recent_activity(self, threshold_sec: float = 2.0) -> bool:
        sm = get_state_manager()
        return sm.get_inactivity_seconds() < threshold_sec

    def is_screen_locked(self) -> bool:
        return False
