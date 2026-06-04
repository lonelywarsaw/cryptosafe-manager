"""Монитор буфера обмена: поллинг изменений через ClipboardAdapter."""

import threading
import time
from typing import Callable, Optional

from .platform_adapter import ClipboardAdapter


class ClipboardMonitor:
    """Фоновый поллинг буфера обмена и callback при смене текста."""

    def __init__(self, adapter: ClipboardAdapter):
        """Args:
            adapter: Платформенный адаптер чтения/записи буфера.
        """
        self._adapter = adapter
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_value: Optional[str] = None
        self._on_change: Optional[Callable[[str], None]] = None

    def set_on_change(self, callback: Callable[[str], None]):
        """Регистрирует callback при изменении текста в буфере."""
        self._on_change = callback

    def start(self):
        """Запускает daemon-поток поллинга (~0.5 с)."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Останавливает поллинг (флаг _running)."""
        self._running = False

    def _loop(self):
        # простейший поллинг раз в 0.5с; полноценная защита — в следующих шагах спринта
        while self._running:
            try:
                value = self._adapter.get_clipboard_content()
                if value != self._last_value:
                    self._last_value = value
                    if self._on_change is not None:
                        try:
                            self._on_change(value or "")
                        except Exception:
                            pass
            except Exception:
                pass
            time.sleep(0.5)

