# Главное окно — меню сверху, таблица записей, внизу статус и таймер буфера.

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QMenuBar, QMenu, QStatusBar,
    QLabel, QMessageBox, QFileDialog, QApplication, QTableWidgetItem,
)
from PyQt6.QtCore import QTimer, Qt

import base64
from core import config
from core.state_manager import get_state_manager
from core.crypto.placeholder import AES256Placeholder
from core.key_manager import derive_key
from core import events
from database import db as database_db
from .strings import t
from .widgets.secure_table import SecureTable


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        sm = get_state_manager()
        self._buffer_seconds = int(config.get(config.CLIPBOARD_TIMEOUT, "30") or "30")
        sm.set_clipboard_timeout(self._buffer_seconds)
        self._build_ui()
        self._build_menu()
        self._build_status_bar()
        self._start_buffer_timer()

    def _build_ui(self):
        self.setWindowTitle(t("app_title"))
        self.setMinimumSize(700, 400)
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        self._table = SecureTable(self)
        self._table.setHorizontalHeaderLabels([t("title"), t("login"), t("url"), t("notes")])
        self._row_ids = []
        self._load_table()
        layout.addWidget(self._table)

    def _build_menu(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu(t("file"))
        file_menu.addAction(t("new"), self._on_new)
        file_menu.addAction(t("open"), self._on_open)
        file_menu.addAction(t("backup"), self._on_backup)
        file_menu.addSeparator()
        file_menu.addAction(t("exit"), QApplication.quit)
        edit_menu = menubar.addMenu(t("edit"))
        edit_menu.addAction(t("add"), self._on_add)
        edit_menu.addAction(t("edit_"), self._on_edit)
        edit_menu.addAction(t("delete"), self._on_delete)
        edit_menu.addSeparator()
        edit_menu.addAction(t("copy_login"), self._on_copy_login)
        edit_menu.addAction(t("copy_password"), self._on_copy_password)
        view_menu = menubar.addMenu(t("view"))
        view_menu.addAction(t("logs"), self._on_logs)
        view_menu.addAction(t("settings"), self._on_settings)
        view_menu.addAction(t("state_monitor"), self._on_state_monitor)
        help_menu = menubar.addMenu(t("help"))
        help_menu.addAction(t("about"), self._on_about)

    def _build_status_bar(self):
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        sm = get_state_manager()
        self._status_label = QLabel(t("status_locked") if sm.is_locked() else t("status_unlocked"))
        self._buffer_label = QLabel(t("buffer_timer") % str(sm.get_clipboard_seconds_left()))
        self._status_bar.addPermanentWidget(self._status_label)
        self._status_bar.addPermanentWidget(self._buffer_label)

    def _start_buffer_timer(self):
        self._buffer_timer = QTimer(self)
        self._buffer_timer.timeout.connect(self._on_buffer_tick)
        self._buffer_timer.start(1000)

    def _on_buffer_tick(self):
        sm = get_state_manager()
        prev = sm.get_clipboard_seconds_left()
        sm.tick_clipboard_timer()
        left = sm.get_clipboard_seconds_left()
        self._buffer_label.setText(t("buffer_timer") % str(left))
        if prev == 1 and left == 0:
            try:
                QApplication.clipboard().clear()
            except Exception:
                pass

    def reset_buffer_timer(self):
        sm = get_state_manager()
        sm.reset_clipboard_timer()
        self._buffer_label.setText(t("buffer_timer") % str(sm.get_clipboard_seconds_left()))

    def set_locked(self, locked):
        get_state_manager().set_locked(locked)
        self._status_label.setText(t("status_locked") if locked else t("status_unlocked"))

    def _on_state_monitor(self):
        get_state_manager().touch_activity()
        from .view_windows import StateMonitorWindow
        self._state_monitor_window = StateMonitorWindow(None)
        self._state_monitor_window.setWindowTitle(t("state_monitor"))
        self._state_monitor_window.setWindowFlags(self._state_monitor_window.windowFlags() | Qt.WindowType.Window)
        self._state_monitor_window.move(self.x() + self.width() + 20, self.y())
        self._state_monitor_window.show()

    def _on_new(self):
        get_state_manager().touch_activity()
        QMessageBox.information(self, t("new"), t("new"))

    def _on_open(self):
        get_state_manager().touch_activity()
        path, _ = QFileDialog.getOpenFileName(self, t("open"), "", "Database (*.db)")
        if path:
            config.set(config.DB_PATH, path)

    def _on_backup(self):
        get_state_manager().touch_activity()
        path, _ = QFileDialog.getSaveFileName(self, t("backup"), "", "Database (*.db)")
        if path:
            pass

    def _load_table(self):
        try:
            rows = database_db.get_all_vault_entries()
            self._row_ids = [r[0] for r in rows]
            self._table.setRowCount(len(rows))
            for i, r in enumerate(rows):
                for j, cell in enumerate([r[1], r[2], r[4], r[5]]):
                    self._table.setItem(i, j, QTableWidgetItem(str(cell or "")))
            if not rows:
                self._table.setRowCount(0)
        except Exception:
            QMessageBox.warning(self, t("app_title"), t("error_generic"))
            self._row_ids = []
            self._table.setRowCount(0)

    def _encrypt_password(self, password):
        if not password:
            return ""
        cipher = AES256Placeholder()
        salt = config.get_vault_salt()
        key = derive_key("", salt)
        enc = cipher.encrypt(password.encode("utf-8"), key)
        return base64.b64encode(enc).decode("ascii")

    def _decrypt_password(self, encrypted_b64):
        if not encrypted_b64:
            return ""
        cipher = AES256Placeholder()
        salt = config.get_vault_salt()
        key = derive_key("", salt)
        raw = base64.b64decode(encrypted_b64.encode("ascii"))
        return cipher.decrypt(raw, key).decode("utf-8", errors="replace")

    def _on_add(self):
        get_state_manager().touch_activity()
        try:
            from .entry_dialog import EntryDialog
            d = EntryDialog(self, is_edit=False)
            if not d.exec():
                return
            data = d.get_data()
            enc = self._encrypt_password(data["password"])
            entry_id = database_db.insert_vault_entry(
                title=data["title"], username=data["username"], encrypted_password=enc,
                url=data["url"] or None, notes=data["notes"] or None,
            )
            events.publish(events.EntryAdded, sync=True, entry_id=entry_id)
            self._load_table()
        except Exception:
            QMessageBox.warning(self, t("app_title"), t("error_generic"))

    def _on_edit(self):
        get_state_manager().touch_activity()
        row = self._table.currentRow()
        if row < 0 or row >= len(self._row_ids):
            QMessageBox.information(self, t("edit_"), t("select_entry_edit"))
            return
        try:
            entry_id = self._row_ids[row]
            entry = database_db.get_vault_entry(entry_id)
            if not entry:
                return
            _, title, username, enc_pass, url, notes = entry
            pwd_plain = self._decrypt_password(enc_pass) if enc_pass else ""
            from .entry_dialog import EntryDialog
            d = EntryDialog(self, title=title or "", username=username or "", password=pwd_plain, url=url or "", notes=notes or "", is_edit=True)
            if not d.exec():
                return
            data = d.get_data()
            new_enc = self._encrypt_password(data["password"]) if data["password"] else enc_pass
            database_db.update_vault_entry(entry_id, title=data["title"], username=data["username"], encrypted_password=new_enc, url=data["url"] or None, notes=data["notes"] or None)
            events.publish(events.EntryUpdated, sync=True, entry_id=entry_id)
            self._load_table()
        except Exception:
            QMessageBox.warning(self, t("app_title"), t("error_generic"))

    def _on_delete(self):
        get_state_manager().touch_activity()
        row = self._table.currentRow()
        if row < 0 or row >= len(self._row_ids):
            QMessageBox.information(self, t("delete"), t("select_entry_delete"))
            return
        entry_id = self._row_ids[row]
        if QMessageBox.question(self, t("delete"), t("confirm_delete"), QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        try:
            database_db.delete_vault_entry(entry_id)
            events.publish(events.EntryDeleted, sync=True, entry_id=entry_id)
            self._load_table()
        except Exception:
            QMessageBox.warning(self, t("app_title"), t("error_generic"))

    def _on_copy_login(self):
        get_state_manager().touch_activity()
        row = self._table.currentRow()
        if row < 0 or row >= len(self._row_ids):
            QMessageBox.information(self, t("copy_login"), t("select_entry_edit"))
            return
        try:
            entry = database_db.get_vault_entry(self._row_ids[row])
            if not entry:
                return
            _, title, username, enc_pass, url, notes = entry
            text = username or ""
            QApplication.clipboard().setText(text)
            self.reset_buffer_timer()
            events.publish(events.ClipboardCopied, sync=True, entry_id=self._row_ids[row], kind="login")
        except Exception:
            QMessageBox.warning(self, t("app_title"), t("error_generic"))

    def _on_copy_password(self):
        get_state_manager().touch_activity()
        row = self._table.currentRow()
        if row < 0 or row >= len(self._row_ids):
            QMessageBox.information(self, t("copy_password"), t("select_entry_edit"))
            return
        try:
            entry = database_db.get_vault_entry(self._row_ids[row])
            if not entry:
                return
            _, title, username, enc_pass, url, notes = entry
            text = self._decrypt_password(enc_pass) if enc_pass else ""
            QApplication.clipboard().setText(text)
            self.reset_buffer_timer()
            events.publish(events.ClipboardCopied, sync=True, entry_id=self._row_ids[row], kind="password")
        except Exception:
            QMessageBox.warning(self, t("app_title"), t("error_generic"))

    def _on_logs(self):
        get_state_manager().touch_activity()
        from .view_windows import AuditLogViewer
        self._audit_log_window = AuditLogViewer(None)
        self._audit_log_window.setWindowTitle(t("logs"))
        self._audit_log_window.setWindowFlags(self._audit_log_window.windowFlags() | Qt.WindowType.Window)
        self._audit_log_window.resize(400, 300)
        self._audit_log_window.move(self.x() + self.width() + 20, self.y())
        self._audit_log_window.show()

    def _on_about(self):
        QMessageBox.about(self, t("app_title"), t("about_text"))

    def _on_settings(self):
        get_state_manager().touch_activity()
        from .settings_dialog import SettingsDialog
        d = SettingsDialog(self)
        if d.exec():
            self._buffer_seconds = int(config.get(config.CLIPBOARD_TIMEOUT, "30") or "30")
            get_state_manager().set_clipboard_timeout(self._buffer_seconds)
            self._apply_theme_and_language()

    def _apply_theme_and_language(self):
        from .theme import apply_theme
        apply_theme(QApplication.instance())
        self.setWindowTitle(t("app_title"))
        self.menuBar().clear()
        self._build_menu()
        sm = get_state_manager()
        self._status_label.setText(t("status_locked") if sm.is_locked() else t("status_unlocked"))
        self._buffer_label.setText(t("buffer_timer") % str(sm.get_clipboard_seconds_left()))
        self._table.setHorizontalHeaderLabels([t("title"), t("login"), t("url"), t("notes")])
