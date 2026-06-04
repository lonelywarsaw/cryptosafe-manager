"""Режим паники: экстренная блокировка и опциональный stealth."""

import threading
from typing import Callable, List, Optional


class PanicMode:
    """Регистрация обработчиков и однократная активация паники по hotkey."""

    def __init__(self) -> None:
        self._handlers: List[Callable[[], None]] = []
        self._stealth_handlers: List[Callable[[], None]] = []
        self._lock = threading.Lock()
        self._activated = False
        self._stealth_enabled = False

    def register_handler(self, handler: Callable[[], None]) -> None:
        """Добавляет обработчик основной паники (блокировка, очистка)."""
        self._handlers.append(handler)

    def register_stealth_handler(self, handler: Callable[[], None]) -> None:
        """Добавляет обработчик stealth (скрытие UI и т.п.)."""
        self._stealth_handlers.append(handler)

    def set_stealth_enabled(self, enabled: bool) -> None:
        """Включает вызов stealth-обработчиков при activate."""
        self._stealth_enabled = bool(enabled)

    def activate(self, method: str = "hotkey") -> None:
        """Выполняет зарегистрированные обработчики и публикует PanicModeActivated."""
        with self._lock:
            if self._activated:
                return
            self._activated = True
        for handler in list(self._handlers):
            try:
                handler()
            except Exception:
                pass
        if self._stealth_enabled:
            for handler in list(self._stealth_handlers):
                try:
                    handler()
                except Exception:
                    pass
        try:
            from core import events

            events.publish(events.PanicModeActivated, sync=True, method=method)
        except Exception:
            pass
        with self._lock:
            self._activated = False

    def reset(self) -> None:
        """Сбрасывает флаг активации (для тестов)."""
        with self._lock:
            self._activated = False


_panic_instance: Optional[PanicMode] = None


def get_panic_mode() -> PanicMode:
    """Возвращает синглтон PanicMode."""
    global _panic_instance
    if _panic_instance is None:
        _panic_instance = PanicMode()
    return _panic_instance
