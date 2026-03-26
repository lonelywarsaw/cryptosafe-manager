# диалог смены мастер-пароля: текущий, новый, подтверждение; спринт 2 CHANGE-1

import sys
import os
import json
import secrets

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QPushButton, QHBoxLayout, QMessageBox, QGroupBox, QFormLayout
from PyQt6.QtCore import Qt

from core.input_validation import MAX_MASTER_PASSWORD_LEN
from core.crypto.authentication import verify_password, validate_password_strength
from core.crypto.key_derivation import hash_password_argon2, derive_key_pbkdf2
from core.crypto import key_storage
from database import db as database_db
from core.vault.encryption_service import EncryptionServiceAESGCM
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
        params_blob = database_db.get_key_store("params")
        iterations = None
        if params_blob:
            try:
                params = json.loads(params_blob.decode("utf-8"))
                iterations = params.get("pbkdf2_iterations")
                if iterations is not None:
                    iterations = int(iterations)
            except Exception:
                iterations = None
        new_key = derive_key_pbkdf2(new_pwd, new_salt, iterations=iterations)
        new_auth_hash = hash_password_argon2(new_pwd)
        cipher_old = EncryptionServiceAESGCM(_FakeKeyManager(old_key))
        cipher_new = EncryptionServiceAESGCM(_FakeKeyManager(new_key))
        try:
            rows = database_db.get_all_vault_entries()

            # CHANGE-4: если перешифровка упадёт — восстанавливаем старые encrypted_data
            old_payloads = {}
            for r in rows:
                eid, encrypted_data, created_at, updated_at, tags = r
                old_payloads[int(eid)] = (encrypted_data, tags)

            # перешифровка всех записей (Decrypt old -> Encrypt new)
            for r in rows:
                eid, encrypted_data, created_at, updated_at, tags = r
                plain_payload = cipher_old.decrypt_entry_payload(encrypted_data)
                created_at_use = created_at or plain_payload.get("created_at") or cipher_old.now_timestamp()
                payload_new = EncryptionServiceAESGCM.build_payload_for_encrypt(plain_payload, created_at=created_at_use)
                new_encrypted = cipher_new.encrypt_entry_payload(payload_new).encrypted_blob
                database_db.update_vault_entry(int(eid), encrypted_data=new_encrypted, tags=tags)

            database_db.set_key_store("auth_hash", new_auth_hash.encode("utf-8"))
            database_db.set_key_store("enc_salt", new_salt)
            key_storage.set_cached_key(new_key)
            QMessageBox.information(self, t("change_password_title"), t("change_password_ok"))
            self.accept()
        except Exception:
            if old_auth_blob:
                database_db.set_key_store("auth_hash", old_auth_blob)
            if old_salt_blob:
                database_db.set_key_store("enc_salt", old_salt_blob)
            # откат изменений в vault_entries
            try:
                rows = database_db.get_all_vault_entries()
                # восстановление делаем только если список старых значений доступен
                # (old_payloads может быть не задан, если ошибка случилась очень рано)
                if "old_payloads" in locals():
                    for r in rows:
                        eid = int(r[0])
                        if eid in old_payloads:
                            encrypted_data_old, tags_old = old_payloads[eid]
                            database_db.update_vault_entry(eid, encrypted_data=encrypted_data_old, tags=tags_old)
            except Exception:
                pass
            key_storage.set_cached_key(old_key)
            QMessageBox.warning(self, t("change_password_title"), t("error_generic"))


class _FakeKeyManager:
    def __init__(self, key):
        self._key = key
    def get_encryption_key(self):
        return self._key
