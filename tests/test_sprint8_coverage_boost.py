# Sprint 8 — быстрые тесты для покрытия core/database (TEST-2)

from __future__ import annotations

import os
import tempfile

import pytest

import database.db as db
from core.audit import audit_logger
from core.clipboard.platform_adapter import FakeClipboardAdapter
from core.crypto.authentication import (
    record_login_failure,
    record_login_success,
    validate_password_strength,
)
from core.import_export import key_exchange
from core.key_manager import clear_encryption_key, set_encryption_key


@pytest.fixture
def vault_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db.set_db_path(path)
    db.init_db()
    yield path
    db.set_db_path(None)
    try:
        os.remove(path)
    except OSError:
        pass


def test_fake_clipboard_adapter():
    fb = FakeClipboardAdapter()
    assert fb.copy_to_clipboard("x")
    assert fb.get_clipboard_content() == "x"
    assert fb.clear_clipboard()
    assert fb.get_clipboard_content() is None


def test_key_exchange_roundtrip():
    priv, pub = key_exchange.generate_rsa_keypair()
    data_key = b"0" * 32
    wrapped = key_exchange.wrap_key_for_public(data_key, pub)
    unwrapped = key_exchange.unwrap_key_with_private(wrapped, priv)
    assert unwrapped == data_key


def test_key_exchange_contacts():
    _priv, pub = key_exchange.generate_rsa_keypair()
    key_exchange.add_contact("alice", pub)
    keys = key_exchange.list_contacts()
    assert any(k.get("name") == "alice" for k in keys)


def test_authentication_session():
    ok, _ = validate_password_strength("ValidPass123!")
    assert ok
    record_login_failure()
    record_login_success()


def test_database_audit_and_ie_tables(vault_db):
    set_encryption_key(b"k" * 32)
    try:
        db.insert_audit_log(
            "TestEvent",
            entry_id=1,
            details="ok",
            previous_hash="0" * 64,
            entry_data=b'{"x":1}',
            signature="sig",
            sequence_number=1,
        )
        logs = db.list_audit_logs(limit=5)
        assert logs
        db.insert_shared_entry(
            "share-1",
            1,
            "aes",
            "bob",
            "read",
        )
        shared = db.list_shared_entries(limit=5)
        assert shared
        db.insert_import_export_history(
            "export",
            "json",
            "aes-gcm",
            1,
            128,
            "abc",
            "ok",
        )
        hist = db.list_import_export_history(limit=5)
        assert hist
    finally:
        clear_encryption_key()


def test_audit_logger_register(vault_db):
    audit_logger.register()
    audit_logger._log_event("ClipboardCopied", entry_id=1, details="test")  # noqa: SLF001
    tail = db.get_audit_tail()
    assert tail is not None
