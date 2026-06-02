# Поиск и загрузка иконки приложения (assets/icon.ico или icon.png)

import os
import sys
from typing import Optional

from PyQt6.QtGui import QIcon


def resource_root() -> str:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def find_icon_path() -> Optional[str]:
    root = resource_root()
    for rel in ("assets/icon.ico", "assets/icon.png"):
        path = os.path.join(root, rel)
        if os.path.isfile(path):
            return path
    return None


def load_app_icon() -> Optional[QIcon]:
    path = find_icon_path()
    if not path:
        return None
    icon = QIcon(path)
    return icon if not icon.isNull() else None
