import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from PyQt6.QtWidgets import (QDialog, QTabWidget, QVBoxLayout, QHBoxLayout,
                             QWidget, QLabel, QComboBox, QSpinBox, QCheckBox,
                             QPushButton, QGroupBox, QFormLayout)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont


class SettingsDialog(QDialog):
    """Диалог настроек с вкладками"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки")
        self.setModal(True)
        self.resize(600, 500)
        self.setMinimumSize(500, 400)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Заголовок
        title = QLabel("⚙️ Настройки приложения")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Вкладки
        self.tabs = QTabWidget()
        self._create_security_tab()
        self._create_appearance_tab()
        self._create_advanced_tab()
        layout.addWidget(self.tabs)

        # Кнопки
        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("Сохранить")
        self.cancel_btn = QPushButton("Отмена")
        self.save_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.save_btn)
        layout.addLayout(btn_layout)

    def _create_security_tab(self):
        """Вкладка Безопасность"""
        security_widget = QWidget()
        layout = QVBoxLayout(security_widget)

        group = QGroupBox("Безопасность")
        form_layout = QFormLayout(group)

        # Таймаут буфера
        self.clipboard_timeout = QSpinBox()
        self.clipboard_timeout.setRange(5, 300)
        self.clipboard_timeout.setValue(30)
        self.clipboard_timeout.setSuffix(" сек")
        form_layout.addRow("Таймаут буфера:", self.clipboard_timeout)

        # Авто-блокировка
        self.auto_lock = QSpinBox()
        self.auto_lock.setRange(1, 60)
        self.auto_lock.setValue(5)
        self.auto_lock.setSuffix(" мин")
        form_layout.addRow("Авто-блокировка:", self.auto_lock)

        layout.addWidget(group)
        layout.addStretch()
        self.tabs.addTab(security_widget, "🔒 Безопасность")

    def _create_appearance_tab(self):
        """Вкладка Внешний вид"""
        appearance_widget = QWidget()
        layout = QVBoxLayout(appearance_widget)

        # Группа темы
        theme_group = QGroupBox("Тема")
        theme_layout = QVBoxLayout(theme_group)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Системная", "Темная", "Светлая"])
        self.theme_combo.setCurrentText("Системная")
        theme_layout.addWidget(QLabel("Выберите тему интерфейса:"))
        theme_layout.addWidget(self.theme_combo)
        layout.addWidget(theme_group)

        # Группа языка
        lang_group = QGroupBox("Язык")
        lang_layout = QVBoxLayout(lang_group)

        self.lang_combo = QComboBox()
        self.lang_combo.addItem("🇷🇺 Русский", "ru")
        self.lang_combo.addItem("🇺🇸 English", "en")
        self.lang_combo.setCurrentIndex(0)
        lang_layout.addWidget(QLabel("Язык интерфейса:"))
        lang_layout.addWidget(self.lang_combo)
        layout.addWidget(lang_group)

        layout.addStretch()
        self.tabs.addTab(appearance_widget, "🎨 Внешний вид")

    def _create_advanced_tab(self):
        """Вкладка Дополнительно"""
        advanced_widget = QWidget()
        layout = QVBoxLayout(advanced_widget)

        # Резервное копирование
        backup_group = QGroupBox("Резервное копирование")
        backup_layout = QVBoxLayout(backup_group)

        self.auto_backup = QCheckBox("Автоматическое создание резервных копий")
        self.backup_days = QSpinBox()
        self.backup_days.setRange(1, 30)
        self.backup_days.setValue(7)
        self.backup_days.setSuffix(" дней")
        backup_layout.addWidget(self.auto_backup)
        backup_layout.addWidget(QLabel("Интервал:"))
        backup_layout.addWidget(self.backup_days)
        layout.addWidget(backup_group)

        # Экспорт
        export_group = QGroupBox("Экспорт")
        export_layout = QVBoxLayout(export_group)

        self.export_encrypted = QCheckBox("Экспорт с шифрованием")
        self.export_encrypted.setChecked(True)
        export_layout.addWidget(self.export_encrypted)
        layout.addWidget(export_group)

        layout.addStretch()
        self.tabs.addTab(advanced_widget, "⚙️ Дополнительно")

    def get_settings(self):
        """Получить текущие настройки"""
        return {
            "security": {
                "clipboard_timeout": self.clipboard_timeout.value(),
                "auto_lock": self.auto_lock.value()
            },
            "appearance": {
                "theme": self.theme_combo.currentText(),
                "language": self.lang_combo.currentData()
            },
            "advanced": {
                "auto_backup": self.auto_backup.isChecked(),
                "backup_days": self.backup_days.value(),
                "export_encrypted": self.export_encrypted.isChecked()
            }
        }
