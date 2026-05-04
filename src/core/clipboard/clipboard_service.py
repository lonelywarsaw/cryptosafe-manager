# единая точка работы с буфером обмена


import secrets
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional

from core import events
from core import config
from core.state_manager import get_state_manager
from .platform_adapter import ClipboardAdapter


@dataclass
class SecureClipboardItem:
    # одна запись в "безопасном" буфере
    data: str
    data_type: str
    source_entry_id: Optional[int]
    copied_at: datetime
    mask: bytes
    obfuscated_data: bytes

    def secure_wipe(self):
        # обнуляем строку и маску
        self.data = ""
        self.obfuscated_data = b""
        self.mask = b""


class ClipboardService:
    def __init__(self, platform_adapter: ClipboardAdapter):
        # platform_adapter — абстракция над реальным буфером
        self._platform = platform_adapter
        self._current: Optional[SecureClipboardItem] = None
        self._timer: Optional[threading.Timer] = None
        self._lock = threading.RLock()
        self._observers: List[Callable[[Dict], None]] = []

    @property
    def adapter(self) -> ClipboardAdapter:
        return self._platform

    def subscribe(self, callback: Callable[[Dict], None]):
        # GUI или другие слои могут подписаться на обновление статуса clipboard
        with self._lock:
            self._observers.append(callback)

    def _notify_observers(self):
        status = self.get_status()
        for cb in list(self._observers):
            try:
                cb(status)
            except Exception:
                # не роняем сервис из-за UI
                continue

    def copy_text(self, data: str, data_type: str = "text", source_entry_id: Optional[int] = None):
        # скопировать строку в системный буфер обмена с авто-очисткой
        with self._lock:
            # при новом содержимом старое очищается
            self._clear_internal(reason="replace")

            plain_data = data or ""
            mask = secrets.token_bytes(32)
            obfuscated = self._obfuscate_bytes(plain_data, mask)
            item = SecureClipboardItem(
                data=plain_data,
                data_type=data_type,
                source_entry_id=source_entry_id,
                copied_at=datetime.now(timezone.utc),
                mask=mask,
                obfuscated_data=obfuscated,
            )

            # в системный буфер кладём plaintext, а в памяти держим обфусцированную копию
            ok = self._platform.copy_to_clipboard(plain_data)
            if not ok:
                return

            self._current = item

            # таймер из настроек (config CLIPBOARD_TIMEOUT, диапазон 5–300)
            timeout = int(config.get(config.CLIPBOARD_TIMEOUT, "30") or "30")
            if timeout < 5:
                timeout = 5
            if timeout > 300:
                timeout = 300

            # сохраняем таймаут в state_manager для статус-бара
            sm = get_state_manager()
            sm.set_clipboard_timeout(timeout)
            sm.reset_clipboard_timer()

            # запускаем отдельный таймер авто-очистки
            self._timer = threading.Timer(timeout, self._on_timeout)
            self._timer.daemon = True
            self._timer.start()

            # событие ClipboardCopied
            events.publish(
                events.ClipboardCopied,
                sync=True,
                entry_id=source_entry_id,
                kind=data_type,
            )

            self._notify_observers()

    def clear(self, reason: str = "manual"):
        # явная очистка
        with self._lock:
            self._clear_internal(reason=reason)

    def get_status(self) -> Dict:
        # текущее состояние для UI
        with self._lock:
            if not self._current:
                return {"active": False}

            remaining = self._remaining_time()
            return {
                "active": True,
                "data_type": self._current.data_type,
                "remaining_seconds": max(0, int(remaining)) if remaining is not None else 0,
                "source_entry_id": self._current.source_entry_id,
            }

    def _on_timeout(self):
        # очистка при истечении таймера
        with self._lock:
            self._clear_internal(reason="timeout")

    def _remaining_time(self) -> Optional[float]:
        if not self._current:
            return None
        timeout = int(config.get(config.CLIPBOARD_TIMEOUT, "30") or "30")
        if timeout < 0:
            return None
        delta = datetime.now(timezone.utc) - self._current.copied_at
        remain = timeout - delta.total_seconds()
        return remain

    def clear_if_active_data_replaced(self):
        # если буфер изменился вне приложения — очищаем внутреннее состояние
        with self._lock:
            if not self._current:
                return
            content = self._platform.get_clipboard_content()
            if content is None:
                return
            if content != self._current.data:
                self._clear_internal(reason="external_change")

    def _clear_internal(self, reason: str):
        # останавливаем таймер
        if self._timer:
            try:
                self._timer.cancel()
            except Exception:
                pass
            self._timer = None

        # очищаем системный буфер и память
        if self._current:
            try:
                self._platform.clear_clipboard()
            except Exception:
                pass

            self._current.secure_wipe()
            self._current = None

            # сбрасываем таймер в state_manager
            sm = get_state_manager()
            sm.set_clipboard_timeout(int(config.get(config.CLIPBOARD_TIMEOUT, "30") or "30"))
            # при очистке считаем, что в буфере уже нет секрета
            sm.reset_clipboard_timer()

            # событие ClipboardCleared
            events.publish(
                events.ClipboardCleared,
                sync=True,
                reason=reason,
            )

        self._notify_observers()

    @staticmethod
    def _obfuscate_bytes(data: str, mask: bytes) -> bytes:
        # простая XOR-обфускация в памяти
        raw = (data or "").encode("utf-8")
        if not raw or not mask:
            return b""
        out = bytearray(len(raw))
        for i, b in enumerate(raw):
            out[i] = b ^ mask[i % len(mask)]
        return bytes(out)

