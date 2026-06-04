"""Адаптеры буфера обмена: Qt, Windows win32, фабрика create_platform_adapter."""

from abc import ABC, abstractmethod
import platform
import subprocess
from typing import Optional


class ClipboardAdapter(ABC):
    """Абстрактный доступ к системному буферу обмена."""

    @abstractmethod
    def copy_to_clipboard(self, data: str) -> bool:
        """Копирует текст в буфер; True при успехе."""
        raise NotImplementedError

    @abstractmethod
    def clear_clipboard(self) -> bool:
        """Очищает буфер; True при успехе."""
        raise NotImplementedError

    @abstractmethod
    def get_clipboard_content(self) -> Optional[str]:
        """Возвращает текст из буфера или None при ошибке."""
        raise NotImplementedError


def _ensure_windows_com() -> None:
    if platform.system().lower() != "windows":
        return
    try:
        import pythoncom  # type: ignore

        pythoncom.CoInitialize()
    except Exception:
        pass


_gui_bridge = None


def _get_gui_bridge():
    global _gui_bridge
    if _gui_bridge is not None:
        return _gui_bridge
    try:
        from PyQt6.QtCore import QObject, pyqtSlot, QMetaObject, Qt, QThread
        from PyQt6.QtWidgets import QApplication
    except ImportError:
        return None

    class _GuiBridge(QObject):
        @pyqtSlot(object, object)
        def _run(self, fn, out):
            _ensure_windows_com()
            try:
                out["v"] = fn()
            except Exception:
                out["v"] = None

    app = QApplication.instance()
    if not app:
        return None
    _gui_bridge = _GuiBridge()
    _gui_bridge.moveToThread(app.thread())
    return _gui_bridge


def _run_on_gui_thread(fn):
    try:
        from PyQt6.QtCore import QThread, QMetaObject, Qt
        from PyQt6.QtWidgets import QApplication
    except ImportError:
        return fn()

    app = QApplication.instance()
    if not app or QThread.currentThread() is app.thread():
        _ensure_windows_com()
        return fn()

    bridge = _get_gui_bridge()
    if bridge is None:
        return fn()

    out = {"v": None}
    QMetaObject.invokeMethod(
        bridge,
        "_run",
        Qt.ConnectionType.BlockingQueuedConnection,
        fn,
        out,
    )
    return out["v"]


class QtClipboardAdapter(ClipboardAdapter):
    """Буфер обмена через QApplication.clipboard (вызовы на GUI-потоке)."""

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
        def _do() -> bool:
            cb = self._clip()
            if not cb:
                return False
            try:
                cb.setText(data or "")
                return True
            except Exception:
                return False

        return _run_on_gui_thread(_do)

    def clear_clipboard(self) -> bool:
        def _do() -> bool:
            cb = self._clip()
            if not cb:
                return False
            try:
                cb.clear()
                return True
            except Exception:
                return False

        return _run_on_gui_thread(_do)

    def get_clipboard_content(self) -> Optional[str]:
        def _do() -> Optional[str]:
            cb = self._clip()
            if not cb:
                return None
            try:
                text = cb.text()
                return text if text is not None else ""
            except Exception:
                return None

        return _run_on_gui_thread(_do)


class WindowsClipboardAdapter(ClipboardAdapter):
    """Windows: win32clipboard с fallback на Qt и PowerShell для clear."""

    def __init__(self):
        self._win32clipboard = None
        self._qt_fallback = QtClipboardAdapter()
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
        if self._win32_copy(data):
            return True
        return self._qt_fallback.copy_to_clipboard(data)

    def clear_clipboard(self) -> bool:
        ok = self._win32_clear()
        if not ok:
            ok = self._powershell_clear()
        if ok:
            return True
        return self._qt_fallback.clear_clipboard()

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
        return self._qt_fallback.get_clipboard_content()


def create_platform_adapter() -> ClipboardAdapter:
    """Возвращает WindowsClipboardAdapter или QtClipboardAdapter по ОС."""
    if platform.system().lower() == "windows":
        adapter = WindowsClipboardAdapter()
        if adapter._win32clipboard is not None:
            return adapter
    return QtClipboardAdapter()

class FakeClipboardAdapter(ClipboardAdapter):

    def __init__(self):
        self.clear_called = False
        self.last_copied = None
        self._content = None

    def copy_to_clipboard(self, data: str) -> bool:
        self.last_copied = data
        self._content = data
        return True

    def clear_clipboard(self) -> bool:
        self.clear_called = True
        self._content = None
        return True

    def get_clipboard_content(self) -> Optional[str]:
        return self._content