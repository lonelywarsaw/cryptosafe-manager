"""Unlock dialog: master password verification and key derivation. / Диалог разблокировки: проверка пароля и вывод ключа."""

import sys
import os
import time
import json
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
    """Modal login dialog shown at startup and from tray unlock. / Модальный вход при запуске и разблокировке из трея."""

    def __init__(self, parent=None, *, after_restore: bool = False):
        """Builds master password field and OK/cancel actions. / Создаёт поле мастер-пароля и кнопки OK/Отмена."""
        super().__init__(parent)
        self._after_restore = after_restore
        self.setWindowTitle(t("app_title") + " — " + t("login_title"))
        self.setMinimumSize(420, 200)
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)
        prompt = t("enter_master_password")
        if after_restore:
            prompt = f"{prompt}\n\n{t('restore_wrong_password_hint')}"
        layout.addWidget(QLabel(prompt))
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
            n_fail = get_failed_attempt_count()
            msg = (
                t("wrong_password_attempts") % n_fail
                if n_fail >= 2
                else t("wrong_password")
            )
            if self._after_restore:
                msg = f"{msg}\n\n{t('restore_wrong_password_hint')}"
            QMessageBox.warning(self, t("login_title"), msg)
            return
        salt_blob = database_db.get_key_store("enc_salt")
        if not salt_blob:
            QMessageBox.warning(self, t("login_title"), t("setup_first"))
            return

        # (KEY-3, спринт2) итерации PBKDF2 читаем из key_store.params (если есть)
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

        key = derive_key_pbkdf2(pwd, salt_blob, iterations=iterations)
        key_storage.set_cached_key(key)
        record_login_success()
        events.publish(events.UserLoggedIn, sync=True)
        self.accept()

    def get_password(self):
        """Returns the entered master password text. / Возвращает введённый текст мастер-пароля."""
        return self._password.text()
