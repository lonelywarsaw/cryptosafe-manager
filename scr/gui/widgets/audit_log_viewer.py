from PyQt6.QtWidgets import QWidget, QTableWidget, QVBoxLayout, QHeaderView, QLabel

class AuditLogViewer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Журнал событий"))
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Время", "Действие", "Подробности"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

    def set_entries(self, entries):
        self.table.setRowCount(0)
        for e in entries:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, _item(e.get("timestamp", "")))
            self.table.setItem(row, 1, _item(e.get("action", "")))
            self.table.setItem(row, 2, _item(e.get("details", "")))

def _item(text):
    from PyQt6.QtWidgets import QTableWidgetItem
    return QTableWidgetItem(str(text) if text is not None else "")
