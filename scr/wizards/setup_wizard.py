import os
from PyQt6.QtWidgets import (
    QWizard, QWizardPage, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog, QMessageBox, QFormLayout, QComboBox
)
from PyQt6.QtGui import QPixmap, QIcon, QFont
from PyQt6.QtCore import Qt, pyqtSignal
from src.gui.widgets.password_entry import PasswordEntry


class SetupWizard(QWizard):
    setupCompleted = pyqtSignal(dict)  # db_path, master_password, encryption_config

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Первоначальная настройка")
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.resize(600, 500)
        self.setFixedSize(600, 500)

        self._create_pages()
        self._setup_styles()

    def _create_pages(self):
        # Страница 1: Мастер-пароль
        self.password_page = PasswordPage()
        self.password_page.completeChanged.connect(self._on_password_page_changed)
        self.addPage(self.password_page)

        # Страница 2: Расположение БД
        self.db_page = DatabasePage()
        self.db_page.completeChanged.connect(self._on_db_page_changed)
        self.addPage(self.db_page)

        # Страница 3: Настройки шифрования
        self.encryption_page = EncryptionPage()
        self.addPage(self.encryption_page)

    def _setup_styles(self):
        # Кастомный заголовок
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.GlobalColor.transparent)
        self.setPixmap(QWizard.WizardPixmap.BannerPixmap, pixmap)
        self.setPixmap(QWizard.WizardPixmap.WatermarkPixmap, pixmap)

    def _on_password_page_changed(self):
        self.button(QWizard.WizardButton.NextButton).setEnabled(
            self.password_page.isComplete()
        )

    def _on_db_page_changed(self):
        self.button(QWizard.WizardButton.NextButton).setEnabled(
            self.db_page.isComplete()
        )

    def accept(self):
        """Завершение мастера"""
        config = {
            'db_path': self.db_page.db_path,
            'master_password': self.password_page.get_password(),
            'encryption_config': self.encryption_page.get_config()
        }
        self.setupCompleted.emit(config)
        super().accept()


class PasswordPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Мастер-пароль")
        self.setSubTitle("Создайте надежный мастер-пароль для защиты хранилища.")
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Заголовок
        title = QLabel("🔐 Создание мастер-пароля")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        layout.addWidget(title)

        # Поля ввода
        form_layout = QFormLayout()

        self.password_entry = PasswordEntry()
        self.password_entry.setPlaceholderText("Введите мастер-пароль (минимум 12 символов)")
        form_layout.addRow("Новый пароль:", self.password_entry)

        self.confirm_entry = PasswordEntry()
        self.confirm_entry.setPlaceholderText("Подтвердите мастер-пароль")
        form_layout.addRow("Подтверждение:", self.confirm_entry)

        layout.addLayout(form_layout)

        # Информация о требованиях
        info = QLabel(
            "• Минимум 12 символов\n"
            "• Используйте буквы разного регистра\n"
            "• Добавьте цифры и специальные символы"
        )
        info.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(info)

        layout.addStretch()

    def isComplete(self):
        password = self.password_entry.text()
        confirm = self.confirm_entry.text()
        return (len(password) >= 12 and
                password == confirm and
                any(c.isdigit() for c in password))

    def get_password(self):
        return self.password_entry.text()


class DatabasePage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Расположение базы данных")
        self.setSubTitle("Выберите место для хранения зашифрованного хранилища.")
        self.db_path = ""
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel("💾 База данных")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        layout.addWidget(title)

        # Поле выбора файла
        hbox = QHBoxLayout()

        self.db_label = QLabel("Не выбран")
        self.db_label.setStyleSheet("padding: 8px; border: 1px solid #ccc; border-radius: 4px;")
        self.db_label.setMinimumWidth(300)
        hbox.addWidget(self.db_label)

        self.browse_btn = QPushButton("Обзор...")
        self.browse_btn.clicked.connect(self._browse_database)
        hbox.addWidget(self.browse_btn)

        layout.addLayout(hbox)

        # Информация
        info = QLabel(
            "• Файл будет содержать все зашифрованные данные\n"
            "• Рекомендуется использовать внешний диск или облако\n"
            "• Регулярно создавайте резервные копии"
        )
        info.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(info)

        layout.addStretch()

    def _browse_database(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Выберите расположение базы данных",
            "crypto_vault.db", "Database files (*.db)"
        )
        if file_path:
            self.db_path = file_path
            self.db_label.setText(os.path.basename(file_path))
            self.completeChanged.emit()

    def isComplete(self):
        return bool(self.db_path)


class EncryptionPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Настройки шифрования")
        self.setSubTitle("Параметры формирования ключа (заглушка)")
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel("🔒 Шифрование")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        layout.addWidget(title)

        # Заглушка настроек
        info = QLabel(
            "✓ AES-256 шифрование (рекомендуется)\n"
            "✓ PBKDF2 для вывода ключа из пароля\n"
            "✓ Salt генерируется автоматически\n"
            "✓ Итерации: 100,000 (высокая безопасность)\n"
            "\nСпринт 2: Расширенные параметры"
        )
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info.setStyleSheet("padding: 20px; background: #f0f8ff; border-radius: 8px;")
        layout.addWidget(info)

        layout.addStretch()

    def get_config(self):
        return {
            "algorithm": "AES-256",
            "key_derivation": "PBKDF2",
            "iterations": 100000,
            "status": "recommended"
        }
