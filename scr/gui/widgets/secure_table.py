from PyQt6.QtWidgets import QWidget, QTableWidget, QVBoxLayout, QHeaderView
from PyQt6.QtCore import Qt

class SecureTable(QWidget):
    def __init__(self, parent=None, columns=None):
        super().__init__(parent)
        self.cols = columns or ["Название", "Пользователь", "URL", "Изменено"]
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.table = QTableWidget()
        self.table.setColumnCount(len(self.cols))
        self.table.setHorizontalHeaderLabels(self.cols)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        layout.addWidget(self.table)
        self._on_select_callback = None
        self.table.itemSelectionChanged.connect(self._on_select)

    def _on_select(self):
        if self._on_select_callback:
            self._on_select_callback()

    def clear(self):
        self.table.setRowCount(0)

    def set_rows(self, rows):
        self.clear()
        for r in rows:
            row = self.table.rowCount()
            self.table.insertRow(row)
            it0 = _cell(r.get("title", ""))
            it0.setData(Qt.ItemDataRole.UserRole, r.get("id"))
            self.table.setItem(row, 0, it0)
            self.table.setItem(row, 1, _cell(r.get("username", "")))
            self.table.setItem(row, 2, _cell(r.get("url", "")))
            updated = r.get("updated_at", "") or ""
            if isinstance(updated, str) and len(updated) > 19:
                updated = updated[:19]
            self.table.setItem(row, 3, _cell(updated))

    def get_selected_id(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if item is None:
            return None
        uid = item.data(Qt.ItemDataRole.UserRole)
        return str(uid) if uid is not None else None

    def on_select(self, callback):
        self._on_select_callback = callback

def _cell(text):
    from PyQt6.QtWidgets import QTableWidgetItem
    return QTableWidgetItem(str(text) if text is not None else "")
