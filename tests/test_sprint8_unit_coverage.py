# Sprint 8 — доп. быстрые тесты для покрытия core/database (TEST-2)

from __future__ import annotations

import os
import tempfile

import pytest

from core import config, events
from core.audit import log_formatters, log_verifier
from core.clipboard.clipboard_monitor import ClipboardMonitor
from core.clipboard.platform_adapter import ClipboardAdapter, create_platform_adapter
from core.clipboard.secure_buffer import digest_text, secure_to_text, text_to_secure, wipe_bytearray
from core.security.activity_monitor import ActivityMonitor
from core.security.memory_guard import SecretBuffer, secure_wipe_bytes
from core.security.panic_mode import get_panic_mode
from core.security.security_profiles import PROFILE_STANDARD, apply_profile
from core.security.side_channel_protection import constant_time_compare
from core.state_manager import get_state_manager
from core.key_manager import clear_encryption_key, set_encryption_key


class _Clip(ClipboardAdapter):
    def __init__(self) -> None:
        self._v: str | None = None

    def copy_to_clipboard(self, data: str) -> bool:
        self._v = data
        return True

    def clear_clipboard(self) -> bool:
        self._v = None
        return True

    def get_clipboard_content(self) -> str | None:
        return self._v


def test_log_formatters():
    rows = [{"event": "Login", "n": 1}]
    js = log_formatters.format_json_lines(rows)
    assert "Login" in js
    csv_out = log_formatters.format_csv(rows, ["event", "n"])
    assert "event" in csv_out


def test_state_manager_clipboard_timer():
    sm = get_state_manager()
    sm.set_clipboard_timeout(30)
    sm.reset_clipboard_timer()
    assert sm.get_clipboard_seconds_left() == 30
    sm.tick_clipboard_timer()
    assert sm.get_clipboard_seconds_left() == 29
    sm.clear_clipboard_timer()


def test_secure_buffer_roundtrip():
    buf = text_to_secure("secret")
    assert secure_to_text(buf) == "secret"
    wipe = bytearray(b"xy")
    wipe_bytearray(wipe)
    assert digest_text("a") != digest_text("b")


def test_clipboard_monitor_lifecycle():
    adapter = _Clip()
    mon = ClipboardMonitor(adapter)
    mon.set_on_change(lambda _v: None)
    mon.stop()


def test_platform_adapter_factory():
    adapter = create_platform_adapter()
    assert hasattr(adapter, "copy_to_clipboard")


def test_config_roundtrip():
    old = config.get(config.LANGUAGE)
    try:
        config.set(config.LANGUAGE, "en")
        assert config.get(config.LANGUAGE) == "en"
    finally:
        if old is not None:
            config.set(config.LANGUAGE, old)


def test_events_publish():
    received: list = []

    def cb(**kw):
        received.append(kw)

    events.subscribe(events.ClipboardCleared, cb)
    events.publish(events.ClipboardCleared, sync=True, reason="test")
    assert received and received[0].get("reason") == "test"


def test_security_modules_smoke():
    assert constant_time_compare(b"ab", b"ab")
    assert not constant_time_compare(b"ab", b"cd")
    pm = get_panic_mode()
    pm.reset()
    called = []

    def h():
        called.append(1)

    pm.register_handler(h)
    pm.activate()
    assert called
    apply_profile(PROFILE_STANDARD)
    assert config.get(config.SECURITY_PROFILE) == PROFILE_STANDARD
    with SecretBuffer(b"secret-bytes") as sb:
        assert sb.get_copy() == b"secret-bytes"
    buf = bytearray(b"wipe-me")
    secure_wipe_bytes(buf)
    mon = ActivityMonitor(lambda: None, lock_timeout_sec=3600)
    mon.record_activity()
    mon.stop()


def test_key_manager_cache():
    clear_encryption_key()
    set_encryption_key(b"x" * 32)
    from core.key_manager import get_encryption_key

    assert get_encryption_key() == b"x" * 32
    clear_encryption_key()


def test_log_verifier_empty_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    import database.db as db

    db.set_db_path(path)
    db.init_db()
    try:
        result = log_verifier.verify_audit_chain([], None)
        assert result["verified"] is True
    finally:
        db.set_db_path(None)
        try:
            os.remove(path)
        except OSError:
            pass
