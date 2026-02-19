from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QTabWidget, QWidget, QLabel, QSpinBox,
    QComboBox, QPushButton, QHBoxLayout, QGridLayout,
)
from PyQt6.QtCore import Qt
from src.gui.theme import apply_theme
from src.gui.i18n import t

THEME_OPTIONS = [("Системная", "system"), ("Светлая", "light"), ("Тёмная", "dark")]
LANG_OPTIONS = [("Русский", "ru"), ("English", "en")]

class SettingsDialog(QDialog):
    def __init__(self, parent=None, config=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle(t("dlg_settings_title"))
        self.setMinimumSize(420, 320)
        layout = QVBoxLayout(self)
        self.notebook = QTabWidget()
        sec = QWidget()
        secl = QGridLayout(sec)
        secl.addWidget(QLabel(t("label_clipboard_timeout")), 0, 0)
        self.clipboard_timeout_var = QSpinBox()
        self.clipboard_timeout_var.setRange(0, 300)
        self.clipboard_timeout_var.setValue(getattr(config, "clipboard_timeout", 30) if config else 30)
        secl.addWidget(self.clipboard_timeout_var, 0, 1)
        secl.addWidget(QLabel(t("label_auto_lock")), 1, 0)
        self.auto_lock_var = QSpinBox()
        self.auto_lock_var.setRange(0, 120)
        self.auto_lock_var.setValue(getattr(config, "auto_lock_minutes", 5) if config else 5)
        secl.addWidget(self.auto_lock_var, 1, 1)
        self.notebook.addTab(sec, t("tab_security"))
        app = QWidget()
        appl = QGridLayout(app)
        appl.addWidget(QLabel(t("label_theme")), 0, 0)
        self.theme_combo = QComboBox()
        self.theme_combo.addItems([t[0] for t in THEME_OPTIONS])
        self.theme_combo.setCurrentText(self._theme_display(config.theme if config else "light"))
        appl.addWidget(self.theme_combo, 0, 1)
        appl.addWidget(QLabel(t("label_lang")), 1, 0)
        self.lang_combo = QComboBox()
        self.lang_combo.addItems([t[0] for t in LANG_OPTIONS])
        self.lang_combo.setCurrentText(self._lang_display(config.language if config else "ru"))
        appl.addWidget(self.lang_combo, 1, 1)
        self.notebook.addTab(app, t("tab_appearance"))
        adv = QWidget()
        advl = QVBoxLayout(adv)
        advl.addWidget(QLabel(t("menu_backup") + " / Export"))
        b = QPushButton(t("menu_backup") + "...")
        b.setEnabled(False)
        advl.addWidget(b)
        b2 = QPushButton("Export...")
        b2.setEnabled(False)
        advl.addWidget(b2)
        self.notebook.addTab(adv, t("tab_advanced"))
        layout.addWidget(self.notebook)
        ok_btn = QPushButton(t("btn_ok"))
        ok_btn.clicked.connect(self._ok)
        layout.addWidget(ok_btn)

    def _theme_value(self, display):
        for d, v in THEME_OPTIONS:
            if d == display:
                return v
        return "light"

    def _theme_display(self, value):
        for d, v in THEME_OPTIONS:
            if v == value:
                return d
        return "Светлая"

    def _lang_value(self, display):
        for d, v in LANG_OPTIONS:
            if d == display:
                return v
        return "ru"

    def _lang_display(self, value):
        for d, v in LANG_OPTIONS:
            if v == value:
                return d
        return "Русский"

    def _ok(self):
        if self.config:
            try:
                self.config.set_clipboard_timeout(self.clipboard_timeout_var.value())
                self.config.set_auto_lock_minutes(self.auto_lock_var.value())
            except ValueError:
                pass
            theme = self._theme_value(self.theme_combo.currentText())
            lang = self._lang_value(self.lang_combo.currentText())
            self.config.set_theme(theme)
            self.config.set_language(lang)
            apply_theme(None, theme)
            parent = self.parent()
            if parent is not None and getattr(parent, "db", None) is not None:
                self.config.save_to_db(parent.db)
        self.accept()
