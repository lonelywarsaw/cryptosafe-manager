# точка входа: создаётся приложение, применяется тема, инициализируются бд и аудит
# при первом запуске показывается мастер настройки, затем окно ввода пароля, затем главное окно

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication, QMessageBox

from core import config
from core import events
from core.audit import register as register_audit
from core.audit import verify_integrity
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

    # спринт 2: первый запуск — если нет пути к бд или нет auth_hash в key_store, показываем мастер настройки
    if not config.get(config.DB_PATH) or not database_db.get_key_store("auth_hash"):
        wiz = SetupWizard()
        if not wiz.exec():
            return 0
        database_db.set_db_path(config.get(config.DB_PATH))
        if config.get(config.DB_PATH):
            database_db.init_db()

    unlock = UnlockDialog()
    if not unlock.exec():
        return 0

    # UserLoggedIn уже публикуется в unlock_dialog после успешного входа (спринт 2)

    try:
        audit_check = verify_integrity(sample_limit=1000)
        if not audit_check.get("verified") and "pytest" not in sys.modules:
            from gui.strings import t
            QMessageBox.warning(
                None,
                t("audit_tamper_title"),
                t("audit_tamper_message"),
            )
    except Exception:
        pass

    win = MainWindow()
    win.set_locked(False)
    win.show()

    def on_quit():
        from core.key_manager import clear_encryption_key
        clear_encryption_key()
        events.publish(events.UserLoggedOut, sync=True)
        events.shutdown()
    app.aboutToQuit.connect(on_quit)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
