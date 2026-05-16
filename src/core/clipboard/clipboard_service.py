# единая точка работы с буфером обмена; таймер только в StateManager

import secrets
import threading
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from core import events
from core import config
from core.state_manager import get_state_manager
from .platform_adapter import ClipboardAdapter
from .secure_buffer import digest_text, wipe_bytearray


@dataclass
class _ActiveClip:
    data_type: str
    source_entry_id: Optional[int]
    content_digest: str
    mask: bytes = field(default_factory=bytes)
    obfuscated: bytes = field(default_factory=bytes)

    def secure_wipe(self):
        self.content_digest = ""
        if self.mask:
            m = bytearray(self.mask)
            wipe_bytearray(m)
        self.mask = b""
        self.obfuscated = b""


class ClipboardService:
    def __init__(self, platform_adapter: ClipboardAdapter):
        self._platform = platform_adapter
        self._current: Optional[_ActiveClip] = None
        self._lock = threading.RLock()
        self._observers: List[Callable[[Dict], None]] = []

    @property
    def adapter(self) -> ClipboardAdapter:
        return self._platform

    def subscribe(self, callback: Callable[[Dict], None]):
        with self._lock:
            self._observers.append(callback)

    def _notify_observers(self):
        status = self.get_status()
        for cb in list(self._observers):
            try:
                cb(status)
            except Exception:
                continue

    def copy_text(self, data: str, data_type: str = "text", source_entry_id: Optional[int] = None):
        with self._lock:
            self._clear_internal(reason="replace", publish=False)
            plain_data = data or ""
            mask = secrets.token_bytes(32)
            item = _ActiveClip(
                data_type=data_type,
                source_entry_id=source_entry_id,
                content_digest=digest_text(plain_data),
                mask=mask,
                obfuscated=self._obfuscate_bytes(plain_data, mask),
            )
            ok = self._platform.copy_to_clipboard(plain_data)
            if not ok:
                item.secure_wipe()
                return
            self._current = item
            sm = get_state_manager()
            sm.set_clipboard_timeout(self._clip_timeout())
            sm.reset_clipboard_timer()
            events.publish(
                events.ClipboardCopied,
                sync=True,
                entry_id=source_entry_id,
                kind=data_type,
            )
            self._notify_observers()

    def clear(self, reason: str = "manual"):
        with self._lock:
            self._clear_internal(reason=reason)

    def get_status(self) -> Dict:
        with self._lock:
            if not self._current:
                return {"active": False, "staged": False}
            sm = get_state_manager()
            left = sm.get_clipboard_seconds_left()
            return {
                "active": True,
                "staged": False,
                "data_type": self._current.data_type,
                "remaining_seconds": left,
                "source_entry_id": self._current.source_entry_id,
            }

    def clear_if_active_data_replaced(self):
        with self._lock:
            if not self._current:
                return
            content = self._platform.get_clipboard_content()
            if content is None:
                return
            if digest_text(content) != self._current.content_digest:
                self._clear_internal(reason="external_change")

    def _clear_internal(self, reason: str, publish: bool = True):
        had_secret = self._current is not None

        if self._current:
            self._current.secure_wipe()
            self._current = None

        if had_secret or reason in ("manual", "timer_tick", "vault_lock", "app_close", "external_change"):
            try:
                self._platform.clear_clipboard()
            except Exception:
                pass
            sm = get_state_manager()
            sm.clear_clipboard_timer()
            if publish and had_secret:
                events.publish(events.ClipboardCleared, sync=True, reason=reason)

        self._notify_observers()

    @staticmethod
    def _clip_timeout() -> int:
        timeout = int(config.get(config.CLIPBOARD_TIMEOUT, "30") or "30")
        if timeout < 5:
            timeout = 5
        if timeout > 300:
            timeout = 300
        return timeout

    @staticmethod
    def _obfuscate_bytes(data: str, mask: bytes) -> bytes:
        raw = (data or "").encode("utf-8")
        if not raw or not mask:
            return b""
        out = bytearray(len(raw))
        for i, b in enumerate(raw):
            out[i] = b ^ mask[i % len(mask)]
        return bytes(out)
