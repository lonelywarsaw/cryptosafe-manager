"""POL-1..POL-4: user errors, edge cases, no stack traces in messages."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gui.user_errors import user_facing_error, format_operation_error
from gui import strings


def test_user_facing_error_hides_traceback():
    exc = RuntimeError('Traceback (most recent call last):\n  File "C:\\secret\\app.py", line 1')
    msg = user_facing_error(exc)
    assert "Traceback" not in msg
    assert "app.py" not in msg


def test_user_facing_timeout():
    msg = user_facing_error(TimeoutError())
    assert msg == strings.t("err_timeout")


def test_user_facing_file_not_found():
    msg = user_facing_error(FileNotFoundError(2, "no such file"))
    assert "не найден" in msg.lower() or "not found" in msg.lower()


def test_format_operation_export_context():
    msg = format_operation_error(RuntimeError("internal"), context="export")
    assert msg == strings.t("s6_export_failed_generic")


def test_pol_strings_registered():
    for key in (
        "vault_empty",
        "session_locked_action",
        "wrong_password_attempts",
        "s6_export_failed_generic",
    ):
        assert key in strings.STRINGS["ru"]
        assert key in strings.STRINGS["en"]


def test_unlock_wrong_password_flow(monkeypatch, tmp_path):
    from core.crypto.key_derivation import hash_password_argon2
    from core.crypto.authentication import verify_password, record_login_success, get_failed_attempt_count
    from database import db as database_db
    from core import config

    db_file = tmp_path / "vault.db"
    config.set(config.DB_PATH, str(db_file))
    database_db.set_db_path(str(db_file))
    database_db.init_db()
    database_db.set_key_store("auth_hash", hash_password_argon2("GoodPass123!").encode("utf-8"))
    database_db.set_key_store("enc_salt", b"\x01" * 16)

    assert not verify_password(
        database_db.get_key_store("auth_hash").decode("utf-8"),
        "WrongPass123!",
    )
    record_login_success()
    assert get_failed_attempt_count() == 0
