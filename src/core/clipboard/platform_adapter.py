from abc import ABC, abstractmethod
import platform
import subprocess
from typing import Optional


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
    def _clip(self):
        try:
            from PyQt6.QtWidgets import QApplication
        except ImportError:
            return None
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
            cb.setText("")
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
    # Windows: win32clipboard + синхронизация с Qt (один адаптер для спринта 4)
    def __init__(self):
        self._win32clipboard = None
        self._qt = QtClipboardAdapter()
        try:
            import win32clipboard  # type: ignore

            self._win32clipboard = win32clipboard
        except Exception:
            self._win32clipboard = None

    def _win32_copy(self, data: str) -> bool:
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

    def _win32_clear(self) -> bool:
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

    def _powershell_clear(self) -> bool:
        try:
            proc = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "Set-Clipboard -Value $null",
                ],
                capture_output=True,
                timeout=3,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            return proc.returncode == 0
        except Exception:
            return False

    def copy_to_clipboard(self, data: str) -> bool:
        ok = self._win32_copy(data)
        self._qt.copy_to_clipboard(data)
        return ok or self._qt.copy_to_clipboard(data)

    def clear_clipboard(self) -> bool:
        ok = self._win32_clear()
        self._powershell_clear()
        return self._qt.clear_clipboard() or ok

    def get_clipboard_content(self) -> Optional[str]:
        if self._win32clipboard:
            try:
                self._win32clipboard.OpenClipboard()
                text = self._win32clipboard.GetClipboardData(self._win32clipboard.CF_UNICODETEXT)
                self._win32clipboard.CloseClipboard()
                if text is not None:
                    return text
            except Exception:
                try:
                    self._win32clipboard.CloseClipboard()
                except Exception:
                    pass
        return self._qt.get_clipboard_content()


def create_platform_adapter() -> ClipboardAdapter:
    if platform.system().lower() == "windows":
        adapter = WindowsClipboardAdapter()
        if adapter._win32clipboard is not None:
            return adapter
    return QtClipboardAdapter()
