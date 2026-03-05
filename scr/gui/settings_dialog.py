# Окно настроек приложения.

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QTabWidget, QWidget, QFormLayout,
    QSpinBox, QComboBox, QPushButton, QHBoxLayout, QLabel, QGroupBox,
)
from PyQt6.QtCore import Qt

from core import config
from .strings import t


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("settings"))
        self.setMinimumWidth(400)
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(self._security_tab(), t("security"))
        tabs.addTab(self._appearance_tab(), t("appearance"))
        tabs.addTab(self._advanced_tab(), t("advanced"))
        layout.addWidget(tabs)
        btns = QHBoxLayout()
        btns.addStretch()
        self._apply_btn = QPushButton(t("apply"))
        self._apply_btn.clicked.connect(self._apply)
        self._cancel_btn = QPushButton(t("cancel"))
        self._cancel_btn.clicked.connect(self.reject)
        btns.addWidget(self._apply_btn)
        btns.addWidget(self._cancel_btn)
        layout.addLayout(btns)
        self._load()

    def _security_tab(self):
        w = QWidget()
        form = QFormLayout(w)
        self._clipboard_spin = QSpinBox()
        self._clipboard_spin.setRange(0, 300)
        self._clipboard_spin.setSuffix(" сек")
        form.addRow(t("clipboard_timeout"), self._clipboard_spin)
        self._autolock_spin = QSpinBox()
        self._autolock_spin.setRange(0, 120)
        self._autolock_spin.setSuffix(" мин")
        form.addRow(t("auto_lock"), self._autolock_spin)
        return w

    def _appearance_tab(self):
        w = QWidget()
        form = QFormLayout(w)
        self._theme_combo = QComboBox()
        self._theme_combo.addItems([t("theme_system"), t("theme_dark"), t("theme_light")])
        form.addRow(t("theme"), self._theme_combo)
        self._lang_combo = QComboBox()
        self._lang_combo.addItem("Русский", "ru")
        self._lang_combo.addItem("English", "en")
        form.addRow(t("language"), self._lang_combo)
        return w

    def _advanced_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.addWidget(QLabel(t("backup_export")))
        return w

    def _load(self):
        self._clipboard_spin.setValue(int(config.get(config.CLIPBOARD_TIMEOUT, "30") or "30"))
        self._autolock_spin.setValue(int(config.get(config.AUTO_LOCK_MINUTES, "5") or "5"))
        theme = config.get(config.THEME, "system") or "system"
        self._theme_combo.setCurrentIndex({"system": 0, "dark": 1, "light": 2}.get(theme, 0))
        lang = config.get(config.LANGUAGE, "ru") or "ru"
        self._lang_combo.setCurrentIndex(0 if lang == "ru" else 1)

    def _apply(self):
        config.set(config.CLIPBOARD_TIMEOUT, str(self._clipboard_spin.value()))
        config.set(config.AUTO_LOCK_MINUTES, str(self._autolock_spin.value()))
        theme_map = {0: "system", 1: "dark", 2: "light"}
        config.set(config.THEME, theme_map[self._theme_combo.currentIndex()])
        config.set(config.LANGUAGE, "ru" if self._lang_combo.currentIndex() == 0 else "en")
        self.accept()
