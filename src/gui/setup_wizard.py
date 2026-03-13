# мастер первого запуска: ввод пароля дважды, выбор пути к vault.db, параметры шифрования (заглушка)
# спринт 2: проверка силы пароля, хеш Argon2 и соль в key_store

import sys
import os
import secrets
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QGroupBox, QFormLayout, QMessageBox,
)
from PyQt6.QtCore import Qt

from core import config
from core.input_validation import MAX_MASTER_PASSWORD_LEN
from core.crypto.key_derivation import hash_password_argon2
from core.crypto.authentication import validate_password_strength
from database import db as database_db
from .strings import t
from .widgets.password_entry import PasswordEntry


class SetupWizard(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("app_title") + " — Первый запуск")
        self.setMinimumWidth(450)
        layout = QVBoxLayout(self)
        pass_group = QGroupBox(t("master_password"))
        pass_layout = QFormLayout(pass_group)
        self._pass = PasswordEntry(self)
        self._confirm = PasswordEntry(self)
        pass_layout.addRow(t("master_password"), self._pass)
        pass_layout.addRow(t("confirm_password"), self._confirm)
        layout.addWidget(pass_group)
        db_group = QGroupBox(t("db_location"))
        db_layout = QVBoxLayout(db_group)
        self._db_path_label = QLabel(config.get(config.DB_PATH) or "—")
        self._db_btn = QPushButton(t("open"))
        self._db_btn.clicked.connect(self._choose_db)
        db_layout.addWidget(self._db_path_label)
        db_layout.addWidget(self._db_btn)
        layout.addWidget(db_group)
        enc_group = QGroupBox(t("encryption_settings"))
        enc_layout = QVBoxLayout(enc_group)
        enc_layout.addWidget(QLabel("Параметры ключа (заглушка):"))
        btn_row = QHBoxLayout()
        for label in ["По умолчанию", "Высокая стойкость"]:
            b = QPushButton(label)
            b.clicked.connect(lambda checked, l=label: None)
            btn_row.addWidget(b)
        enc_layout.addLayout(btn_row)
        layout.addWidget(enc_group)
        btns = QHBoxLayout()
        btns.addStretch()
        ok_btn = QPushButton(t("ok"))
        ok_btn.clicked.connect(self._finish)
        btns.addWidget(ok_btn)
        layout.addLayout(btns)

    def _choose_db(self):
        # диалог «сохранить как» — пользователь выбирает путь к файлу vault.db, путь сохраняется в config
        path, _ = QFileDialog.getSaveFileName(self, t("db_location"), "", "Database (*.db)")
        if path:
            config.set(config.DB_PATH, path)
            self._db_path_label.setText(path)

    def _finish(self):
        # спринт 2: проверка пути, силы пароля и совпадения; хеш Argon2 и соль сохраняются в key_store
        if not config.get(config.DB_PATH) or self._db_path_label.text().strip() in ("", "—"):
            QMessageBox.warning(self, t("db_location"), t("db_location_required"))
            return
        pwd = self._pass.text().strip()
        if len(pwd) > MAX_MASTER_PASSWORD_LEN:
            QMessageBox.warning(self, t("master_password"), t("password_too_long"))
            return
        if pwd != self._confirm.text().strip():
            QMessageBox.warning(self, "", t("passwords_dont_match"))
            return
        ok, msg = validate_password_strength(pwd)
        if not ok:
            QMessageBox.warning(self, t("master_password"), msg)
            return
        path = config.get(config.DB_PATH)
        database_db.set_db_path(path)
        database_db.init_db()
        auth_hash = hash_password_argon2(pwd)
        salt = secrets.token_bytes(16)
        database_db.set_key_store("auth_hash", auth_hash.encode("utf-8"))
        database_db.set_key_store("enc_salt", salt)
        self.accept()
