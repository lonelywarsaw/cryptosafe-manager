from PyQt6.QtWidgets import QWidget, QLineEdit, QPushButton, QHBoxLayout
from PyQt6.QtCore import Qt

class PasswordEntry(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._show = False
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.entry = QLineEdit()
        self.entry.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.entry)
        self.btn = QPushButton("Показать")
        self.btn.setFixedWidth(90)
        self.btn.clicked.connect(self._toggle)
        layout.addWidget(self.btn)

    def _toggle(self):
        self._show = not self._show
        if self._show:
            self.entry.setEchoMode(QLineEdit.EchoMode.Normal)
            self.btn.setText("Скрыть")
        else:
            self.entry.setEchoMode(QLineEdit.EchoMode.Password)
            self.btn.setText("Показать")

    def get(self):
        return self.entry.text()

    def set(self, value):
        self.entry.setText(value)

    def clear(self):
        self.entry.clear()
