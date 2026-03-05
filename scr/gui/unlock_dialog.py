# При запуске спрашиваем мастер-пароль.

import hashlib
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QMessageBox
from PyQt6.QtCore import Qt

from core import config
from core.input_validation import MAX_MASTER_PASSWORD_LEN
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
        stored = config.get(config.MASTER_PASSWORD_HASH)
        if not stored:
            QMessageBox.warning(self, t("login_title"), t("setup_first"))
            return
        if hashlib.sha256(pwd.encode()).hexdigest() != stored:
            QMessageBox.warning(self, t("login_title"), t("wrong_password"))
            return
        self.accept()

    def get_password(self):
        return self._password.text()
