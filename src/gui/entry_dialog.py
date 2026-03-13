# Окно, чтобы добавить или изменить запись (название, логин, пароль, URL, заметки).

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QLineEdit, QPushButton, QHBoxLayout, QMessageBox
from PyQt6.QtCore import Qt

from core.input_validation import (
    validate_title,
    sanitize_username,
    sanitize_url,
    sanitize_notes,
)
from .strings import t
from .widgets.password_entry import PasswordEntry

class EntryDialog(QDialog):

    def __init__(self, parent=None, title="", username="", password="", url="", notes="", is_edit=False):
        super().__init__(parent)
        self._is_edit = is_edit
        self.setWindowTitle(t("edit_") if is_edit else t("add"))
        self.setMinimumWidth(400)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self._title = QLineEdit()
        self._title.setPlaceholderText(t("title"))
        self._title.setText(title)
        form.addRow(t("title"), self._title)
        self._username = QLineEdit()
        self._username.setPlaceholderText(t("login"))
        self._username.setText(username)
        form.addRow(t("login"), self._username)
        self._password = PasswordEntry(self)
        self._password.setText(password)
        form.addRow(t("password_field"), self._password)
        self._url = QLineEdit()
        self._url.setPlaceholderText(t("url"))
        self._url.setText(url)
        form.addRow(t("url"), self._url)
        self._notes = QLineEdit()
        self._notes.setPlaceholderText(t("notes"))
        self._notes.setText(notes)
        form.addRow(t("notes"), self._notes)
        layout.addLayout(form)
        btns = QHBoxLayout()
        btns.addStretch()
        ok_btn = QPushButton(t("ok"))
        ok_btn.clicked.connect(self._on_ok)
        cancel_btn = QPushButton(t("cancel"))
        cancel_btn.clicked.connect(self.reject)
        btns.addWidget(ok_btn)
        btns.addWidget(cancel_btn)
        layout.addLayout(btns)

    def _on_ok(self):
        title_sanitized, ok = validate_title(self._title.text())
        if not ok:
            QMessageBox.warning(self, "", t("title_required"))
            return
        self.accept()

    def get_data(self):
        title_sanitized, _ = validate_title(self._title.text())
        return {
            "title": title_sanitized,
            "username": sanitize_username(self._username.text()),
            "password": self._password.text(),
            "url": sanitize_url(self._url.text()),
            "notes": sanitize_notes(self._notes.text()),
        }
