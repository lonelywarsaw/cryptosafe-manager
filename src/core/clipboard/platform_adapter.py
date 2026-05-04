from abc import ABC, abstractmethod
import platform
import subprocess
from typing import List, Optional

from PyQt6.QtWidgets import QApplication


class ClipboardAdapter(ABC):
    @abstractmethod
    def copy_to_clipboard(self, data: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def clear_clipboard(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def get_clipboard_content(self) -> Optional[str]:
        raise NotImplementedError


class QtClipboardAdapter(ClipboardAdapter):
    # адаптер вокруг QApplication.clipboard
    def _clip(self):
        app = QApplication.instance()
        if not app:
            return None
        return app.clipboard()

    def copy_to_clipboard(self, data: str) -> bool:
        cb = self._clip()
        if not cb:
            return False
        try:
            cb.setText(data or "")
            return True
        except Exception:
            return False

    def clear_clipboard(self) -> bool:
        cb = self._clip()
        if not cb:
            return False
        try:
            cb.clear()
            return True
        except Exception:
            return False

    def get_clipboard_content(self) -> Optional[str]:
        cb = self._clip()
        if not cb:
            return None
        try:
            text = cb.text()
            return text if text is not None else ""
        except Exception:
            return None


class WindowsClipboardAdapter(ClipboardAdapter):
    def __init__(self):
        self._win32clipboard = None
        try:
            import win32clipboard  # type: ignore

            self._win32clipboard = win32clipboard
        except Exception:
            self._win32clipboard = None

    def copy_to_clipboard(self, data: str) -> bool:
        if not self._win32clipboard:
            return False
        try:
            self._win32clipboard.OpenClipboard()
            self._win32clipboard.EmptyClipboard()
            self._win32clipboard.SetClipboardText(data or "", self._win32clipboard.CF_UNICODETEXT)
            self._win32clipboard.CloseClipboard()
            return True
        except Exception:
            try:
                self._win32clipboard.CloseClipboard()
            except Exception:
                pass
            return False

    def clear_clipboard(self) -> bool:
        if not self._win32clipboard:
            return False
        try:
            self._win32clipboard.OpenClipboard()
            self._win32clipboard.EmptyClipboard()
            self._win32clipboard.CloseClipboard()
            return True
        except Exception:
            try:
                self._win32clipboard.CloseClipboard()
            except Exception:
                pass
            return False

    def get_clipboard_content(self) -> Optional[str]:
        if not self._win32clipboard:
            return None
        try:
            self._win32clipboard.OpenClipboard()
            text = self._win32clipboard.GetClipboardData(self._win32clipboard.CF_UNICODETEXT)
            self._win32clipboard.CloseClipboard()
            return text if text is not None else ""
        except Exception:
            try:
                self._win32clipboard.CloseClipboard()
            except Exception:
                pass
            return None


class PyperclipAdapter(ClipboardAdapter):
    def __init__(self):
        self._pyperclip = None
        try:
            import pyperclip  # type: ignore

            self._pyperclip = pyperclip
        except Exception:
            self._pyperclip = None

    def copy_to_clipboard(self, data: str) -> bool:
        if not self._pyperclip:
            return False
        try:
            self._pyperclip.copy(data or "")
            return True
        except Exception:
            return False

    def clear_clipboard(self) -> bool:
        return self.copy_to_clipboard("")

    def get_clipboard_content(self) -> Optional[str]:
        if not self._pyperclip:
            return None
        try:
            return self._pyperclip.paste() or ""
        except Exception:
            return None


class LinuxClipboardAdapter(ClipboardAdapter):
    def __init__(self):
        self._fallback = PyperclipAdapter()

    def _run(self, command: List[str], input_text: Optional[str] = None) -> Optional[str]:
        try:
            proc = subprocess.run(
                command,
                input=input_text,
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
            if proc.returncode != 0:
                return None
            return proc.stdout
        except Exception:
            return None

    def copy_to_clipboard(self, data: str) -> bool:
        value = data or ""
        if self._run(["wl-copy"], input_text=value) is not None:
            return True
        if self._run(["xclip", "-selection", "clipboard"], input_text=value) is not None:
            return True
        if self._run(["xsel", "--clipboard", "--input"], input_text=value) is not None:
            return True
        return self._fallback.copy_to_clipboard(value)

    def clear_clipboard(self) -> bool:
        return self.copy_to_clipboard("")

    def get_clipboard_content(self) -> Optional[str]:
        for cmd in (
            ["wl-paste", "--no-newline"],
            ["xclip", "-selection", "clipboard", "-o"],
            ["xsel", "--clipboard", "--output"],
        ):
            result = self._run(cmd)
            if result is not None:
                return result
        return self._fallback.get_clipboard_content()


def create_platform_adapter() -> ClipboardAdapter:
    system = platform.system().lower()
    if system == "windows":
        adapter = WindowsClipboardAdapter()
        if adapter._win32clipboard is not None:
            return adapter
    if system == "linux":
        return LinuxClipboardAdapter()
    return QtClipboardAdapter()

