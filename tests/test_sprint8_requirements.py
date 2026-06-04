# Sprint 8 — TEST-1: обязательные области (crypto, vault, clipboard, import/export)

from __future__ import annotations

import os
import sqlite3
import tempfile
import time

import pytest

import database.db as db
from core.clipboard.clipboard_service import ClipboardService
from core.clipboard.platform_adapter import ClipboardAdapter
from core.crypto.authentication import validate_password_strength
from core.crypto.key_derivation import derive_key_pbkdf2, hash_password_argon2, verify_password_argon2
from core.import_export.exporter import ExportOptions, VaultExporter
from core.import_export.importer import VaultImporter
from core.import_export.key_exchange import generate_rsa_keypair, normalize_pem_block, optional_public_key_pem
from core.input_validation import sanitize_notes, sanitize_text, validate_title
from core.vault.encryption_service import EncryptionServiceAESGCM
from core.vault.entry_manager import EntryManager
from core.key_manager import set_encryption_key

try:
    import cryptography  # noqa: F401

    _HAS_CRYPTO = True
except Exception:
    _HAS_CRYPTO = False


class _MemAdapter(ClipboardAdapter):
    def __init__(self) -> None:
        self._content: str | None = None

    def copy_to_clipboard(self, data: str) -> bool:
        self._content = data
        return True

    def clear_clipboard(self) -> bool:
        self._content = None
        return True

    def get_clipboard_content(self) -> str | None:
        return self._content


class _FakeKeyManager:
    def __init__(self, key: bytes) -> None:
        self._key = key

    def get_encryption_key(self) -> bytes:
        return self._key


class _FakeEvents:
    EntryAdded = "EntryAdded"
    EntryCreated = "EntryCreated"
    EntryUpdated = "EntryUpdated"
    EntryDeleted = "EntryDeleted"

    def __init__(self) -> None:
        self.published: list = []

    def publish(self, event_type, sync=True, **kwargs):
        self.published.append((event_type, kwargs))


def _vault_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db.set_db_path(path)
    db.init_db()
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA journal_mode=MEMORY")
        conn.execute("PRAGMA synchronous=OFF")
        conn.commit()
    finally:
        conn.close()
    return path


def _filter_entries_simple(query: str, rows: list) -> list:
    q = (query or "").strip().lower()
    if not q:
        return list(rows)

    def hay(row: dict) -> str:
        return " ".join(
            [
                str(row.get("title", "")),
                str(row.get("username_masked", row.get("username", ""))),
                str(row.get("url_domain", row.get("url", ""))),
                str(row.get("notes", "")),
            ]
        ).lower()

    return [r for r in rows if q in hay(r)]


@pytest.mark.skipif(not _HAS_CRYPTO, reason="cryptography required")
class TestSprint8Crypto:
    """TEST-1: шифрование, дешифрование, деривация ключей."""

    def test_key_derivation_and_argon2(self):
        pwd = "MasterPass123!"
        h = hash_password_argon2(pwd)
        assert verify_password_argon2(h, pwd)
        assert not verify_password_argon2(h, "wrong")
        salt = b"s" * 16
        k1 = derive_key_pbkdf2(pwd, salt)
        k2 = derive_key_pbkdf2(pwd, salt)
        assert k1 == k2 and len(k1) == 32

    def test_password_strength(self):
        ok, _ = validate_password_strength("Weak1!")
        assert not ok
        ok, _ = validate_password_strength("StrongPass123!")
        assert ok

    def test_aes_gcm_roundtrip(self):
        km = _FakeKeyManager(b"k" * 32)
        cipher = EncryptionServiceAESGCM(km)
        payload = {
            "title": "T",
            "username": "u",
            "password": "secret",
            "url": "https://x.com",
            "notes": "n",
            "category": "c",
            "created_at": "1",
            "version": 1,
        }
        blob = cipher.encrypt_entry_payload(payload).encrypted_blob
        dec = cipher.decrypt_entry_payload(blob)
        assert dec["password"] == "secret"


@pytest.mark.skipif(not _HAS_CRYPTO, reason="cryptography required")
class TestSprint8Vault:
    """TEST-1: добавление, редактирование, удаление, поиск."""

    def setup_method(self):
        self._path = _vault_db()
        km = _FakeKeyManager(b"x" * 32)
        self._events = _FakeEvents()
        self._mgr = EntryManager(db, km, self._events)

    def teardown_method(self):
        db.set_db_path(None)
        try:
            os.remove(self._path)
        except OSError:
            pass

    def test_crud_and_search(self):
        e1 = self._mgr.create_entry(
            {
                "title": "GitHub",
                "username": "alice",
                "password": "p1!",
                "url": "https://github.com",
                "notes": "work account",
                "category": "Work",
            }
        )
        self._mgr.create_entry(
            {
                "title": "Personal Mail",
                "username": "bob",
                "password": "p2!",
                "url": "https://mail.example.com",
                "notes": "private",
                "category": "Personal",
            }
        )
        e1_id = e1["id"]
        got = self._mgr.get_entry(e1_id)
        assert got["username"] == "alice"

        self._mgr.update_entry(
            e1_id,
            {
                "title": "GitHub Pro",
                "username": "alice",
                "password": "p1-new!",
                "url": "https://github.com",
                "notes": "updated",
                "category": "Work",
            },
        )
        assert self._mgr.get_entry(e1_id)["title"] == "GitHub Pro"

        listed = self._mgr.get_all_entries()
        found = _filter_entries_simple("github", listed)
        assert len(found) == 1
        assert "GitHub" in found[0]["title"]

        self._mgr.delete_entry(e1_id)
        assert db.get_vault_entry(e1_id) is None
        with pytest.raises(ValueError):
            self._mgr.get_entry(e1_id)


@pytest.mark.skipif(not _HAS_CRYPTO, reason="cryptography required")
class TestSprint8Clipboard:
    """TEST-1: буфер обмена."""

    def test_copy_clear_timer_status(self):
        from unittest.mock import MagicMock, patch

        adapter = _MemAdapter()
        service = ClipboardService(adapter)
        with patch("core.clipboard.clipboard_service.get_state_manager") as mock_sm:
            mock_sm.return_value = MagicMock()
            service.copy_text("clip-secret", data_type="password", source_entry_id=7)
            assert service.get_status()["active"]
            assert adapter.get_clipboard_content() == "clip-secret"
            service.clear(reason="manual")
            assert not service.get_status()["active"]
            assert adapter.get_clipboard_content() is None


@pytest.mark.skipif(not _HAS_CRYPTO, reason="cryptography required")
class TestSprint8ImportExport:
    """TEST-1: импорт / экспорт."""

    def setup_method(self):
        self._path = _vault_db()
        set_encryption_key(b"x" * 32)
        self._created: list = []

    def teardown_method(self):
        db.set_db_path(None)
        set_encryption_key(None)
        try:
            os.remove(self._path)
        except OSError:
            pass

    def test_json_export_import_roundtrip(self):
        from unittest.mock import patch

        entries = [
            {
                "id": 1,
                "title": "Site",
                "username": "u",
                "password": "Secr3t!",
                "url": "https://a.com",
                "notes": "n",
                "category": "work",
            }
        ]
        created: list = []

        def create(entry):
            row = dict(entry)
            row["id"] = len(created) + 1
            created.append(row)
            return row

        exporter = VaultExporter(lambda: list(entries))
        importer = VaultImporter(create_entry=create, list_entries=lambda: list(created), delete_all=created.clear)

        with patch("core.import_export.exporter.verify_master_password", return_value=True), patch(
            "core.import_export.importer.verify_master_password", return_value=True
        ):
            pkg = exporter.export_encrypted_json("export-pass", master_password="master-pass")
            path = os.path.join(tempfile.gettempdir(), f"cs8_{os.getpid()}.json")
            with open(path, "w", encoding="utf-8") as f:
                import json

                json.dump(pkg, f)
            preview = importer.parse_file(path, export_password="export-pass")
            assert len(preview) == 1
            result = importer.import_file(path, "merge", master_password="master-pass", export_password="export-pass")
            assert len(result.added) == 1
            assert result.added[0]["title"] == "Site"
        try:
            os.remove(path)
        except OSError:
            pass

    def test_key_exchange_pem(self):
        _priv, pub = generate_rsa_keypair()
        norm = normalize_pem_block(pub)
        assert optional_public_key_pem(norm) == norm


class TestSprint8InputValidation:
    def test_sanitize_and_title(self):
        title, ok = validate_title("  Hello\x00World  ")
        assert ok and title == "HelloWorld"
        assert sanitize_text(None) == ""
        assert "bad" in sanitize_notes("notes") or sanitize_notes("notes") == "notes"


class TestSprint8RuntimeBudget:
    """TEST-4: мета-проверка — быстрый smoke (полный прогон — в CI / generate_test_report)."""

    def test_crypto_smoke_under_one_second(self):
        if not _HAS_CRYPTO:
            pytest.skip("no crypto")
        t0 = time.perf_counter()
        km = _FakeKeyManager(b"z" * 32)
        cipher = EncryptionServiceAESGCM(km)
        cipher.encrypt_entry_payload(
            {
                "title": "t",
                "username": "u",
                "password": "p",
                "url": "",
                "notes": "",
                "category": "",
                "created_at": "1",
                "version": 1,
            }
        )
        assert time.perf_counter() - t0 < 1.0
