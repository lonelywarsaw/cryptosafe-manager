from pathlib import Path
from typing import Optional
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QMessageBox, QFileDialog,
    QDialog, QGridLayout, QLabel, QLineEdit, QPushButton, QApplication,
)
from PyQt6.QtCore import Qt
from src.core.config import get_config
from src.core.state_manager import StateManager
from src.core.key_manager import KeyManager
from src.core.crypto.placeholder import AES256Placeholder
from src.database.db import Database
from src.database.vault import get_entries, insert_entry, update_entry, delete_entry
from src.database.audit import register_audit_handlers
from src.core.events import event_bus, entry_added, entry_updated, entry_deleted
from src.gui.widgets import SecureTable, PasswordEntry
from src.gui.setup_wizard import SetupWizard
from src.gui.settings_dialog import SettingsDialog
from src.gui.widgets.audit_log_viewer import AuditLogViewer
from src.gui.theme import apply_theme
from src.gui.i18n import t, set_config

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.resize(800, 500)
        self.setMinimumSize(400, 300)
        self.config = get_config()
        set_config(self.config)
        self.state = StateManager()
        self.key_manager = KeyManager()
        self.crypto = AES256Placeholder()
        self.db = None
        self._key = None
        self._setup_done = False
        self._build_ui()
        apply_theme(None, self.config.theme)
        self._check_first_run()

    def _build_ui(self):
        menubar = self.menuBar()
        self._menus = []
        self._actions = []
        file_menu = menubar.addMenu(t("menu_file"))
        self._menus.append((file_menu, "menu_file"))
        self._actions.append((file_menu.addAction(t("menu_new"), self._on_new), "menu_new"))
        self._actions.append((file_menu.addAction(t("menu_open"), self._on_open), "menu_open"))
        self._actions.append((file_menu.addAction(t("menu_backup"), self._on_backup), "menu_backup"))
        file_menu.addSeparator()
        self._actions.append((file_menu.addAction(t("menu_exit"), QApplication.quit), "menu_exit"))
        edit_menu = menubar.addMenu(t("menu_edit"))
        self._menus.append((edit_menu, "menu_edit"))
        self._actions.append((edit_menu.addAction(t("menu_add"), self._on_add), "menu_add"))
        self._actions.append((edit_menu.addAction(t("menu_edit_entry"), self._on_edit), "menu_edit_entry"))
        self._actions.append((edit_menu.addAction(t("menu_delete"), self._on_delete), "menu_delete"))
        view_menu = menubar.addMenu(t("menu_view"))
        self._menus.append((view_menu, "menu_view"))
        self._actions.append((view_menu.addAction(t("menu_logs"), self._on_view_logs), "menu_logs"))
        self._actions.append((view_menu.addAction(t("menu_settings"), self._on_settings), "menu_settings"))
        help_menu = menubar.addMenu(t("menu_help"))
        self._menus.append((help_menu, "menu_help"))
        self._actions.append((help_menu.addAction(t("menu_about"), self._on_about), "menu_about"))
        self.setWindowTitle(t("title_main"))
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        self.table = SecureTable(self)
        self.table.on_select(self._refresh_status)
        layout.addWidget(self.table)
        self.statusBar().showMessage(t("status_locked"))

    def update_ui_language(self):
        self.setWindowTitle(t("title_main"))
        for menu, key in self._menus:
            menu.setTitle(t(key))
        for action, key in self._actions:
            action.setText(t(key))
        self._refresh_status()

    def _check_first_run(self):
        db_path = self.config.database_path
        if not db_path.exists():
            w = SetupWizard(self, on_done=self._on_setup_done)
            w.exec()
        else:
            self._show_unlock()

    def _on_setup_done(self, master_password: str, db_path: Path):
        self.config.set_database_path(db_path)
        salt = self.key_manager.generate_salt()
        self._key = self.key_manager.derive_key(master_password, salt)
        self.db = Database(db_path)
        self.db.init_schema()
        import base64
        with self.db.cursor() as cur:
            cur.execute("DELETE FROM settings WHERE setting_key = ?", ("master_salt",))
            cur.execute(
                "INSERT INTO settings (setting_key, setting_value, encrypted) VALUES (?, ?, 0)",
                ("master_salt", base64.b64encode(salt).decode()),
            )
        register_audit_handlers(self.db)
        self.config.load_from_db(self.db)
        self.state.set_locked(False)
        self._setup_done = True
        self._refresh_table()
        self._refresh_status()

    def _show_unlock(self):
        dlg = QDialog(self)
        dlg.setWindowTitle(t("dlg_unlock_title"))
        dlg.setMinimumSize(380, 180)
        dlg.resize(380, 180)
        layout = QVBoxLayout(dlg)
        layout.addWidget(QLabel(t("label_master_pw")))
        pw = PasswordEntry(dlg)
        layout.addWidget(pw)
        layout.addSpacing(12)
        btn = QPushButton(t("btn_unlock"))
        def ok():
            p = pw.get()
            if not p:
                return
            self.db = Database(self.config.database_path)
            if not self.config.database_path.exists():
                self.db.init_schema()
            row = self.db.fetchone("SELECT setting_value FROM settings WHERE setting_key = ?", ("master_salt",))
            if row and row[0]:
                import base64
                try:
                    salt = base64.b64decode(row[0])
                    self._key = self.key_manager.derive_key(p, salt)
                except Exception:
                    QMessageBox.critical(dlg, t("dlg_unlock_title"), t("msg_unlock_invalid"))
                    return
            else:
                QMessageBox.critical(dlg, t("dlg_unlock_title"), t("msg_unlock_no_salt"))
                return
            register_audit_handlers(self.db)
            self.config.load_from_db(self.db)
            self.state.set_locked(False)
            self._refresh_table()
            self._refresh_status()
            dlg.accept()
        btn.clicked.connect(ok)
        layout.addWidget(btn)
        dlg.exec()

    def _refresh_table(self):
        if not self.db or self.state.is_locked():
            return
        rows = get_entries(self.db)
        self.table.set_rows(rows)

    def _refresh_status(self):
        if self.state.is_locked():
            self.statusBar().showMessage(t("status_locked"))
        else:
            clip = self.state.get_clipboard_timer_remaining()
            clip_str = f"{int(clip)}" if clip is not None else "--"
            self.statusBar().showMessage(t("status_unlocked").format(clip_str))

    def _on_new(self):
        self.config.set_database_path(self.config.config_dir / "cryptosafe.db")
        self._check_first_run()

    def _on_open(self):
        path, _ = QFileDialog.getOpenFileName(self, t("menu_open"), "", "База данных (*.db)")
        if path:
            self.config.set_database_path(path)
            if self.db:
                self.db.close()
            self._show_unlock()

    def _on_backup(self):
        from src.database.db import backup_database
        if not self.db:
            QMessageBox.information(self, t("menu_backup"), t("msg_backup_first"))
            return
        path, _ = QFileDialog.getSaveFileName(self, t("menu_backup"), "", "База данных (*.db)")
        if path:
            backup_database(Path(self.config.database_path), Path(path))
            QMessageBox.information(self, t("menu_backup"), t("msg_backup_saved"))

    def _on_add(self):
        if self.state.is_locked() or not self.db or not self._key:
            QMessageBox.warning(self, t("menu_add"), t("msg_unlock_first"))
            return
        self._entry_dialog(None)

    def _on_edit(self):
        if self.state.is_locked() or not self.db or not self._key:
            QMessageBox.warning(self, t("menu_edit_entry"), t("msg_unlock_first"))
            return
        eid = self.table.get_selected_id()
        if not eid:
            QMessageBox.information(self, t("menu_edit_entry"), t("msg_select_entry"))
            return
        self._entry_dialog(int(eid))

    def _on_delete(self):
        if self.state.is_locked() or not self.db:
            QMessageBox.warning(self, t("menu_delete"), t("msg_unlock_first"))
            return
        eid = self.table.get_selected_id()
        if not eid:
            QMessageBox.information(self, t("menu_delete"), t("msg_select_entry"))
            return
        if QMessageBox.question(self, t("menu_delete"), t("msg_delete_confirm"), QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            delete_entry(self.db, int(eid))
            event_bus.publish(entry_deleted, {"entry_id": int(eid)})
            self._refresh_table()

    def _entry_dialog(self, entry_id: Optional[int]):
        dlg = QDialog(self)
        dlg.setWindowTitle(t("dlg_entry_add") if entry_id is None else t("dlg_entry_edit"))
        dlg.setMinimumSize(400, 300)
        layout = QVBoxLayout(dlg)
        grid = QGridLayout()
        title_edit = QLineEdit()
        grid.addWidget(QLabel(t("label_title")), 0, 0)
        grid.addWidget(title_edit, 0, 1)
        user_edit = QLineEdit()
        grid.addWidget(QLabel(t("label_username")), 1, 0)
        grid.addWidget(user_edit, 1, 1)
        pw_entry = PasswordEntry()
        grid.addWidget(QLabel(t("label_password")), 2, 0)
        grid.addWidget(pw_entry, 2, 1)
        url_edit = QLineEdit()
        grid.addWidget(QLabel(t("label_url")), 3, 0)
        grid.addWidget(url_edit, 3, 1)
        notes_edit = QLineEdit()
        grid.addWidget(QLabel(t("label_notes")), 4, 0)
        grid.addWidget(notes_edit, 4, 1)
        layout.addLayout(grid)
        def save():
            title = title_edit.text().strip()
            if not title:
                QMessageBox.critical(dlg, t("menu_about"), t("msg_error_title"))
                return
            try:
                if entry_id is None:
                    insert_entry(
                        self.db, self.crypto, self._key,
                        title=title,
                        username=user_edit.text(),
                        password=pw_entry.get(),
                        url=url_edit.text(),
                        notes=notes_edit.text(),
                    )
                    event_bus.publish(entry_added, {"title": title})
                else:
                    update_entry(
                        self.db, self.crypto, self._key, entry_id,
                        title=title,
                        username=user_edit.text(),
                        password=pw_entry.get() or None,
                        url=url_edit.text(),
                        notes=notes_edit.text() or None,
                    )
                    event_bus.publish(entry_updated, {"entry_id": entry_id})
                self._refresh_table()
                dlg.accept()
            except Exception:
                QMessageBox.critical(dlg, t("menu_about"), t("msg_error_failed"))
        save_btn = QPushButton(t("btn_save"))
        save_btn.clicked.connect(save)
        layout.addWidget(save_btn)
        dlg.exec()

    def _on_view_logs(self):
        dlg = QDialog(self)
        dlg.setWindowTitle(t("dlg_logs_title"))
        dlg.setMinimumSize(500, 300)
        dlg.resize(500, 300)
        layout = QVBoxLayout(dlg)
        viewer = AuditLogViewer(dlg)
        layout.addWidget(viewer)
        if self.db:
            rows = self.db.fetchall("SELECT action, timestamp, details FROM audit_log ORDER BY id DESC LIMIT 100")
            viewer.set_entries([{"action": r[0], "timestamp": r[1], "details": (r[2] or "")} for r in rows])
        dlg.exec()

    def _on_settings(self):
        d = SettingsDialog(self, config=self.config)
        d.exec()
        if hasattr(self, "update_ui_language"):
            self.update_ui_language()

    def _on_about(self):
        QMessageBox.information(self, t("menu_about"), t("about_text"))

    def run(self):
        self.show()
        QApplication.instance().exec()
        if self.db:
            self.db.close()
