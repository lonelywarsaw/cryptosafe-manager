# добавляем src в путь, чтобы импорты core, database, gui работали
import os
import sys

_here = os.path.dirname(os.path.abspath(__file__))
_src = os.path.join(os.path.dirname(_here), "src")
if _src not in sys.path:
    sys.path.insert(0, _src)
