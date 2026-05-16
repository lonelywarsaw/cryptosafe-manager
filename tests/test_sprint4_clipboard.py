import time
import unittest

from core import config
from core.clipboard.clipboard_service import ClipboardService


class _FakeAdapter:
    def __init__(self):
        self.value = ""

    def copy_to_clipboard(self, data: str) -> bool:
        self.value = data or ""
        return True

    def clear_clipboard(self) -> bool:
        self.value = ""
        return True

    def get_clipboard_content(self):
        return self.value


class TestSprint4Clipboard(unittest.TestCase):
    def setUp(self):
        self._old_timeout = config.get(config.CLIPBOARD_TIMEOUT, "30")
        config.set(config.CLIPBOARD_TIMEOUT, "5")
        self.adapter = _FakeAdapter()
        self.service = ClipboardService(self.adapter)

    def tearDown(self):
        self.service.clear(reason="teardown")
        config.set(config.CLIPBOARD_TIMEOUT, self._old_timeout)

    def test_copy_keeps_plain_text_in_system_clipboard(self):
        self.service.copy_text("Secret_123!", data_type="text", source_entry_id=77)
        self.assertEqual(self.adapter.value, "Secret_123!")

    def test_manual_clear_clears_clipboard(self):
        self.service.copy_text("value", data_type="text")
        self.service.clear(reason="manual")
        self.assertEqual(self.adapter.value, "")
        self.assertFalse(self.service.get_status().get("active"))

    def test_external_change_resets_active_secret(self):
        self.service.copy_text("value", data_type="password")
        self.adapter.value = "changed_by_other_app"
        self.service.clear_if_active_data_replaced()
        self.assertFalse(self.service.get_status().get("active"))

    def test_timeout_auto_clear(self):
        from core.state_manager import get_state_manager

        self.service.copy_text("x", data_type="text")
        sm = get_state_manager()
        while sm.get_clipboard_seconds_left() > 0:
            sm.tick_clipboard_timer()
        self.service.clear(reason="timer_tick")
        self.assertFalse(self.service.get_status().get("active"))
        self.assertEqual(self.adapter.value, "")
