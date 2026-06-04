"""Settings dialog: security profiles, theme, clipboard, tray. / Диалог настроек: профили, тема, буфер, трей."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QTabWidget,
    QWidget,
    QFormLayout,
    QSpinBox,
    QComboBox,
    QPushButton,
    QHBoxLayout,
    QLabel,
    QCheckBox,
    QLineEdit,
    QMessageBox,
    QScrollArea,
)

from core import config
from core.security.security_profiles import PROFILES, apply_profile, describe_profile, profile_settings
from .strings import t
from .user_errors import user_facing_error


class SettingsDialog(QDialog):
    """Tabbed preferences editor for app configuration. / Редактор настроек приложения с вкладками."""

    def __init__(self, parent=None):
        """Builds security, appearance, and advanced tabs. / Создаёт вкладки безопасности, внешнего вида и доп. опций."""
        super().__init__(parent)
        self.setWindowTitle(t("settings"))
        self.setMinimumWidth(440)
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            avail = screen.availableGeometry()
            self.setMaximumHeight(int(avail.height() * 0.85))
            self.resize(min(480, avail.width() - 40), min(520, int(avail.height() * 0.75)))
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(self._security_tab_scroll(), t("security"))
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

    def _security_tab_scroll(self) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(self._security_tab())
        return scroll

    def _security_tab(self):
        w = QWidget()
        form = QFormLayout(w)
        form.setVerticalSpacing(8)
        self._profile_combo = QComboBox()
        self._profile_combo.addItem(t("profile_standard"), "standard")
        self._profile_combo.addItem(t("profile_enhanced"), "enhanced")
        self._profile_combo.addItem(t("profile_paranoid"), "paranoid")
        self._profile_combo.currentIndexChanged.connect(self._on_profile_changed)
        form.addRow(t("security_profile"), self._profile_combo)
        self._profile_desc = QLabel()
        self._profile_desc.setWordWrap(True)
        form.addRow(t("profile_desc"), self._profile_desc)
        self._profile_combo.setToolTip(t("security_profile_hint"))

        self._clipboard_spin = QSpinBox()
        self._clipboard_spin.setRange(0, 300)
        form.addRow(t("clipboard_timeout"), self._clipboard_spin)
        self._notifications_checkbox = QCheckBox()
        form.addRow(t("notifications_enabled"), self._notifications_checkbox)
        self._security_level = QComboBox()
        self._security_level.addItems(
            [t("security_basic"), t("security_advanced"), t("security_paranoid")]
        )
        self._security_level.setToolTip(t("security_level_hint"))
        form.addRow(t("security_level"), self._security_level)
        self._whitelist_edit = QLineEdit()
        self._whitelist_edit.setToolTip(t("clipboard_whitelist_hint"))
        form.addRow(t("clipboard_whitelist"), self._whitelist_edit)
        self._autolock_spin = QSpinBox()
        self._autolock_spin.setRange(1, 480)
        form.addRow(t("auto_lock"), self._autolock_spin)
        self._sensitivity_combo = QComboBox()
        self._sensitivity_combo.setToolTip(t("activity_sensitivity_hint"))
        form.addRow(t("activity_sensitivity"), self._sensitivity_combo)
        self._device_combo = QComboBox()
        self._device_combo.addItem(t("device_laptop"), "laptop")
        self._device_combo.addItem(t("device_desktop"), "desktop")
        form.addRow(t("device_profile_label"), self._device_combo)
        self._tray_checkbox = QCheckBox()
        form.addRow(t("minimize_to_tray"), self._tray_checkbox)
        self._start_tray_checkbox = QCheckBox()
        form.addRow(t("start_minimized_tray"), self._start_tray_checkbox)
        self._panic_hotkey_checkbox = QCheckBox()
        form.addRow(t("panic_hotkey"), self._panic_hotkey_checkbox)
        self._panic_stealth_checkbox = QCheckBox()
        form.addRow(t("panic_stealth"), self._panic_stealth_checkbox)
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
        hint = QLabel(t("backup_export_hint"))
        hint.setWordWrap(True)
        layout.addWidget(hint)
        for label_key, method in (
            ("backup", "_on_backup"),
            ("restore_backup", "_on_restore_backup"),
            ("s6_export", "_on_export_vault"),
            ("s6_import", "_on_import_vault"),
        ):
            btn = QPushButton(t(label_key))
            btn.clicked.connect(lambda _checked=False, m=method: self._run_main_window_action(m))
            layout.addWidget(btn)
        layout.addStretch()
        return w

    def _run_main_window_action(self, method_name: str) -> None:
        """Close settings and run backup/export handler from MainWindow."""
        main = self.parent()
        if main is None or not hasattr(main, method_name):
            QMessageBox.information(self, t("settings"), t("backup_export_unavailable"))
            return
        handler = getattr(main, method_name)
        self.accept()
        QTimer.singleShot(0, handler)

    def _fill_sensitivity_combo(self, selected: str = "medium") -> None:
        self._sensitivity_combo.clear()
        for value, key in (("low", "sens_low"), ("medium", "sens_medium"), ("high", "sens_high")):
            self._sensitivity_combo.addItem(t(key), value)
        idx = {"low": 0, "medium": 1, "high": 2}.get((selected or "medium").lower(), 1)
        self._sensitivity_combo.setCurrentIndex(idx)

    def _apply_profile_preview(self, name: str) -> None:
        """Updates security fields to show profile preset (before Apply)."""
        preset = profile_settings(name)
        if not preset:
            return
        self._clipboard_spin.setValue(int(preset.get(config.CLIPBOARD_TIMEOUT, "30") or "30"))
        level = preset.get(config.CLIPBOARD_SECURITY_LEVEL, "basic") or "basic"
        self._security_level.setCurrentIndex({"basic": 0, "advanced": 1, "paranoid": 2}.get(level, 0))
        self._autolock_spin.setValue(max(1, int(preset.get(config.AUTO_LOCK_MINUTES, "5") or "5")))
        sens = (preset.get(config.ACTIVITY_SENSITIVITY, "medium") or "medium").lower()
        if sens in ("low", "medium", "high"):
            self._sensitivity_combo.setCurrentIndex({"low": 0, "medium": 1, "high": 2}[sens])

    def _on_profile_changed(self, _index=None):
        name = self._profile_combo.currentData() or "standard"
        self._profile_desc.setText(describe_profile(name))
        self._apply_profile_preview(name)

    def _load(self):
        self._clipboard_spin.setSuffix(t("unit_seconds"))
        self._autolock_spin.setSuffix(t("unit_minutes"))
        self._clipboard_spin.setValue(int(config.get(config.CLIPBOARD_TIMEOUT, "30") or "30"))
        self._notifications_checkbox.setChecked(
            int(config.get(config.CLIPBOARD_NOTIFICATIONS, "1") or "1") > 0
        )
        level = config.get(config.CLIPBOARD_SECURITY_LEVEL, "basic") or "basic"
        self._security_level.setCurrentIndex({"basic": 0, "advanced": 1, "paranoid": 2}.get(level, 0))
        self._whitelist_edit.setText(config.get(config.CLIPBOARD_APP_WHITELIST, "") or "")
        self._autolock_spin.setValue(max(1, int(config.get(config.AUTO_LOCK_MINUTES, "5") or "5")))
        theme = config.get(config.THEME, "system") or "system"
        self._theme_combo.setCurrentIndex({"system": 0, "dark": 1, "light": 2}.get(theme, 0))
        lang = config.get(config.LANGUAGE, "ru") or "ru"
        self._lang_combo.setCurrentIndex(0 if lang == "ru" else 1)
        profile = config.get(config.SECURITY_PROFILE, "standard") or "standard"
        idx = {"standard": 0, "enhanced": 1, "paranoid": 2}.get(profile, 0)
        self._profile_combo.blockSignals(True)
        self._profile_combo.setCurrentIndex(idx)
        self._profile_combo.blockSignals(False)
        self._profile_desc.setText(describe_profile(profile))
        sens = (config.get(config.ACTIVITY_SENSITIVITY, "medium") or "medium").lower()
        if sens not in ("low", "medium", "high"):
            sens = "medium"
        self._fill_sensitivity_combo(sens)
        device = config.get(config.DEVICE_PROFILE, "laptop") or "laptop"
        self._device_combo.setCurrentIndex(0 if device == "laptop" else 1)
        self._tray_checkbox.setChecked(int(config.get(config.MINIMIZE_TO_TRAY, "0") or "0") > 0)
        self._start_tray_checkbox.setChecked(int(config.get(config.START_MINIMIZED_TRAY, "0") or "0") > 0)
        self._panic_hotkey_checkbox.setChecked(int(config.get(config.PANIC_HOTKEY_ENABLED, "1") or "1") > 0)
        self._panic_stealth_checkbox.setChecked(int(config.get(config.PANIC_STEALTH_MODE, "0") or "0") > 0)

    def _apply(self):
        profile_name = self._profile_combo.currentData() or "standard"
        prev = config.get(config.SECURITY_PROFILE, "standard") or "standard"
        profile_changed = profile_name in PROFILES and profile_name != prev
        try:
            if profile_changed:
                apply_profile(profile_name)
                self._load()
            config.set(config.CLIPBOARD_TIMEOUT, str(self._clipboard_spin.value()))
            config.set(config.CLIPBOARD_NOTIFICATIONS, "1" if self._notifications_checkbox.isChecked() else "0")
            level_map = {0: "basic", 1: "advanced", 2: "paranoid"}
            config.set(config.CLIPBOARD_SECURITY_LEVEL, level_map[self._security_level.currentIndex()])
            config.set(config.CLIPBOARD_APP_WHITELIST, (self._whitelist_edit.text() or "").strip())
            config.set(config.AUTO_LOCK_MINUTES, str(self._autolock_spin.value()))
            config.set(config.ACTIVITY_SENSITIVITY, self._sensitivity_combo.currentData() or "medium")
            config.set(config.DEVICE_PROFILE, self._device_combo.currentData())
            config.set(config.SECURITY_PROFILE, profile_name)
        except ValueError as exc:
            QMessageBox.warning(self, t("settings"), user_facing_error(exc))
            return

        config.set(config.MINIMIZE_TO_TRAY, "1" if self._tray_checkbox.isChecked() else "0")
        config.set(config.START_MINIMIZED_TRAY, "1" if self._start_tray_checkbox.isChecked() else "0")
        config.set(config.PANIC_HOTKEY_ENABLED, "1" if self._panic_hotkey_checkbox.isChecked() else "0")
        config.set(config.PANIC_STEALTH_MODE, "1" if self._panic_stealth_checkbox.isChecked() else "0")
        theme_map = {0: "system", 1: "dark", 2: "light"}
        config.set(config.THEME, theme_map[self._theme_combo.currentIndex()])
        config.set(config.LANGUAGE, "ru" if self._lang_combo.currentIndex() == 0 else "en")

        if profile_changed:
            from core import events

            events.publish(events.SecurityProfileChanged, sync=True, profile=profile_name)
        self.accept()
