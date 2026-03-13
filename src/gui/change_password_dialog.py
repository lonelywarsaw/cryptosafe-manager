# диалог смены мастер-пароля: текущий, новый, подтверждение; спринт 2 CHANGE-1

import sys
import os
import secrets
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QMessageBox, QGroupBox, QFormLayout
from PyQt6.QtCore import Qt

from core.input_validation import MAX_MASTER_PASSWORD_LEN
from core.crypto.authentication import verify_password, validate_password_strength
from core.crypto.key_derivation import hash_password_argon2, derive_key_pbkdf2
from core.crypto import key_storage
from database import db as database_db
from .strings import t
from .widgets.password_entry import PasswordEntry


class ChangePasswordDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("change_password_title"))
        self.setMinimumSize(420, 280)
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)
        gr = QGroupBox(t("change_password_title"))
        fl = QFormLayout(gr)
        self._current = PasswordEntry(self)
        self._new = PasswordEntry(self)
        self._confirm = PasswordEntry(self)
        fl.addRow(t("current_password"), self._current)
        fl.addRow(t("new_password"), self._new)
        fl.addRow(t("confirm_password"), self._confirm)
        layout.addWidget(gr)
        btns = QHBoxLayout()
        btns.addStretch()
        ok_btn = QPushButton(t("ok"))
        ok_btn.setMinimumWidth(100)
        ok_btn.clicked.connect(self._on_ok)
        cancel_btn = QPushButton(t("cancel"))
        cancel_btn.setMinimumWidth(100)
        cancel_btn.clicked.connect(self.reject)
        btns.addWidget(ok_btn)
        btns.addWidget(cancel_btn)
        layout.addLayout(btns)

    def _on_ok(self):
        current = self._current.text().strip()
        new_pwd = self._new.text().strip()
        confirm = self._confirm.text().strip()
        if not current:
            QMessageBox.warning(self, t("change_password_title"), t("password_required"))
            return
        if len(current) > MAX_MASTER_PASSWORD_LEN or len(new_pwd) > MAX_MASTER_PASSWORD_LEN:
            QMessageBox.warning(self, t("change_password_title"), t("password_too_long"))
            return
        if new_pwd != confirm:
            QMessageBox.warning(self, t("change_password_title"), t("passwords_dont_match"))
            return
        ok, msg = validate_password_strength(new_pwd)
        if not ok:
            QMessageBox.warning(self, t("change_password_title"), msg)
            return
        auth_blob = database_db.get_key_store("auth_hash")
        if not auth_blob:
            QMessageBox.warning(self, t("change_password_title"), t("setup_first"))
            return
        stored_hash = auth_blob.decode("utf-8")
        if not verify_password(stored_hash, current):
            QMessageBox.warning(self, t("change_password_title"), t("wrong_password"))
            return
        # спринт 2 CHANGE-2: новый ключ, перешифровка записей, обновление key_store; при ошибке откат (CHANGE-4)
        old_key = key_storage.get_cached_key()
        if not old_key:
            QMessageBox.warning(self, t("change_password_title"), t("error_generic"))
            return
        old_auth_blob = database_db.get_key_store("auth_hash")
        old_salt_blob = database_db.get_key_store("enc_salt")
        new_salt = secrets.token_bytes(16)
        new_key = derive_key_pbkdf2(new_pwd, new_salt)
        new_auth_hash = hash_password_argon2(new_pwd)
        import base64
        from core.crypto.placeholder import AES256Placeholder
        cipher = AES256Placeholder()
        km_old = _FakeKeyManager(old_key)
        km_new_fake = _FakeKeyManager(new_key)
        try:
            rows = database_db.get_all_vault_entries()
            updates = []
            for r in rows:
                eid, title, username, enc_b64, url, notes = r[0], r[1], r[2], r[3], r[4], r[5]
                if not enc_b64:
                    updates.append((eid, title, username, "", url or "", notes or ""))
                    continue
                raw = base64.b64decode(enc_b64.encode("ascii"))
                plain = cipher.decrypt(raw, km_old)
                new_enc = cipher.encrypt(plain, km_new_fake)
                new_b64 = base64.b64encode(new_enc).decode("ascii")
                updates.append((eid, title, username, new_b64, url or "", notes or ""))
            database_db.set_key_store("auth_hash", new_auth_hash.encode("utf-8"))
            database_db.set_key_store("enc_salt", new_salt)
            key_storage.set_cached_key(new_key)
            for eid, title, username, new_b64, url, notes in updates:
                database_db.update_vault_entry(eid, title, username, new_b64, url=url, notes=notes)
            QMessageBox.information(self, t("change_password_title"), t("change_password_ok"))
            self.accept()
        except Exception:
            if old_auth_blob:
                database_db.set_key_store("auth_hash", old_auth_blob)
            if old_salt_blob:
                database_db.set_key_store("enc_salt", old_salt_blob)
            key_storage.set_cached_key(old_key)
            QMessageBox.warning(self, t("change_password_title"), t("error_generic"))


class _FakeKeyManager:
    def __init__(self, key):
        self._key = key
    def get_encryption_key(self):
        return self._key
