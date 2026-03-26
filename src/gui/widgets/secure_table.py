# таблица записей хранилища: колонки название, логин, url, заметки (пароль в таблице не показывается)
# выбор по строкам, редактирование через диалог добавления/редактирования

from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
from PyQt6.QtCore import Qt


class SecureTable(QTableWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        # (спринт3) таблица: название, логин (маска), URL/domain, last modified, заметки, пароль
        self.setColumnCount(6)
        self.setHorizontalHeaderLabels(["Название", "Логин", "URL", "Последнее изменение", "Заметки", "Пароль"])
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setSectionsMovable(True)  # (GUI-2)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)  # (GUI-2)
        self.setSortingEnabled(True)  # (GUI-1)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)  # (GUI-2)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

    def set_placeholder_data(self, rows=None):
        # таблица заполняется тестовыми строками (для демо или когда записей ещё нет)
        if rows is None:
            rows = [
                ("Пример 1", "user1", "example.com", "—", "Заметка", "••••••••"),
                ("Пример 2", "user2", "site.ru", "—", "", "••••••••"),
            ]
        self.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, cell in enumerate(row):
                self.setItem(i, j, QTableWidgetItem(str(cell)))
