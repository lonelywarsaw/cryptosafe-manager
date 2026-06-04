from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from core.clipboard import clipboard_policy
from core.clipboard.clipboard_service import ClipboardService
from core.clipboard.platform_adapter import ClipboardAdapter


class _MemAdapter(ClipboardAdapter):
    def __init__(self):
        self._content: str | None = None

    def copy_to_clipboard(self, data: str) -> bool:
        self._content = data
        return True

    def clear_clipboard(self) -> bool:
        self._content = None
        return True

    def get_clipboard_content(self) -> str | None:
        return self._content


class TestClipboardPolicy(unittest.TestCase):
    def test_parse_whitelist(self):
        wl = clipboard_policy.parse_whitelist(" Chrome.EXE , firefox;notepad ")
        self.assertIn("chrome.exe", wl)
        self.assertIn("firefox", wl)
        self.assertIn("notepad", wl)

    def test_process_in_whitelist_stem(self):
        wl = clipboard_policy.parse_whitelist("chrome.exe")
        self.assertTrue(clipboard_policy.process_in_whitelist("Chrome.exe", wl))
        self.assertTrue(clipboard_policy.process_in_whitelist("chrome", wl))

    def test_monitors_external_by_level(self):
        self.assertFalse(clipboard_policy.monitors_external_clipboard("basic"))
        self.assertTrue(clipboard_policy.monitors_external_clipboard("advanced"))
        self.assertTrue(clipboard_policy.monitors_external_clipboard("paranoid"))

    def test_effective_timeout_paranoid(self):
        self.assertEqual(clipboard_policy.effective_clipboard_timeout(30, "paranoid"), 21)
        self.assertEqual(clipboard_policy.effective_clipboard_timeout(30, "basic"), 30)

    def test_should_clear_rules(self):
        wl = frozenset({"chrome.exe"})
        self.assertFalse(
            clipboard_policy.should_clear_on_external_change(
                level="basic", digest_matches=False, clipboard_empty=False
            )
        )
        self.assertTrue(
            clipboard_policy.should_clear_on_external_change(
                level="paranoid", digest_matches=False, clipboard_empty=False
            )
        )
        self.assertFalse(
            clipboard_policy.should_clear_on_external_change(
                level="advanced",
                digest_matches=False,
                clipboard_empty=False,
                foreground_process="chrome.exe",
                whitelist=wl,
            )
        )
        self.assertTrue(
            clipboard_policy.should_clear_on_external_change(
                level="advanced",
                digest_matches=False,
                clipboard_empty=False,
                foreground_process="malware.exe",
                whitelist=wl,
            )
        )
        self.assertTrue(
            clipboard_policy.should_clear_on_external_change(
                level="paranoid", digest_matches=False, clipboard_empty=True
            )
        )


class TestClipboardServicePolicyIntegration(unittest.TestCase):
    @patch("core.clipboard.clipboard_service.get_state_manager")
    @patch("core.clipboard.clipboard_service.clipboard_policy.get_security_level", return_value="basic")
    def test_basic_ignores_external_change(self, _level, mock_sm):
        mock_sm.return_value = MagicMock()
        adapter = _MemAdapter()
        service = ClipboardService(adapter)
        service.copy_text("secret", data_type="password")
        adapter._content = "tampered"
        service.clear_if_active_data_replaced()
        self.assertEqual(adapter.get_clipboard_content(), "tampered")

    @patch("core.clipboard.clipboard_service.get_state_manager")
    @patch("core.clipboard.clipboard_service.clipboard_policy.get_security_level", return_value="advanced")
    @patch(
        "core.clipboard.clipboard_service.get_foreground_process_name",
        return_value="chrome.exe",
    )
    @patch(
        "core.clipboard.clipboard_service.clipboard_policy.parse_whitelist",
        return_value=frozenset({"chrome.exe"}),
    )
    def test_advanced_whitelist_skips_clear(self, _wl, _fg, _level, mock_sm):
        mock_sm.return_value = MagicMock()
        adapter = _MemAdapter()
        service = ClipboardService(adapter)
        service.copy_text("secret", data_type="password")
        adapter._content = "other"
        service.clear_if_active_data_replaced()
        self.assertEqual(adapter.get_clipboard_content(), "other")

    @patch("core.clipboard.clipboard_service.get_state_manager")
    @patch("core.clipboard.clipboard_service.clipboard_policy.get_security_level", return_value="paranoid")
    def test_paranoid_clears_on_external_change(self, _level, mock_sm):
        mock_sm.return_value = MagicMock()
        adapter = _MemAdapter()
        service = ClipboardService(adapter)
        service.copy_text("secret", data_type="password")
        adapter._content = "other"
        service.clear_if_active_data_replaced()
        self.assertIsNone(adapter.get_clipboard_content())

    @patch("core.clipboard.clipboard_service.get_state_manager")
    @patch("core.clipboard.clipboard_service.clipboard_policy.get_security_level", return_value="paranoid")
    def test_paranoid_timeout_factor_on_copy(self, _level, mock_sm):
        sm = MagicMock()
        mock_sm.return_value = sm
        with patch("core.clipboard.clipboard_service.config.get", return_value="30"):
            service = ClipboardService(_MemAdapter())
            service.copy_text("x")
        sm.set_clipboard_timeout.assert_called_once_with(21)


if __name__ == "__main__":
    unittest.main()
