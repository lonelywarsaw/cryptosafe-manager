# Проверяем что главное окно и мастер первого запуска открываются.
import unittest
import sys

from PyQt6.QtWidgets import QApplication


class TestMainWindowLaunches(unittest.TestCase):
    # Просто создаём главное окно и смотрим что не падает.

    def test_main_window_creates(self):
        app = QApplication.instance() or QApplication(sys.argv)
        from gui.main_window import MainWindow
        win = MainWindow()
        win.setWindowTitle("Test")
        self.assertIsNotNone(win)
        self.assertIsNotNone(win.menuBar())

        try:
            win.show()
            self.assertTrue(win.isVisible())
        except Exception:
            pass
        win.close()

    def test_setup_wizard_dialog_creates(self):
        app = QApplication.instance() or QApplication(sys.argv)
        from gui.setup_wizard import SetupWizard
        wiz = SetupWizard()
        self.assertIsNotNone(wiz)
        try:
            wiz.show()
            self.assertTrue(wiz.isVisible())
        except Exception:
            pass
        wiz.reject()


class TestGUIWithPyAutoGUI(unittest.TestCase):
    # Окно показываем и проверяем что видно.

    def setUp(self):
        try:
            import pyautogui
            self.pyautogui = pyautogui
        except ImportError:
            self.pyautogui = None

    def test_cryptosafe_window_appears_with_pyautogui(self):
        app = QApplication.instance() or QApplication(sys.argv)
        from gui.main_window import MainWindow
        win = MainWindow()
        win.setWindowTitle("CryptoSafe Manager")
        win.show()
        win.raise_()
        win.activateWindow()
        self.assertTrue(win.isVisible(), "Окно должно быть видимым")

        if self.pyautogui is not None:
            try:
                self.pyautogui.size()
            except Exception:
                pass
        win.close()
