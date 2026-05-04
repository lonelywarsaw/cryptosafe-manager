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
        self.service.copy_text("Secret_123!", data_type="password", source_entry_id=77)
        self.assertEqual(self.adapter.value, "Secret_123!")
        status = self.service.get_status()
        self.assertTrue(status["active"])
        self.assertEqual(status["data_type"], "password")
        self.assertEqual(status["source_entry_id"], 77)

    def test_manual_clear_clears_clipboard(self):
        self.service.copy_text("value", data_type="text")
        self.service.clear(reason="manual")
        self.assertEqual(self.adapter.value, "")
        self.assertEqual(self.service.get_status(), {"active": False})

    def test_external_change_resets_active_secret(self):
        self.service.copy_text("value", data_type="password")
        self.adapter.value = "changed_by_other_app"
        self.service.clear_if_active_data_replaced()
        self.assertEqual(self.service.get_status(), {"active": False})

    def test_timeout_auto_clear(self):
        self.service.copy_text("x", data_type="password")
        time.sleep(5.3)
        self.assertEqual(self.service.get_status(), {"active": False})
        self.assertEqual(self.adapter.value, "")
