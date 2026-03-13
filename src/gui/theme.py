# Подключаем тему — как в системе, тёмная или светлая.

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtCore import Qt

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import config


def apply_theme(app):
    theme = config.get(config.THEME, "system") or "system"
    if theme == "dark":
        app.setStyle("Fusion")
        palette = QPalette()
        dark_bg = QColor(53, 53, 53)
        darker_bg = QColor(35, 35, 35)
        white = QColor(255, 255, 255)
        highlight = QColor(42, 130, 218)
        palette.setColor(QPalette.ColorRole.Window, dark_bg)
        palette.setColor(QPalette.ColorRole.WindowText, white)
        palette.setColor(QPalette.ColorRole.Base, darker_bg)
        palette.setColor(QPalette.ColorRole.AlternateBase, dark_bg)
        palette.setColor(QPalette.ColorRole.Text, white)
        palette.setColor(QPalette.ColorRole.Button, dark_bg)
        palette.setColor(QPalette.ColorRole.ButtonText, white)
        palette.setColor(QPalette.ColorRole.Highlight, highlight)
        palette.setColor(QPalette.ColorRole.HighlightedText, white)
        palette.setColor(QPalette.ColorRole.ToolTipBase, darker_bg)
        palette.setColor(QPalette.ColorRole.ToolTipText, white)
        palette.setColor(QPalette.ColorGroup.Inactive, QPalette.ColorRole.Window, dark_bg)
        palette.setColor(QPalette.ColorGroup.Inactive, QPalette.ColorRole.WindowText, white)
        palette.setColor(QPalette.ColorGroup.Inactive, QPalette.ColorRole.Highlight, highlight)
        palette.setColor(QPalette.ColorGroup.Inactive, QPalette.ColorRole.HighlightedText, white)
        app.setPalette(palette)
        app.setStyleSheet("""
            QMenuBar { background-color: #353535; color: #ffffff; }
            QMenuBar::item { color: #ffffff; padding: 4px 8px; }
            QMenuBar::item:selected { background-color: #2a82da; color: #ffffff; }
            QMenu { background-color: #353535; color: #ffffff; }
            QMenu::item { color: #ffffff; padding: 6px 24px; }
            QMenu::item:selected { background-color: #2a82da; color: #ffffff; }
            QLineEdit { background-color: #232323; color: #ffffff; border: 1px solid #555555; padding: 4px; }
        """)
    elif theme == "light":
        app.setStyle("Fusion")
        palette = QPalette()
        light_bg = QColor(240, 240, 240)
        white = QColor(255, 255, 255)
        black = QColor(0, 0, 0)
        highlight = QColor(42, 130, 218)
        palette.setColor(QPalette.ColorRole.Window, light_bg)
        palette.setColor(QPalette.ColorRole.WindowText, black)
        palette.setColor(QPalette.ColorRole.Base, white)
        palette.setColor(QPalette.ColorRole.AlternateBase, light_bg)
        palette.setColor(QPalette.ColorRole.Text, black)
        palette.setColor(QPalette.ColorRole.Button, light_bg)
        palette.setColor(QPalette.ColorRole.ButtonText, black)
        palette.setColor(QPalette.ColorRole.Highlight, highlight)
        palette.setColor(QPalette.ColorRole.HighlightedText, white)
        palette.setColor(QPalette.ColorRole.ToolTipBase, white)
        palette.setColor(QPalette.ColorRole.ToolTipText, black)
        palette.setColor(QPalette.ColorGroup.Inactive, QPalette.ColorRole.Window, light_bg)
        palette.setColor(QPalette.ColorGroup.Inactive, QPalette.ColorRole.WindowText, black)
        palette.setColor(QPalette.ColorGroup.Inactive, QPalette.ColorRole.Highlight, highlight)
        palette.setColor(QPalette.ColorGroup.Inactive, QPalette.ColorRole.HighlightedText, white)
        app.setPalette(palette)
        app.setStyleSheet("""
            QMenuBar { background-color: #f0f0f0; color: #000000; }
            QMenuBar::item { color: #000000; padding: 4px 8px; }
            QMenuBar::item:selected { background-color: #2a82da; color: #ffffff; }
            QMenu { background-color: #f0f0f0; color: #000000; }
            QMenu::item { color: #000000; padding: 6px 24px; }
            QMenu::item:selected { background-color: #2a82da; color: #ffffff; }
            QLineEdit { background-color: #ffffff; color: #000000; border: 1px solid #cccccc; padding: 4px; }
        """)
    else:
        app.setStyle("Fusion")
        app.setStyleSheet("")
        app.setPalette(QApplication.style().standardPalette())
