# виджет ввода пароля: по умолчанию отображаются точки, кнопка «глаз» переключает показ/скрытие текста

from PyQt6.QtWidgets import QLineEdit, QWidget, QHBoxLayout, QPushButton
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPalette
from ..strings import t


class PasswordEntry(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._line = QLineEdit()
        self._line.setEchoMode(QLineEdit.EchoMode.Password)
        self._line.setPlaceholderText("••••••••")
        self._line.setAutoFillBackground(True)
        layout.addWidget(self._line)
        self._btn = QPushButton(t("password_show"))
        self._btn.setMinimumWidth(72)
        self._btn.setCheckable(True)
        self._btn.toggled.connect(self._on_toggle)
        layout.addWidget(self._btn)

    def showEvent(self, event):
        super().showEvent(event)
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if app and app.palette():
            pal = self._line.palette()
            pal.setColor(QPalette.ColorRole.Base, app.palette().color(QPalette.ColorRole.Base))
            pal.setColor(QPalette.ColorRole.Text, app.palette().color(QPalette.ColorRole.Text))
            pal.setColor(QPalette.ColorRole.Window, app.palette().color(QPalette.ColorRole.Window))
            self._line.setPalette(pal)
            self._btn.setPalette(app.palette())

    def _on_toggle(self, checked):
        # при checked пароль показывается текстом, иначе снова скрывается точками
        if checked:
            self._line.setEchoMode(QLineEdit.EchoMode.Normal)
            self._btn.setText(t("password_hide"))
        else:
            self._line.setEchoMode(QLineEdit.EchoMode.Password)
            self._btn.setText(t("password_show"))

    def text(self):
        return self._line.text()

    def setText(self, text):
        self._line.setText(text)

    def clear(self):
        self._line.clear()
