import sys
from pathlib import Path
root = Path(__file__).resolve().parent
if str(root) not in sys.path:
    sys.path.insert(0, str(root))
from PyQt6.QtWidgets import QApplication
from src.gui.main_window import MainWindow
def main():
    app = QApplication(sys.argv)
    w = MainWindow()
    w.run()
if __name__ == "__main__":
    main()
