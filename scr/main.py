# Отсюда всё стартует. Включаем тему, при первом запуске — мастер настройки, потом всегда спрашиваем пароль.

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication

from core import config
from core import events
from core.audit import register as register_audit
from database import db as database_db
from gui.theme import apply_theme
from gui.main_window import MainWindow
from gui.setup_wizard import SetupWizard
from gui.unlock_dialog import UnlockDialog


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("CryptoSafe Manager")
    apply_theme(app)
    database_db.set_db_path(config.get(config.DB_PATH))
    database_db.init_db()
    register_audit()

    if not config.get(config.DB_PATH) or not config.get(config.MASTER_PASSWORD_HASH):
        wiz = SetupWizard()
        if not wiz.exec():
            return 0
        database_db.set_db_path(config.get(config.DB_PATH))
        if config.get(config.DB_PATH):
            database_db.init_db()

    unlock = UnlockDialog()
    if not unlock.exec():
        return 0

    events.publish(events.UserLoggedIn, sync=True)

    win = MainWindow()
    win.set_locked(False)
    win.show()

    def on_quit():
        events.publish(events.UserLoggedOut, sync=True)
        events.shutdown()
    app.aboutToQuit.connect(on_quit)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
