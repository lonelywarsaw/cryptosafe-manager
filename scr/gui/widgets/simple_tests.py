import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QTableWidget, QTableWidgetItem, QStatusBar, \
    QMenuBar, QMenu, QAction


class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TEST")
        self.setGeometry(100, 100, 600, 400)

        menubar = self.menuBar()
        help_menu = menubar.addMenu("Справка")
        about = QAction("О программе", self)
        about.triggered.connect(self.about)
        help_menu.addAction(about)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        table = QTableWidget(5, 3)
        table.setHorizontalHeaderLabels(["ID", "Site", "User"])
        layout.addWidget(table)

        status = QStatusBar()
        status.showMessage("Готов")
        self.setStatusBar(status)

    def about(self):
        self.statusBar().showMessage("TEST OK", 5000)
        print("TEST WORKS!")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = TestWindow()
    win.show()
    sys.exit(app.exec_())
