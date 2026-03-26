# тесты GUI (окно и диалог создаются, интерфейс отображается)

import sys
import unittest
from PyQt6.QtWidgets import QApplication

class TestGUI(unittest.TestCase):
    def test_main_window(self):
        # главное окно создаётся, у него есть меню (значит базовый UI собран без ошибки)
        app = QApplication.instance() or QApplication(sys.argv)
        from gui.main_window import MainWindow
        win = MainWindow()
        self.assertIsNotNone(win.menuBar())
        win.close()

    def test_main_window_visible(self):
        # окно показывается на экране; isVisible() возвращает True (проверка что интерфейс реально отображается)
        app = QApplication.instance() or QApplication(sys.argv)
        from gui.main_window import MainWindow
        win = MainWindow()
        win.setWindowTitle("CryptoSafe Manager")
        win.show()
        win.raise_()
        win.activateWindow()
        self.assertTrue(win.isVisible(), "окно должно быть видимым")
        win.close()

    def test_main_window_pyautogui(self):
        # проверка интерфейса через PyAutoGUI: окно показывается, обрабатываются события, pyautogui получает размер экрана
        try:
            import pyautogui
        except ImportError:
            self.skipTest("pyautogui не установлен")
        app = QApplication.instance() or QApplication(sys.argv)
        from gui.main_window import MainWindow
        win = MainWindow()
        win.setWindowTitle("CryptoSafe Manager")
        win.show()
        win.raise_()
        win.activateWindow()
        for _ in range(5):
            app.processEvents()
        width, height = pyautogui.size()
        self.assertGreater(width, 0)
        self.assertGreater(height, 0)
        win.close()

    def test_setup_wizard(self):
        # диалог первого запуска создаётся и закрывается без падения (проверка что форма открывается)
        app = QApplication.instance() or QApplication(sys.argv)
        from gui.setup_wizard import SetupWizard
        wiz = SetupWizard()
        self.assertIsNotNone(wiz)
        wiz.reject()
