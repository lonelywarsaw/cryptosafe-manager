# таблица записей хранилища: колонки название, логин, url, заметки (пароль в таблице не показывается)
# выбор по строкам, редактирование через диалог добавления/редактирования

from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem
from PyQt6.QtCore import Qt


class SecureTable(QTableWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(4)
        self.setHorizontalHeaderLabels(["Название", "Логин", "URL", "Заметки"])
        self.horizontalHeader().setStretchLastSection(True)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

    def set_placeholder_data(self, rows=None):
        # таблица заполняется тестовыми строками (для демо или когда записей ещё нет)
        if rows is None:
            rows = [
                ("Пример 1", "user1", "https://example.com", "Заметка"),
                ("Пример 2", "user2", "https://site.ru", ""),
            ]
        self.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, cell in enumerate(row):
                self.setItem(i, j, QTableWidgetItem(str(cell)))
