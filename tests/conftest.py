# Настройка pytest — добавляем src в путь чтобы импорты работали.
import os
import sys

# Чтобы импортировать core, database, gui.
_here = os.path.dirname(os.path.abspath(__file__))
_src = os.path.join(os.path.dirname(_here), "src")
if _src not in sys.path:
    sys.path.insert(0, _src)
