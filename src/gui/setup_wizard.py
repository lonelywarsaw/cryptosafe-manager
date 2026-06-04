"""First-run wizard: master password, DB path, encryption presets. / Мастер первого запуска: пароль, путь к БД, шифрование."""

import sys
import os
import json
import secrets
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QGroupBox, QFormLayout, QMessageBox,
)
from PyQt6.QtCore import Qt

from core import config
from core.input_validation import MAX_MASTER_PASSWORD_LEN
from core.crypto.key_derivation import (
    hash_password_argon2,
    PBKDF2_ITERATIONS,
    PBKDF2_SALT_LEN,
    PBKDF2_KEY_LEN,
)
from core.crypto.authentication import validate_password_strength
from database import db as database_db
from .strings import t
from .theme import apply_dialog_layout
from .widgets.password_entry import PasswordEntry


class SetupWizard(QDialog):
    """Initial setup dialog for new vault creation. / Диалог первичной настройки нового хранилища."""

    def __init__(self, parent=None):
        """Builds password, database, and encryption preset fields. / Создаёт поля пароля, БД и пресетов шифрования."""
        super().__init__(parent)
        self.setWindowTitle(t("app_title") + " — Первый запуск")
        self.setMinimumWidth(450)
        layout = QVBoxLayout(self)
        apply_dialog_layout(layout)
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
        self._pbkdf2_iterations = PBKDF2_ITERATIONS
        self._enc_hint = QLabel(
            f"PBKDF2: {self._pbkdf2_iterations:,} итераций (по умолчанию). "
            "Влияет на скорость входа и стойкость ключа AES."
        )
        self._enc_hint.setWordWrap(True)
        enc_layout.addWidget(self._enc_hint)
        btn_row = QHBoxLayout()
        btn_default = QPushButton("По умолчанию")
        btn_default.clicked.connect(lambda: self._set_encryption_preset(PBKDF2_ITERATIONS))
        btn_high = QPushButton("Высокая стойкость")
        btn_high.clicked.connect(lambda: self._set_encryption_preset(600_000))
        btn_row.addWidget(btn_default)
        btn_row.addWidget(btn_high)
        enc_layout.addLayout(btn_row)
        layout.addWidget(enc_group)
        btns = QHBoxLayout()
        btns.addStretch()
        ok_btn = QPushButton(t("ok"))
        ok_btn.clicked.connect(self._finish)
        btns.addWidget(ok_btn)
        layout.addLayout(btns)

    def _set_encryption_preset(self, iterations: int) -> None:
        self._pbkdf2_iterations = int(iterations)
        label = "по умолчанию" if iterations == PBKDF2_ITERATIONS else "высокая стойкость"
        self._enc_hint.setText(
            f"PBKDF2: {self._pbkdf2_iterations:,} итераций ({label}). "
            "Параметр сохраняется при завершении мастера."
        )

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
        # (KEY-3, спринт2) параметры PBKDF2 храним в key_store с версионированием
        pbkdf2_iterations = int(getattr(self, "_pbkdf2_iterations", PBKDF2_ITERATIONS))
        config.set("pbkdf2_iterations", str(pbkdf2_iterations))
        params = {
            "pbkdf2_iterations": pbkdf2_iterations,
            "salt_len": PBKDF2_SALT_LEN,
            "key_len": PBKDF2_KEY_LEN,
            "version": 1,
        }
        database_db.set_key_store("params", json.dumps(params).encode("utf-8"))
        self.accept()
