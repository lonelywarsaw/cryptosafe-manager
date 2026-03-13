# при каждом запуске запрашивается мастер-пароль; спринт 2: проверка по Argon2, вывод ключа, кэш, backoff

import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QMessageBox
from PyQt6.QtCore import Qt

from core import config
from core.input_validation import MAX_MASTER_PASSWORD_LEN
from core.crypto.authentication import verify_password, record_login_success, record_login_failure, get_failed_attempt_count
from core.crypto.key_derivation import derive_key_pbkdf2
from core.crypto import key_storage
from core import events
from database import db as database_db
from .strings import t
from .widgets.password_entry import PasswordEntry


class UnlockDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("app_title") + " — " + t("login_title"))
        self.setMinimumSize(420, 200)
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.addWidget(QLabel(t("enter_master_password")))
        self._password = PasswordEntry(self)
        layout.addWidget(self._password)
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
        pwd = self._password.text().strip()
        if not pwd:
            QMessageBox.warning(self, t("login_title"), t("password_required"))
            return
        if len(pwd) > MAX_MASTER_PASSWORD_LEN:
            QMessageBox.warning(self, t("login_title"), t("password_too_long"))
            return
        # спринт 2: экспоненциальная задержка при неудачных попытках (1–2: 1 сек, 3–4: 5 сек, 5+: 30 сек)
        n = get_failed_attempt_count()
        if n >= 5:
            time.sleep(30)
        elif n >= 3:
            time.sleep(5)
        elif n >= 1:
            time.sleep(1)
        auth_blob = database_db.get_key_store("auth_hash")
        if not auth_blob:
            QMessageBox.warning(self, t("login_title"), t("setup_first"))
            return
        stored_hash = auth_blob.decode("utf-8")
        if not verify_password(stored_hash, pwd):
            record_login_failure()
            QMessageBox.warning(self, t("login_title"), t("wrong_password"))
            return
        salt_blob = database_db.get_key_store("enc_salt")
        if not salt_blob:
            QMessageBox.warning(self, t("login_title"), t("setup_first"))
            return
        key = derive_key_pbkdf2(pwd, salt_blob)
        key_storage.set_cached_key(key)
        record_login_success()
        events.publish(events.UserLoggedIn, sync=True)
        self.accept()

    def get_password(self):
        return self._password.text()
