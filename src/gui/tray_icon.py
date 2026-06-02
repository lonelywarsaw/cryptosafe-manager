# иконка в системном трее (спринт 7, TRAY-1..4)

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon, QWidget

from .app_icon import load_app_icon
from .strings import t


class TrayController:
    def __init__(self, main_window) -> None:
        self._window = main_window
        self._tray = None
        self._available = QSystemTrayIcon.isSystemTrayAvailable()

    @property
    def available(self) -> bool:
        return self._available

    def setup(self) -> None:
        if not self._available:
            return
        self._tray = QSystemTrayIcon(self._window)
        self._tray.setToolTip(t("app_title"))
        icon = self._window.windowIcon()
        if icon.isNull():
            icon = load_app_icon() or QIcon()
        self._tray.setIcon(icon)
        menu = QMenu()
        menu.addAction(t("tray_show"), self._window.show_from_tray)
        menu.addAction(t("tray_lock"), self._window._do_auto_lock)
        menu.addAction(t("tray_unlock"), self._window._on_unlock)
        menu.addAction(t("tray_clear_clipboard"), self._window._on_clear_clipboard)
        menu.addSeparator()
        menu.addAction(t("tray_panic"), self._window._activate_panic)
        menu.addAction(t("settings"), self._window._on_settings)
        menu.addSeparator()
        menu.addAction(t("exit"), self._window._quit_app)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_activated)
        self._tray.show()
        self.update_status()

    def update_status(self) -> None:
        if not self._tray:
            return
        from core.state_manager import get_state_manager

        locked = get_state_manager().is_locked()
        self._tray.setToolTip(t("tray_tooltip_locked") if locked else t("tray_tooltip_unlocked"))

    def _on_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._window.show_from_tray()

    def notify(self, message: str) -> None:
        if self._tray:
            self._tray.showMessage(t("app_title"), message, QSystemTrayIcon.MessageIcon.Information, 3000)
