from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout,
    QFileDialog, QMessageBox, QLineEdit,
)
from src.gui.widgets import PasswordEntry
from src.gui.i18n import t

class SetupWizard(QDialog):
    def __init__(self, parent=None, on_done=None):
        super().__init__(parent)
        self.on_done = on_done
        self.result_password = None
        self.result_db_path = None
        self.setWindowTitle(t("dlg_setup_title"))
        self.setMinimumSize(500, 420)
        self.resize(500, 420)
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.addWidget(QLabel(t("label_create_pw")))
        self.pw1 = PasswordEntry(self)
        layout.addWidget(self.pw1)
        layout.addWidget(QLabel(t("label_confirm_pw")))
        self.pw2 = PasswordEntry(self)
        layout.addWidget(self.pw2)
        layout.addSpacing(16)
        layout.addWidget(QLabel(t("label_db_path")))
        path_layout = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setText(str(Path.home() / ".cryptosafe" / "cryptosafe.db"))
        path_layout.addWidget(self.path_edit)
        browse_btn = QPushButton(t("btn_browse"))
        browse_btn.clicked.connect(self._browse)
        path_layout.addWidget(browse_btn)
        layout.addLayout(path_layout)
        layout.addStretch()
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        finish_btn = QPushButton(t("btn_finish"))
        finish_btn.clicked.connect(self._finish)
        cancel_btn = QPushButton(t("btn_cancel"))
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(finish_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _browse(self):
        path, _ = QFileDialog.getSaveFileName(self, "База данных", self.path_edit.text(), "База данных (*.db)")
        if path:
            self.path_edit.setText(path)

    def _finish(self):
        p1 = self.pw1.get()
        p2 = self.pw2.get()
        if not p1 or len(p1) < 4:
            QMessageBox.critical(self, "Ошибка", "Пароль должен быть не короче 4 символов.")
            return
        if p1 != p2:
            QMessageBox.critical(self, "Ошибка", "Пароли не совпадают.")
            return
        path = self.path_edit.text().strip()
        if not path:
            QMessageBox.critical(self, "Ошибка", "Укажите расположение базы данных.")
            return
        self.result_password = p1
        self.result_db_path = Path(path)
        if self.on_done:
            self.on_done(self.result_password, self.result_db_path)
        self.accept()
