"""Application icon discovery and loading from bundled assets. / Поиск и загрузка иконки приложения из ресурсов."""

import os
import sys
from typing import Optional

from PyQt6.QtGui import QIcon


def resource_root() -> str:
    """Returns project or PyInstaller bundle root for assets. / Возвращает корень проекта или bundle PyInstaller для ресурсов."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def find_icon_path() -> Optional[str]:
    """Locates icon.ico or icon.png under assets if present. / Находит icon.ico или icon.png в assets, если файл есть."""
    root = resource_root()
    for rel in ("assets/icon.ico", "assets/icon.png"):
        path = os.path.join(root, rel)
        if os.path.isfile(path):
            return path
    return None


def load_app_icon() -> Optional[QIcon]:
    """Loads QIcon from the first available asset path. / Загружает QIcon из первого доступного пути к ресурсу."""
    path = find_icon_path()
    if not path:
        return None
    icon = QIcon(path)
    return icon if not icon.isNull() else None
