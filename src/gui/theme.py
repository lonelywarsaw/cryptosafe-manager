"""Qt theme application: system, dark, or light Fusion palette. / Применение темы Qt: системная, тёмная или светлая Fusion."""

import os
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication, QVBoxLayout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import config

DIALOG_MARGINS = (24, 24, 24, 24)
DIALOG_SPACING = 12


def apply_dialog_layout(layout: QVBoxLayout) -> None:
    """Applies standard dialog margins and spacing. / Задаёт стандартные отступы и интервалы диалога."""
    layout.setContentsMargins(*DIALOG_MARGINS)
    layout.setSpacing(DIALOG_SPACING)


def _normalize_theme_name(raw: str) -> str:
    value = (raw or "system").strip().lower()
    aliases = {
        "тёмная": "dark",
        "темная": "dark",
        "светлая": "light",
        "системная": "system",
        "dark": "dark",
        "light": "light",
        "system": "system",
    }
    return aliases.get(value, value if value in ("dark", "light", "system") else "system")


def _system_prefers_dark() -> bool:
    try:
        from PyQt6.QtGui import QGuiApplication

        hints = QGuiApplication.styleHints()
        scheme = hints.colorScheme()
        return scheme == Qt.ColorScheme.Dark
    except Exception:
        pass
    if sys.platform == "win32":
        try:
            import winreg

            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            )
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return int(value) == 0
        except Exception:
            return False
    return False


def _build_palette(*, dark: bool) -> QPalette:
    palette = QPalette()
    if dark:
        window = QColor(53, 53, 53)
        base = QColor(35, 35, 35)
        alt = QColor(45, 45, 45)
        text = QColor(255, 255, 255)
        button = QColor(53, 53, 53)
        highlight = QColor(42, 130, 218)
    else:
        window = QColor(240, 240, 240)
        base = QColor(255, 255, 255)
        alt = QColor(245, 245, 245)
        text = QColor(0, 0, 0)
        button = QColor(240, 240, 240)
        highlight = QColor(42, 130, 218)

    roles = (
        QPalette.ColorRole.Window,
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Base,
        QPalette.ColorRole.AlternateBase,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.Button,
        QPalette.ColorRole.ButtonText,
        QPalette.ColorRole.ToolTipBase,
        QPalette.ColorRole.ToolTipText,
        QPalette.ColorRole.Highlight,
        QPalette.ColorRole.HighlightedText,
    )
    values = {
        QPalette.ColorRole.Window: window,
        QPalette.ColorRole.WindowText: text,
        QPalette.ColorRole.Base: base,
        QPalette.ColorRole.AlternateBase: alt,
        QPalette.ColorRole.Text: text,
        QPalette.ColorRole.Button: button,
        QPalette.ColorRole.ButtonText: text,
        QPalette.ColorRole.ToolTipBase: base,
        QPalette.ColorRole.ToolTipText: text,
        QPalette.ColorRole.Highlight: highlight,
        QPalette.ColorRole.HighlightedText: QColor(255, 255, 255),
    }
    for group in (
        QPalette.ColorGroup.Active,
        QPalette.ColorGroup.Inactive,
        QPalette.ColorGroup.Disabled,
    ):
        for role in roles:
            palette.setColor(group, role, values[role])
    return palette


def _base_stylesheet(*, dark: bool) -> str:
    if dark:
        bg, bg_alt, text, border, input_bg = "#353535", "#2a2a2a", "#ffffff", "#555555", "#232323"
    else:
        bg, bg_alt, text, border, input_bg = "#f0f0f0", "#ffffff", "#000000", "#cccccc", "#ffffff"
    highlight = "#2a82da"
    return f"""
        QWidget {{
            font-family: "Segoe UI", "SF Pro Text", "Ubuntu", sans-serif;
            font-size: 10pt;
            background-color: {bg_alt};
            color: {text};
        }}
        QMainWindow, QDialog, QMessageBox {{
            background-color: {bg_alt};
            color: {text};
        }}
        QLabel {{
            background-color: transparent;
            color: {text};
        }}
        QGroupBox {{
            font-weight: 600;
            margin-top: 12px;
            padding-top: 8px;
            color: {text};
            border: 1px solid {border};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 8px;
            padding: 0 6px;
            color: {text};
        }}
        QPushButton {{
            min-height: 28px;
            padding: 6px 14px;
            border: 1px solid {border};
            border-radius: 4px;
            background-color: {bg};
            color: {text};
        }}
        QPushButton:hover {{
            border-color: {highlight};
        }}
        QPushButton:default {{
            border: 2px solid {highlight};
        }}
        QTableWidget QToolButton#passwordToggleBtn {{
            min-height: 20px;
            max-height: 22px;
            min-width: 44px;
            max-width: 48px;
            padding: 1px 4px;
            font-size: 9pt;
        }}
        QLineEdit, QSpinBox, QComboBox, QTextEdit, QPlainTextEdit {{
            min-height: 26px;
            padding: 4px 8px;
            background-color: {input_bg};
            color: {text};
            border: 1px solid {border};
            border-radius: 3px;
        }}
        QComboBox QAbstractItemView {{
            background-color: {input_bg};
            color: {text};
            selection-background-color: {highlight};
            selection-color: #ffffff;
        }}
        QTableWidget, QTreeWidget {{
            background-color: {input_bg};
            color: {text};
            gridline-color: {border};
            alternate-background-color: {bg};
        }}
        QTableWidget::item:selected, QTreeWidget::item:selected {{
            background-color: {highlight};
            color: #ffffff;
        }}
        QHeaderView::section {{
            background-color: {bg};
            color: {text};
            padding: 6px;
            border: 1px solid {border};
        }}
        QStatusBar, QToolBar {{
            background-color: {bg};
            color: {text};
        }}
        QMenuBar {{
            background-color: {bg};
            color: {text};
        }}
        QMenuBar::item {{
            color: {text};
            padding: 4px 8px;
            background-color: transparent;
        }}
        QMenuBar::item:selected {{
            background-color: {highlight};
            color: #ffffff;
        }}
        QMenu {{
            background-color: {bg};
            color: {text};
        }}
        QMenu::item {{
            color: {text};
            padding: 6px 24px;
        }}
        QMenu::item:selected {{
            background-color: {highlight};
            color: #ffffff;
        }}
        QCheckBox, QRadioButton {{
            color: {text};
            spacing: 6px;
        }}
        QTabWidget::pane {{
            border: 1px solid {border};
            background-color: {bg_alt};
        }}
        QTabBar::tab {{
            background-color: {bg};
            color: {text};
            padding: 6px 12px;
            border: 1px solid {border};
        }}
        QTabBar::tab:selected {{
            background-color: {highlight};
            color: #ffffff;
        }}
    """


def _resolve_dark_flag(theme: str) -> bool:
    if theme == "dark":
        return True
    if theme == "light":
        return False
    return _system_prefers_dark()


def apply_theme(app):
    """Applies configured theme palette and stylesheets to the app. / Применяет палитру и стили темы из конфигурации к приложению."""
    theme = _normalize_theme_name(config.get(config.THEME, "system"))
    use_dark = _resolve_dark_flag(theme)

    app.setStyle("Fusion")
    app.setPalette(_build_palette(dark=use_dark))
    app.setStyleSheet(_base_stylesheet(dark=use_dark))
