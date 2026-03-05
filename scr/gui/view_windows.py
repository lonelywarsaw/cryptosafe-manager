# Окна из меню «Вид»: монитор состояния и журнал аудита.

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QGridLayout
from PyQt6.QtCore import QTimer

from core.state_manager import get_state_manager
from .strings import t


class StateMonitorWindow(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("state_monitor"))
        self.setMinimumSize(320, 200)
        layout = QVBoxLayout(self)
        self._labels = {}
        grid = QGridLayout()
        grid.addWidget(QLabel(t("state_session")), 0, 0)
        self._labels["session"] = QLabel("—")
        grid.addWidget(self._labels["session"], 0, 1)
        grid.addWidget(QLabel(t("state_clipboard")), 1, 0)
        self._labels["clipboard"] = QLabel("—")
        grid.addWidget(self._labels["clipboard"], 1, 1)
        grid.addWidget(QLabel(t("state_inactivity")), 2, 0)
        self._labels["inactivity"] = QLabel("—")
        grid.addWidget(self._labels["inactivity"], 2, 1)
        layout.addLayout(grid)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(500)

    def _refresh(self):
        sm = get_state_manager()
        state = sm.get_state()
        self._labels["session"].setText(t("status_locked") if state["locked"] else t("status_unlocked"))
        self._labels["clipboard"].setText("%d / %d" % (state["clipboard_seconds_left"], state["clipboard_timeout"]))
        self._labels["inactivity"].setText(str(state["inactivity_seconds"]))

    def showEvent(self, event):
        super().showEvent(event)
        self._refresh()


class AuditLogViewer(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Журнал аудита"))
