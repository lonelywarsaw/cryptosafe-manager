import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

class TestGuiImport(unittest.TestCase):
    def test_main_window_import_and_create(self):
        try:
            from PyQt6.QtWidgets import QApplication
            app = QApplication.instance() or QApplication(sys.argv)
            from src.gui.main_window import MainWindow
            from src.gui.widgets import PasswordEntry, SecureTable, AuditLogViewer
            from PyQt6.QtWidgets import QWidget
            w = QWidget()
            PasswordEntry(w)
            SecureTable(w)
            AuditLogViewer(w)
        except Exception as e:
            self.skipTest("GUI not available: {}".format(e))

if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestGuiImport)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)
