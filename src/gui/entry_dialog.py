# Окно, чтобы добавить или изменить запись (название, логин, пароль, URL, заметки).

import sys
import os
import re
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QHBoxLayout,
    QMessageBox,
    QProgressBar,
    QCheckBox,
    QSpinBox,
    QLabel,
)
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt

from core.input_validation import (
    validate_title,
    sanitize_username,
    sanitize_url,
    sanitize_notes,
    MAX_URL_LEN,
)
from core.crypto.authentication import validate_password_strength
from core.vault.password_generator import PasswordGenConfig, PasswordGenerator
from .strings import t
from .widgets.password_entry import PasswordEntry


class EntryDialog(QDialog):
    def __init__(
        self,
        parent=None,
        title="",
        username="",
        password="",
        url="",
        notes="",
        category="",
        is_edit=False,
    ):
        super().__init__(parent)
        self._is_edit = is_edit
        self._password_generated = False  # (DIALOG-2) если сгенерирован — strength можно не проверять
        self._generated_password_value = None  # чтобы понять: пользователь изменил пароль после генерации

        self.setWindowTitle(t("edit_") if is_edit else t("add"))
        self.setMinimumWidth(450)
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

        # (спринт3) Strength meter
        self._strength_label = QLabel("")
        self._strength_bar = QProgressBar()
        self._strength_bar.setRange(0, 4)
        v_strength = QVBoxLayout()
        v_strength.addWidget(self._strength_label)
        v_strength.addWidget(self._strength_bar)
        layout.addLayout(v_strength)
        try:
            # PasswordEntry хранит QLineEdit внутри; соединяемся (локально) на обновление
            self._password._line.textChanged.connect(self._update_strength_meter)
        except Exception:
            pass

        self._btn_generate = QPushButton("Generate Password")
        self._btn_generate.clicked.connect(self._open_password_generator_dialog)
        layout.addWidget(self._btn_generate)

        self._url = QLineEdit()
        self._url.setPlaceholderText(t("url"))
        self._url.setText(url)
        self._favicon_label = QLabel("")
        self._favicon_label.setFixedSize(24, 24)

        url_row = QHBoxLayout()
        url_row.addWidget(self._url)
        url_row.addWidget(self._favicon_label)
        form.addRow(t("url"), url_row)

        self._notes = QLineEdit()
        self._notes.setPlaceholderText(t("notes"))
        self._notes.setText(notes)
        form.addRow(t("notes"), self._notes)

        self._category = QLineEdit()
        self._category.setPlaceholderText("Category (optional)")
        self._category.setText(category or "")
        form.addRow("Category", self._category)

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

        # первый рендер strength
        self._update_strength_meter()

    def _on_ok(self):
        title_sanitized, ok = validate_title(self._title.text())
        if not ok:
            QMessageBox.warning(self, "", t("title_required"))
            return

        pwd = (self._password.text() or "").strip()
        if not pwd:
            QMessageBox.warning(self, t("password_field"), t("password_required"))
            return

        # URL validation (DIALOG-2)
        url_raw = (self._url.text() or "").strip()
        if url_raw:
            url_s = self._validate_and_sanitize_url(url_raw)
            if url_s is None:
                QMessageBox.warning(self, t("url"), "Некорректный URL (нужен http/https)")
                return
            # чтобы в payload попал именно валидированный вариант
            self._url.setText(url_s)
        else:
            url_s = ""

        # password strength (DIALOG-2): проверяем только если пароль не сгенерирован
        if not self._password_generated:
            ok_pw, msg = validate_password_strength(pwd)
            if not ok_pw:
                QMessageBox.warning(self, t("password_field"), msg)
                return

        # favicon fetching (DIALOG-1): best-effort, не падать если сеть/URL недоступны
        self._try_fetch_favicon(url_raw)

        self.accept()

    def _update_strength_meter(self):
        pwd = self._password.text() or ""

        # если пароль был "сгенерирован", но потом изменён руками — сбрасываем флаг
        if self._password_generated and self._generated_password_value is not None:
            if pwd != self._generated_password_value:
                self._password_generated = False

        # счётчик максимум 4: длина + (lower/upper/digit) + (symbols уплотняем)
        score = 0
        if len(pwd) >= 12:
            score += 1
        if re.search(r"[a-z]", pwd):
            score += 1
        if re.search(r"[A-Z]", pwd):
            score += 1
        if re.search(r"\d", pwd):
            score += 1

        # символы добавляем, если ещё есть место
        has_sym = re.search(r"[!@#$%^&*()_+\-=\[\]{};':\",.<>?/\\|`~]", pwd) is not None
        if has_sym and score < 4:
            score += 1

        if score > 4:
            score = 4
        self._strength_bar.setValue(score)
        self._strength_label.setText("Strength: %d/4" % score)

    def _validate_and_sanitize_url(self, url_raw: str):
        u = (url_raw or "").strip()
        if not u:
            return ""

        if "://" not in u:
            u = "https://" + u
        parsed = urllib.parse.urlparse(u)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return None

        s = sanitize_url(u)
        if len(s) > MAX_URL_LEN:
            return None
        return s

    def _try_fetch_favicon(self, url_raw: str):
        try:
            if not url_raw:
                return
            u = url_raw.strip()
            if "://" not in u:
                u = "https://" + u
            parsed = urllib.parse.urlparse(u)
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                return

            favicon_url = f"{parsed.scheme}://{parsed.netloc}/favicon.ico"
            with urllib.request.urlopen(favicon_url, timeout=2) as resp:
                data = resp.read()
            pix = QPixmap()
            pix.loadFromData(data)
            if pix.isNull():
                return
            pix = pix.scaled(
                24,
                24,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._favicon_label.setPixmap(pix)
        except Exception:
            # (DIALOG-1) favicon best-effort
            pass

    def _open_password_generator_dialog(self):
        # pop-up конфиг для генератора (GEN-2 / DIALOG-1)
        dlg = QDialog(self)
        dlg.setWindowTitle("Password generator")
        dlg.setMinimumWidth(360)

        v = QVBoxLayout(dlg)
        form = QFormLayout()

        spin_len = QSpinBox(dlg)
        spin_len.setRange(8, 64)
        spin_len.setValue(16)
        form.addRow("Length", spin_len)

        cb_upper = QCheckBox("Upper A-Z")
        cb_upper.setChecked(True)
        form.addRow(cb_upper.text(), cb_upper)

        cb_lower = QCheckBox("Lower a-z")
        cb_lower.setChecked(True)
        form.addRow(cb_lower.text(), cb_lower)

        cb_digits = QCheckBox("Digits 0-9")
        cb_digits.setChecked(True)
        form.addRow(cb_digits.text(), cb_digits)

        cb_symbols = QCheckBox("Symbols !@#$%^&*")
        cb_symbols.setChecked(True)
        form.addRow(cb_symbols.text(), cb_symbols)

        cb_amb = QCheckBox("Exclude ambiguous (l I 1 0 O)")
        cb_amb.setChecked(True)
        form.addRow(cb_amb.text(), cb_amb)

        v.addLayout(form)

        btns = QHBoxLayout()
        ok_btn = QPushButton(t("ok"))
        cancel_btn = QPushButton(t("cancel"))
        btns.addWidget(ok_btn)
        btns.addWidget(cancel_btn)
        v.addLayout(btns)

        def _do_generate():
            self._password_generated = True
            self._generated_password_value = None
            cfg = PasswordGenConfig(
                length=int(spin_len.value()),
                use_upper=cb_upper.isChecked(),
                use_lower=cb_lower.isChecked(),
                use_digits=cb_digits.isChecked(),
                use_symbols=cb_symbols.isChecked(),
                exclude_ambiguous=cb_amb.isChecked(),
            )
            gen = PasswordGenerator()
            pwd = gen.generate(cfg)
            self._password.setText(pwd)
            self._generated_password_value = pwd
            self._update_strength_meter()
            dlg.accept()

        ok_btn.clicked.connect(_do_generate)
        cancel_btn.clicked.connect(dlg.reject)

        dlg.exec()

    def get_data(self):
        title_sanitized, _ = validate_title(self._title.text())

        # URL: здесь берём уже валидированное в _on_ok, но если пользователь закрыл без on_ok — санитизируем всё равно
        url_s = sanitize_url(self._url.text())

        return {
            "title": title_sanitized,
            "username": sanitize_username(self._username.text()),
            "password": self._password.text(),
            "url": url_s,
            "notes": sanitize_notes(self._notes.text()),
            "category": self._category.text(),
        }
