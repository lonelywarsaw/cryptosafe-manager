"""Read-only vault entries table with row selection. / Таблица записей хранилища только для чтения с выбором строк."""

from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeyEvent
from ..strings import t

COL_TITLE = 0
COL_LOGIN = 1
COL_URL = 2
COL_UPDATED = 3
COL_NOTES = 4
COL_PASSWORD = 5

TITLE_COLUMN_MIN_WIDTH = 160
UPDATED_AT_COLUMN_WIDTH = 165
PASSWORD_COLUMN_WIDTH = 118
NOTES_COLUMN_WIDTH = 90
URL_COLUMN_WIDTH = 100


class SecureTable(QTableWidget):
    """Sortable table for vault metadata without inline password editing. / Сортируемая таблица метаданных без редактирования пароля."""

    row_edit_requested = pyqtSignal()
    row_delete_requested = pyqtSignal()
    focus_search_requested = pyqtSignal()

    def __init__(self, parent=None):
        """Configures columns, headers, and row selection behavior. / Настраивает колонки, заголовки и выбор строк."""
        super().__init__(parent)
        # (спринт3) таблица: название, логин (маска), URL/domain, last modified, заметки, пароль
        self.setColumnCount(6)
        self.setHorizontalHeaderLabels(
            [t("title"), t("login"), t("url"), t("last_modified"), t("notes"), t("password_field")]
        )
        self.apply_column_layout()
        self.horizontalHeader().setSectionsMovable(True)  # (GUI-2)
        self.verticalHeader().setDefaultSectionSize(32)
        self.setSortingEnabled(True)  # (GUI-1)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)  # (GUI-2)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setTabKeyNavigation(False)
        self.setAccessibleName(t("vault_table_accessible"))

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        mods = event.modifiers()
        no_mod = mods == Qt.KeyboardModifier.NoModifier
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and no_mod:
            if self.currentRow() >= 0:
                self.row_edit_requested.emit()
                event.accept()
                return
        if key == Qt.Key.Key_F2:
            if self.currentRow() >= 0:
                self.row_edit_requested.emit()
                event.accept()
                return
        if key == Qt.Key.Key_Delete and no_mod:
            if self.currentRow() >= 0 or self.selectedItems():
                self.row_delete_requested.emit()
                event.accept()
                return
        if key in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab) and no_mod:
            self.focus_search_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def apply_column_layout(self) -> None:
        """Column layout: title stretches; compact password column."""
        header = self.horizontalHeader()
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(40)
        header.setSectionResizeMode(COL_TITLE, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_LOGIN, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_URL, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(COL_UPDATED, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(COL_NOTES, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(COL_PASSWORD, QHeaderView.ResizeMode.Fixed)
        self.setColumnWidth(COL_TITLE, max(self.columnWidth(COL_TITLE), TITLE_COLUMN_MIN_WIDTH))
        self.setColumnWidth(COL_URL, URL_COLUMN_WIDTH)
        self.setColumnWidth(COL_UPDATED, UPDATED_AT_COLUMN_WIDTH)
        self.setColumnWidth(COL_NOTES, NOTES_COLUMN_WIDTH)
        self.setColumnWidth(COL_PASSWORD, PASSWORD_COLUMN_WIDTH)

    def set_placeholder_data(self, rows=None):
        """Fills the table with demo rows when the vault is empty. / Заполняет таблицу демо-строками при пустом хранилище."""
        if rows is None:
            rows = [
                ("Пример 1", "user1", "example.com", "—", "Заметка", "••••••••"),
                ("Пример 2", "user2", "site.ru", "—", "", "••••••••"),
            ]
        self.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, cell in enumerate(row):
                self.setItem(i, j, QTableWidgetItem(str(cell)))
