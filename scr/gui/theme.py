from PyQt6.QtWidgets import QApplication

def apply_theme(app_or_widget, theme_name):
    app = QApplication.instance() if app_or_widget is None else (app_or_widget if isinstance(app_or_widget, QApplication) else QApplication.instance())
    if app is None:
        return
    if theme_name == "dark":
        app.setStyleSheet("""
            QMainWindow, QDialog, QWidget { background-color: #2d2d2d; color: #e0e0e0; }
            QMenuBar { background-color: #2d2d2d; color: #e0e0e0; }
            QMenuBar::item:selected { background-color: #404040; }
            QTableWidget { background-color: #3d3d3d; color: #e0e0e0; gridline-color: #505050; }
            QHeaderView::section { background-color: #404040; color: #e0e0e0; }
            QLineEdit, QSpinBox, QComboBox { background-color: #3d3d3d; color: #e0e0e0; border: 1px solid #505050; }
            QPushButton { background-color: #404040; color: #e0e0e0; }
            QPushButton:hover { background-color: #505050; }
            QTabWidget::pane { background-color: #2d2d2d; }
            QTabBar::tab { background-color: #404040; color: #e0e0e0; }
            QTabBar::tab:selected { background-color: #2d2d2d; }
            QStatusBar { background-color: #2d2d2d; color: #e0e0e0; }
        """)
    elif theme_name == "system":
        app.setStyleSheet("")
        app.setStyle("Fusion")
    else:
        app.setStyleSheet("""
            QMainWindow, QDialog, QWidget { background-color: #f0f0f0; color: #000000; }
            QMenuBar { background-color: #f0f0f0; color: #000000; }
            QMenuBar::item:selected { background-color: #e0e0e0; }
            QTableWidget { background-color: #ffffff; color: #000000; gridline-color: #d0d0d0; }
            QHeaderView::section { background-color: #e8e8e8; color: #000000; }
            QLineEdit, QSpinBox, QComboBox { background-color: #ffffff; color: #000000; border: 1px solid #c0c0c0; }
            QPushButton { background-color: #e8e8e8; color: #000000; }
            QPushButton:hover { background-color: #d8d8d8; }
            QTabWidget::pane { background-color: #f0f0f0; }
            QTabBar::tab { background-color: #e8e8e8; color: #000000; }
            QTabBar::tab:selected { background-color: #f0f0f0; }
            QStatusBar { background-color: #f0f0f0; color: #000000; }
        """)
        app.setStyle("Fusion")
