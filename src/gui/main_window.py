"""Main window: vault table, menus, clipboard timer, tray integration. / Главное окно: таблица, меню, буфер, трей."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QMenuBar, QStatusBar,
    QLabel, QMessageBox, QFileDialog, QApplication, QTableWidgetItem,
    QLineEdit, QHBoxLayout, QToolBar, QPushButton, QSizePolicy, QToolButton
)
from PyQt6.QtCore import QTimer, Qt, QEvent
from PyQt6.QtGui import QAction, QKeySequence, QShortcut

import difflib
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from core import config
from core.state_manager import get_state_manager
from core.key_manager import get_key_manager
from core import events
from database import db as database_db
from core.vault.entry_manager import EntryManager
from core.clipboard.clipboard_service import ClipboardService
from core.clipboard.clipboard_monitor import ClipboardMonitor
from core.clipboard.platform_adapter import create_platform_adapter
from .strings import t, normalize_search_field
from . import keyboard_shortcuts as kbd
from .user_errors import user_facing_error
from .widgets.secure_table import SecureTable
from .import_export_dialogs import ExportDialog, ImportDialog, ShareDialog, QRViewerDialog
from core.import_export.importer import VaultImporter
from core.security.activity_monitor import ActivityMonitor
from core.security.panic_mode import get_panic_mode
from core.backup_service import create_backup, restore_backup
from .tray_icon import TrayController


class MainWindow(QMainWindow):
    """Primary application window for vault CRUD and session control. / Главное окно приложения: записи и сессия."""

    def __init__(self):
        """Builds UI, services, tray, and security hooks. / Создаёт UI, сервисы, трей и обработчики безопасности."""
        super().__init__()
        sm = get_state_manager()
        self._buffer_seconds = int(config.get(config.CLIPBOARD_TIMEOUT, "30") or "30")
        sm.set_clipboard_timeout(self._buffer_seconds)

        # (спринт3) контроллер vault: CRUD + AES-GCM шифрование/дешифрование
        km = get_key_manager()
        self._entry_manager = EntryManager(database_db, km, events)
        self._all_entries_cache: List[Dict] = []
        self._password_revealed: Dict[int, str] = {}  # entry_id -> plaintext password
        self._password_widgets: Dict[int, Tuple[QLabel, QToolButton]] = {}
        self._global_show_passwords = False

        # (спринт4) сервис буфера обмена; очистка по таймеру GUI — один раз, из главного потока
        self._clipboard_service = ClipboardService(create_platform_adapter())
        self._clipboard_service.subscribe(self._on_clipboard_status_changed)
        self._clipboard_monitor = ClipboardMonitor(self._clipboard_service.adapter)
        self._clipboard_monitor.set_on_change(self._on_external_clipboard_change)

        self._activity_monitor = None
        self._tray = TrayController(self)
        self._setup_panic_mode()
        self.installEventFilter(self)

        self._build_ui()
        self._build_menu()
        self._build_status_bar()
        self._start_buffer_timer()
        self._clipboard_monitor.start()
        self._tray.setup()
        self._start_activity_monitor()
        if int(config.get(config.PANIC_HOTKEY_ENABLED, "1") or "1") > 0:
            self._panic_shortcut = QShortcut(QKeySequence("Ctrl+Shift+Esc"), self)
            self._panic_shortcut.activated.connect(lambda: self._activate_panic("hotkey"))
        if int(config.get(config.START_MINIMIZED_TRAY, "0") or "0") > 0 and self._tray.available:
            QTimer.singleShot(0, self.hide)

    def eventFilter(self, obj, event):
        """Records user activity for auto-lock on input events. / Учитывает активность пользователя для автоблокировки."""
        if event.type() == QEvent.Type.KeyPress and obj is self._search:
            key = event.key()
            mods = event.modifiers()
            if key == Qt.Key.Key_Escape:
                self._search.clear()
                event.accept()
                return True
            if key == Qt.Key.Key_Tab and mods == Qt.KeyboardModifier.NoModifier:
                self._focus_vault_table()
                event.accept()
                return True
        if event.type() in (
            QEvent.Type.MouseMove,
            QEvent.Type.MouseButtonPress,
            QEvent.Type.KeyPress,
            QEvent.Type.Wheel,
        ):
            get_state_manager().touch_activity()
            if self._activity_monitor:
                self._activity_monitor.record_activity()
        return super().eventFilter(obj, event)

    def _setup_panic_mode(self):
        panic = get_panic_mode()
        panic.set_stealth_enabled(int(config.get(config.PANIC_STEALTH_MODE, "0") or "0") > 0)
        panic.register_handler(lambda: self._clipboard_service.clear(reason="panic"))
        panic.register_handler(lambda: self._do_auto_lock(reason="panic"))
        panic.register_handler(self._hide_for_panic)
        panic.register_stealth_handler(self._panic_fake_error)

    def _hide_for_panic(self):
        self._password_revealed.clear()
        self.hide()

    def _panic_fake_error(self):
        try:
            import sys
            if "pytest" in sys.modules:
                return
        except Exception:
            pass
        QMessageBox.critical(self, t("app_title"), t("error_generic"))

    def _activate_panic(self, method: str = "menu"):
        get_panic_mode().activate(method=method)
        if self._tray.available:
            self._tray.notify(t("panic_activated"))

    def _start_activity_monitor(self):
        if self._activity_monitor:
            self._activity_monitor.stop()
        minutes = max(1, int(config.get(config.AUTO_LOCK_MINUTES, "5") or "5"))
        self._activity_monitor = ActivityMonitor(self._on_activity_lock, lock_timeout_sec=minutes * 60)
        self._activity_monitor.start()

    def _on_activity_lock(self):
        QTimer.singleShot(0, lambda: self._do_auto_lock(reason="inactivity"))

    def show_from_tray(self):
        """Restores and focuses the window from the system tray. / Восстанавливает и активирует окно из системного трея."""
        self.showNormal()
        self.raise_()
        self.activateWindow()
        get_state_manager().touch_activity()

    def _cleanup_on_exit(self) -> None:
        try:
            if self._activity_monitor:
                self._activity_monitor.stop()
            self._clipboard_monitor.stop()
            self._clipboard_service.clear(reason="app_close")
            if getattr(self, "_tray", None) and self._tray._tray is not None:
                self._tray._tray.hide()
        except Exception:
            pass

    def _quit_app(self):
        self._cleanup_on_exit()
        QApplication.quit()

    def changeEvent(self, event):
        """Locks or hides the window on minimize per security settings. / Блокирует или скрывает окно при сворачивании."""
        super().changeEvent(event)
        try:
            if event.type() == QEvent.Type.WindowStateChange:
                lock_on_min = int(config.get(config.LOCK_ON_MINIMIZE, "1") or "1")
                if lock_on_min > 0 and not get_state_manager().is_locked() and self.isMinimized():
                    self._do_auto_lock(reason="minimize")
                if int(config.get(config.MINIMIZE_TO_TRAY, "0") or "0") > 0 and self.isMinimized() and self._tray.available:
                    self.hide()
        except Exception:
            pass

    def focusOutEvent(self, event):
        """Locks the vault when the window loses focus if configured. / Блокирует хранилище при потере фокуса окна."""
        super().focusOutEvent(event)
        try:
            lock_on_focus = int(config.get(config.LOCK_ON_FOCUS_LOST, "1") or "1")
            if lock_on_focus > 0 and not get_state_manager().is_locked():
                self._do_auto_lock(reason="focus_lost")
        except Exception:
            pass

    def _build_ui(self):
        self.setWindowTitle(t("app_title"))
        self.setMinimumSize(700, 400)
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # (спринт3) поиск: realtime фильтр по полям с учётом опечаток
        self._search = QLineEdit()
        self._search.setPlaceholderText(t("search_placeholder"))
        self._search.setAccessibleName(t("search_accessible"))
        self._search.textChanged.connect(self._on_search_changed)
        self._search.installEventFilter(self)
        layout.addWidget(self._search)

        self._empty_hint = QLabel()
        self._empty_hint.setWordWrap(True)
        self._empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_hint.hide()
        layout.addWidget(self._empty_hint)

        self._table = SecureTable(self)
        # context menu (GUI-2 / GUI-3): правый клик по строке
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._on_context_menu)
        self._table.cellDoubleClicked.connect(self._on_table_double_click)
        self._table.row_edit_requested.connect(self._on_edit)
        self._table.row_delete_requested.connect(self._on_delete)
        self._table.focus_search_requested.connect(self._focus_search_field)
        self._load_table()
        layout.addWidget(self._table)
        QWidget.setTabOrder(self._search, self._table)
        QWidget.setTabOrder(self._table, self._search)

        # toolbar: глобальный toggle видимости паролей (GUI-3, спринт4: локализованный текст)
        self._toolbar = QToolBar(t("clipboard_toolbar_title"), self)
        self._toolbar.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self._toolbar)
        self._act_toggle_passwords = QAction(t("clipboard_toolbar_show_passwords"), self)
        self._act_toggle_passwords.setCheckable(True)
        self._act_toggle_passwords.setChecked(False)
        self._act_toggle_passwords.setShortcut("Ctrl+Shift+P")
        self._act_toggle_passwords.toggled.connect(self._on_global_toggle_passwords)
        self._toolbar.addAction(self._act_toggle_passwords)
        self._setup_keyboard_shortcuts()

    def _bind_shortcut(self, action: QAction, keys: str) -> None:
        action.setShortcut(QKeySequence(keys))
        action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)

    def _setup_keyboard_shortcuts(self):
        """UX-1: window shortcuts and table-only keys (Delete, F2, Enter)."""
        sc = QShortcut(QKeySequence(kbd.KEY_FOCUS_SEARCH), self)
        sc.setContext(Qt.ShortcutContext.WindowShortcut)
        sc.activated.connect(self._on_focus_search)

    def _on_focus_search(self):
        self._focus_search_field()

    def _focus_search_field(self):
        self._search.setFocus(Qt.FocusReason.TabFocusReason)
        self._search.selectAll()

    def _focus_vault_table(self):
        self._table.setFocus(Qt.FocusReason.TabFocusReason)
        if self._table.rowCount() <= 0:
            return
        row = self._table.currentRow()
        if row < 0:
            row = 0
        self._table.selectRow(row)
        self._table.setCurrentCell(row, 0)

    def _on_lock_session(self):
        if not get_state_manager().is_locked():
            self._do_auto_lock(reason="shortcut")

    def _on_keyboard_shortcuts_help(self):
        QMessageBox.information(self, t("keyboard_shortcuts"), kbd.format_shortcuts_help())

    def _on_table_double_click(self, _row: int, _col: int):
        self._on_edit()

    def _refresh_localized_ui(self):
        self._search.setPlaceholderText(t("search_placeholder"))
        if hasattr(self, "_empty_hint") and self._empty_hint.isVisible():
            query = (self._search.text() or "").strip()
            if query:
                self._empty_hint.setText(t("vault_empty_search"))
            elif not self._all_entries_cache:
                self._empty_hint.setText(f"{t('vault_empty')}\n{t('vault_empty_hint')}")
        if hasattr(self, "_toolbar"):
            self._toolbar.setWindowTitle(t("clipboard_toolbar_title"))
        if hasattr(self, "_act_toggle_passwords"):
            self._act_toggle_passwords.setText(t("clipboard_toolbar_show_passwords"))
        for entry_id, (_label, btn) in self._password_widgets.items():
            shown = entry_id in self._password_revealed
            btn.setText(t("password_btn_hide") if shown else t("password_btn_show"))
            btn.setToolTip(t("password_hide") if shown else t("password_show"))

    def _build_menu(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu(t("file"))
        file_menu.addAction(t("new"), self._on_new)
        file_menu.addAction(t("open"), self._on_open)
        file_menu.addAction(t("s6_export"), self._on_export_vault)
        file_menu.addAction(t("s6_import"), self._on_import_vault)
        file_menu.addAction(t("s6_share"), self._on_share_entry)
        file_menu.addAction(t("s6_qr_viewer"), self._on_qr_viewer)
        act_unlock = file_menu.addAction(t("unlock"), self._on_unlock)
        self._bind_shortcut(act_unlock, kbd.KEY_UNLOCK)
        act_lock = file_menu.addAction(t("lock_session"), self._on_lock_session)
        self._bind_shortcut(act_lock, kbd.KEY_LOCK)
        file_menu.addAction(t("backup"), self._on_backup)
        file_menu.addAction(t("restore_backup"), self._on_restore_backup)
        file_menu.addSeparator()
        file_menu.addAction(t("exit"), self._quit_app)
        edit_menu = menubar.addMenu(t("edit"))
        act_add = edit_menu.addAction(t("add"), self._on_add)
        self._bind_shortcut(act_add, kbd.KEY_ADD)
        act_edit = edit_menu.addAction(t("edit_"), self._on_edit)
        self._bind_shortcut(act_edit, kbd.KEY_EDIT)
        act_del = edit_menu.addAction(t("delete"), self._on_delete)
        act_del.setShortcut(QKeySequence())
        edit_menu.addSeparator()
        act_copy_login = edit_menu.addAction(t("copy_login"), self._on_copy_login)
        self._bind_shortcut(act_copy_login, kbd.KEY_COPY_LOGIN)
        act_copy_pwd = edit_menu.addAction(t("copy_password"), self._on_copy_password)
        self._bind_shortcut(act_copy_pwd, kbd.KEY_COPY_PASSWORD)
        act_copy_all = edit_menu.addAction(t("clipboard_copy_all"), self._on_copy_all)
        self._bind_shortcut(act_copy_all, kbd.KEY_COPY_ALL)
        act_clear_clip = edit_menu.addAction(t("clipboard_manual_clear"), self._on_clear_clipboard)
        self._bind_shortcut(act_clear_clip, kbd.KEY_CLEAR_CLIPBOARD)
        edit_menu.addSeparator()
        edit_menu.addAction(t("change_password_title"), self._on_change_password)
        view_menu = menubar.addMenu(t("view"))
        act_logs = view_menu.addAction(t("logs"), self._on_logs)
        self._bind_shortcut(act_logs, kbd.KEY_AUDIT_LOG)
        act_settings = view_menu.addAction(t("settings"), self._on_settings)
        self._bind_shortcut(act_settings, kbd.KEY_SETTINGS)
        view_menu.addAction(t("state_monitor"), self._on_state_monitor)
        help_menu = menubar.addMenu(t("help"))
        help_menu.addAction(t("keyboard_shortcuts"), self._on_keyboard_shortcuts_help)
        help_menu.addAction(t("about"), self._on_about)

    def _build_status_bar(self):
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        sm = get_state_manager()
        self._status_label = QLabel(t("status_locked") if sm.is_locked() else t("status_unlocked"))
        self._buffer_label = QLabel(t("buffer_timer") % str(sm.get_clipboard_seconds_left()))
        self._clipboard_status_label = QLabel(t("clipboard_status_idle"))
        self._status_bar.addPermanentWidget(self._status_label)
        self._status_bar.addPermanentWidget(self._buffer_label)
        self._status_bar.addPermanentWidget(self._clipboard_status_label)

    def _start_buffer_timer(self):
        self._buffer_timer = QTimer(self)
        self._buffer_timer.timeout.connect(self._on_buffer_tick)
        self._buffer_timer.start(1000)

    def _on_buffer_tick(self):
        # раз в секунду: счётчик буфера и проверка неактивности для авто-блокировки
        sm = get_state_manager()
        prev = sm.get_clipboard_seconds_left()
        sm.tick_clipboard_timer()
        left = sm.get_clipboard_seconds_left()
        self._buffer_label.setText(t("buffer_timer") % str(left))
        if prev == 1 and left == 0 and self._clipboard_service.get_status().get("active"):
            try:
                self._clipboard_service.clear(reason="timer_tick")
            except Exception:
                pass
        if left == 5 and self._clipboard_service.get_status().get("active"):
            self.statusBar().showMessage(t("clipboard_warning_soon_clear"), 1500)
        # авто-блокировка: если прошло больше N минут без действий — блокируем сессию
        auto_lock_min = int(config.get(config.AUTO_LOCK_MINUTES, "5") or "5")
        if auto_lock_min > 0 and not sm.is_locked() and sm.get_inactivity_seconds() >= auto_lock_min * 60:
            self._do_auto_lock(reason="inactivity")

    def _do_auto_lock(self, reason: str = "inactivity", *, show_message: bool = True):
        from core.key_manager import clear_encryption_key
        if hasattr(self, "_status_label") and not self._status_label:
            return
        try:
            self._clipboard_service.clear(reason="vault_lock")
        except Exception:
            pass
        clear_encryption_key()
        get_state_manager().set_locked(True)
        if hasattr(self, "_status_label"):
            self._status_label.setText(t("status_locked"))
        events.publish(events.UserLoggedOut, sync=True)
        events.publish(events.VaultLocked, sync=True, reason=reason)
        if self._activity_monitor:
            self._activity_monitor.record_activity()
        if hasattr(self, "_tray"):
            self._tray.update_status()
        # чтобы тесты не зависали из-за модального окна
        if reason == "panic" or not show_message:
            return
        try:
            import sys
            if "pytest" in sys.modules:
                return
        except Exception:
            pass
        msg_key = "session_locked_inactivity" if reason == "inactivity" else "session_locked_manual"
        QMessageBox.information(self, t("app_title"), t(msg_key))

    def _on_unlock(self):
        get_state_manager().touch_activity()
        from .unlock_dialog import UnlockDialog
        d = UnlockDialog(self)
        if d.exec():
            self.set_locked(False)

    def reset_buffer_timer(self):
        """Resets the clipboard auto-clear countdown in the status bar. / Сбрасывает таймер автоочистки буфера обмена."""
        sm = get_state_manager()
        sm.reset_clipboard_timer()
        self._buffer_label.setText(t("buffer_timer") % str(sm.get_clipboard_seconds_left()))

    def set_locked(self, locked):
        """Updates locked state in UI and tray after unlock/lock. / Обновляет состояние блокировки в UI и трее."""
        get_state_manager().set_locked(locked)
        self._status_label.setText(t("status_locked") if locked else t("status_unlocked"))
        if hasattr(self, "_tray"):
            self._tray.update_status()
        if not locked:
            self._start_activity_monitor()

    def _get_selected_entry_id(self):
        # возвращаем id выбранной записи (спринт3: пароль/eye кнопки не участвуют в item-data)
        item = self._table.currentItem()
        if item is None:
            # если текущий item не выбран — берём первый выбранный
            selected = self._table.selectedItems()
            if not selected:
                return None
            item = selected[0]
        return item.data(Qt.ItemDataRole.UserRole)

    def _show_error(self, exc=None):
        # POL-3: без трассировок и внутренних путей
        try:
            import sys
            if "pytest" in sys.modules:
                return
        except Exception:
            pass
        QMessageBox.warning(self, t("app_title"), user_facing_error(exc))

    def _require_unlocked(self) -> bool:
        """POL-4: блокируем изменения данных в заблокированной сессии."""
        if get_state_manager().is_locked():
            QMessageBox.information(self, t("app_title"), t("session_locked_action"))
            return False
        return True

    def _touch_and_open_side_window(self, window_class, title_key, width=400, height=300):
        # обновляется время активности; открывается боковое окно (журнал, монитор состояния) справа от главного
        get_state_manager().touch_activity()
        win = window_class(None)
        win.setWindowTitle(t(title_key))
        win.setWindowFlags(win.windowFlags() | Qt.WindowType.Window)
        win.resize(width, height)
        win.move(self.x() + self.width() + 20, self.y())
        win.show()
        return win

    def _on_state_monitor(self):
        from .view_windows import StateMonitorWindow
        self._state_monitor_window = self._touch_and_open_side_window(
            StateMonitorWindow, "state_monitor", 320, 200
        )

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
        default_name = f"cryptosafe-backup-{datetime.now().strftime('%Y%m%d-%H%M')}.csafe.zip"
        path, _ = QFileDialog.getSaveFileName(
            self,
            t("backup"),
            default_name,
            f"{t('backup_save_filter')};;All files (*.*)",
        )
        if not path:
            return
        try:
            manifest = create_backup(path, include_config=True)
            archive = manifest.get("archive_path", path)
            QMessageBox.information(
                self,
                t("backup"),
                t("backup_ok")
                % f"{archive}\n{t('title')}: {manifest.get('entry_count', 0)}",
            )
        except Exception as exc:
            from .user_errors import format_operation_error

            QMessageBox.warning(self, t("backup"), format_operation_error(exc, context="backup"))

    def _on_restore_backup(self):
        get_state_manager().touch_activity()
        reply = QMessageBox.question(
            self, t("confirm_destructive"), t("confirm_restore"), QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, t("restore_backup"), "", "CryptoSafe backup (*.csafe.zip);;All files (*.*)"
        )
        if not path:
            return
        try:
            restore_backup(path, restore_config=False)
            self._password_revealed.clear()
            self._do_auto_lock(reason="restore", show_message=False)
            QMessageBox.information(self, t("restore_backup"), t("restore_ok"))
            from .unlock_dialog import UnlockDialog

            if UnlockDialog(self, after_restore=True).exec():
                self.set_locked(False)
                self._load_table()
            else:
                self._all_entries_cache = []
                self._apply_search_filter_and_fill()
        except Exception as exc:
            from .user_errors import format_operation_error

            QMessageBox.warning(self, t("restore_backup"), format_operation_error(exc, context="backup"))

    def _fill_table(self, rows):
        # таблица заполняется списком уже расшифрованных метаданных (пароль не держим)
        self._table.setRowCount(len(rows))
        self._password_widgets = {}
        # если перерисовали таблицу — скрываем все ранее раскрытые пароли
        self._password_revealed = {}

        masked_password = "••••••••"
        for i, row in enumerate(rows):
            entry_id = int(row["id"])

            t0 = QTableWidgetItem(str(row.get("title", "") or ""))
            t0.setData(Qt.ItemDataRole.UserRole, entry_id)
            self._table.setItem(i, 0, t0)

            t1 = QTableWidgetItem(str(row.get("username_masked", "") or ""))
            t1.setData(Qt.ItemDataRole.UserRole, entry_id)
            self._table.setItem(i, 1, t1)

            t2 = QTableWidgetItem(str(row.get("url_domain", "") or ""))
            t2.setData(Qt.ItemDataRole.UserRole, entry_id)
            self._table.setItem(i, 2, t2)

            t3 = QTableWidgetItem(str(row.get("updated_at", "") or ""))
            t3.setData(Qt.ItemDataRole.UserRole, entry_id)
            self._table.setItem(i, 3, t3)

            t4 = QTableWidgetItem(str(row.get("notes", "") or ""))
            t4.setData(Qt.ItemDataRole.UserRole, entry_id)
            self._table.setItem(i, 4, t4)

            cell = QWidget()
            hb = QHBoxLayout(cell)
            hb.setContentsMargins(4, 0, 4, 0)
            hb.setSpacing(2)
            label = QLabel(masked_password)
            label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            btn = QToolButton(cell)
            btn.setObjectName("passwordToggleBtn")
            btn.setText(t("password_btn_show"))
            btn.setToolTip(t("password_show"))
            btn.setAutoRaise(True)
            btn.setFixedSize(46, 22)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setProperty("entry_id", entry_id)
            btn.clicked.connect(self._on_eye_clicked)
            hb.addWidget(label, 1)
            hb.addWidget(btn, 0)

            self._table.setRowHeight(i, 30)
            self._table.setCellWidget(i, 5, cell)
            self._password_widgets[entry_id] = (label, btn)

    def _load_table(self):
        if get_state_manager().is_locked():
            self._all_entries_cache = []
            self._apply_search_filter_and_fill()
            return
        try:
            self._all_entries_cache = self._entry_manager.get_all_entries()
            self._apply_search_filter_and_fill()
        except Exception as exc:
            self._show_error(exc)
            self._all_entries_cache = []
            self._apply_search_filter_and_fill()

    def _apply_search_filter_and_fill(self):
        query = (self._search.text() or "").strip()
        if not query:
            rows = self._all_entries_cache
        else:
            rows = self._filter_entries(query, self._all_entries_cache)
        self._fill_table(rows)
        self._update_empty_state(rows, bool(query))

    def _update_empty_state(self, rows: List[Dict], has_search: bool) -> None:
        if rows:
            self._empty_hint.hide()
            self._table.show()
            return
        self._table.setRowCount(0)
        self._table.show()
        if has_search:
            self._empty_hint.setText(t("vault_empty_search"))
        elif not self._all_entries_cache:
            self._empty_hint.setText(f"{t('vault_empty')}\n{t('vault_empty_hint')}")
        else:
            self._empty_hint.setText(t("vault_empty_search"))
        self._empty_hint.show()

    def _on_search_changed(self, _):
        # SEARCH-2: realtime обновление результатов
        try:
            self._apply_search_filter_and_fill()
        except Exception as exc:
            self._show_error(exc)

    def _similarity(self, a: str, b: str) -> float:
        # fuzzy matching: опечатки → приблизительное совпадение
        a = (a or "").lower()
        b = (b or "").lower()
        if not a or not b:
            return 0.0
        if b in a:
            return 1.0
        return difflib.SequenceMatcher(None, a, b).ratio()

    def _filter_entries(self, query: str, rows: List[Dict]) -> List[Dict]:
        # SEARCH-1: full-text по title/username/url/notes + fuzzy + field filters title:"..."
        # поддержим поля: title, username, url, notes
        terms: List[str] = []
        field_filters: List[Tuple[str, str]] = []

        # простой разбор токенов с поддержкой двойных кавычек: key:"value"
        buff = ""
        in_quotes = False
        tokens: List[str] = []
        for ch in query:
            if ch == '"':
                in_quotes = not in_quotes
                continue
            if ch.isspace() and not in_quotes:
                if buff:
                    tokens.append(buff)
                    buff = ""
                continue
            buff += ch
        if buff:
            tokens.append(buff)

        for tok in tokens:
            if ":" in tok:
                k, v = tok.split(":", 1)
                k = k.strip().lower()
                v = v.strip()
                field_key = normalize_search_field(k)
                if field_key:
                    field_filters.append((field_key, v))
                    continue
            terms.append(tok)

        out: List[Dict] = []
        for r in rows:
            title = r.get("title", "") or ""
            username = r.get("username_masked", "") or ""
            url_domain = r.get("url_domain", "") or ""
            notes = r.get("notes", "") or ""

            # для fuzzy используем тоже masked username; для "username:" фильтра этого достаточно
            ok = True
            for k, v in field_filters:
                if k == "title":
                    hay = title
                elif k == "username":
                    hay = username
                elif k == "url":
                    hay = url_domain
                elif k == "notes":
                    hay = notes
                else:
                    hay = ""
                if self._similarity(hay, v) < 0.6:
                    ok = False
                    break
            if not ok:
                continue

            # free-text: все термины должны хотя бы немного совпасть с каким-то полем
            for term in terms:
                best = max(
                    self._similarity(title, term),
                    self._similarity(username, term),
                    self._similarity(url_domain, term),
                    self._similarity(notes, term),
                )
                if best < 0.6:
                    ok = False
                    break
            if ok:
                out.append(r)
        return out

    def _toggle_password_cell(self, entry_id: int, show: bool):
        # обновляет UI-ячейку и держит plaintext только пока show=True
        widget = self._password_widgets.get(entry_id)
        if not widget:
            return
        label, btn = widget
        if not show:
            label.setText("••••••••")
            btn.setText(t("password_btn_show"))
            btn.setToolTip(t("password_show"))
            if entry_id in self._password_revealed:
                # убираем ссылку на plaintext (SEC-1: не держим постоянно)
                del self._password_revealed[entry_id]
            return

        # show=True: расшифровываем пароль (требуется unlocked + PBKDF2 ключ в кэше)
        try:
            entry = self._entry_manager.get_entry(entry_id)
            pwd = entry.get("password") or ""
            self._password_revealed[entry_id] = pwd
            label.setText(pwd)
            btn.setText(t("password_btn_hide"))
            btn.setToolTip(t("password_hide"))
        except Exception as exc:
            self._show_error(exc)

    def _on_eye_clicked(self):
        btn = self.sender()
        if not isinstance(btn, QToolButton):
            return
        entry_id = int(btn.property("entry_id"))
        is_shown = entry_id in self._password_revealed
        self._toggle_password_cell(entry_id, show=not is_shown)

    def _on_global_toggle_passwords(self, checked: bool):
        # GUI-3: глобальный toggle + Ctrl+Shift+P
        self._global_show_passwords = bool(checked)
        # выделение по строкам (selectedItems не видит ячейку с виджетом пароля — только QTableWidgetItem)
        selected_ids = set()
        sm = self._table.selectionModel()
        if sm is not None:
            for idx in sm.selectedRows():
                item = self._table.item(idx.row(), 0)
                if item is not None:
                    eid = item.data(Qt.ItemDataRole.UserRole)
                    if eid is not None:
                        selected_ids.add(int(eid))
        cur_row = self._table.currentRow()
        if cur_row >= 0:
            item = self._table.item(cur_row, 0)
            if item is not None:
                eid = item.data(Qt.ItemDataRole.UserRole)
                if eid is not None:
                    selected_ids.add(int(eid))
        # явный «показать всё» по тулбару: если строк не выделили — все видимые записи
        if not selected_ids and checked:
            selected_ids = set(self._password_widgets.keys())

        if not selected_ids:
            if checked:
                self._act_toggle_passwords.blockSignals(True)
                self._act_toggle_passwords.setChecked(False)
                self._act_toggle_passwords.blockSignals(False)
                self._global_show_passwords = False
            else:
                for eid in list(self._password_revealed.keys()):
                    self._toggle_password_cell(eid, show=False)
            return

        for eid in selected_ids:
            self._toggle_password_cell(eid, show=self._global_show_passwords)

        if not self._global_show_passwords:
            for eid in list(self._password_revealed.keys()):
                self._toggle_password_cell(eid, show=False)

    def _on_context_menu(self, pos):
        # GUI-3: контекстное меню (правая кнопка мыши)
        idx = self._table.indexAt(pos)
        if not idx.isValid():
            return
        row = idx.row()
        self._table.selectRow(row)
        # берём id из ячейки "Название" (колонка 0)
        item = self._table.item(row, 0)
        entry_id = int(item.data(Qt.ItemDataRole.UserRole)) if item else None
        if entry_id is None:
            return

        from PyQt6.QtWidgets import QMenu

        menu = QMenu(self)
        a_copy_login = menu.addAction(t("copy_login"))
        a_copy_password = menu.addAction(t("copy_password"))
        a_copy_all = menu.addAction(t("clipboard_copy_all"))
        a_clear = menu.addAction(t("clipboard_manual_clear"))
        menu.addSeparator()
        a_edit = menu.addAction(t("edit_"))
        a_delete = menu.addAction(t("delete"))

        action = menu.exec(self._table.viewport().mapToGlobal(pos))
        if action == a_copy_login:
            self._copy_selected_login(entry_id)
        elif action == a_copy_password:
            self._copy_selected_password(entry_id)
        elif action == a_copy_all:
            self._copy_selected_all(entry_id)
        elif action == a_clear:
            self._on_clear_clipboard()
        elif action == a_edit:
            self._on_edit(entry_id_override=entry_id)
        elif action == a_delete:
            self._on_delete(entry_id_override=entry_id)

    def _on_add(self):
        if not self._require_unlocked():
            return
        get_state_manager().touch_activity()
        try:
            from .entry_dialog import EntryDialog
            d = EntryDialog(self, is_edit=False)
            if not d.exec():
                return
            data = d.get_data()
            self._entry_manager.create_entry(data)
            self._load_table()
        except Exception as exc:
            self._show_error(exc)

    def _on_edit(self, entry_id_override=None):
        if not self._require_unlocked():
            return
        get_state_manager().touch_activity()
        entry_id = entry_id_override if entry_id_override is not None else self._get_selected_entry_id()
        if entry_id is None:
            QMessageBox.information(self, t("edit_"), t("select_entry_edit"))
            return
        try:
            entry = self._entry_manager.get_entry(entry_id)
            from .entry_dialog import EntryDialog
            d = EntryDialog(
                self,
                title=entry.get("title", "") or "",
                username=entry.get("username", "") or "",
                password=entry.get("password", "") or "",
                url=entry.get("url", "") or "",
                notes=entry.get("notes", "") or "",
                category=entry.get("category", "") or "",
                is_edit=True,
            )
            if not d.exec():
                return
            data = d.get_data()
            self._entry_manager.update_entry(entry_id, data)
            self._load_table()
        except Exception as exc:
            self._show_error(exc)

    def _on_delete(self, entry_id_override=None):
        if not self._require_unlocked():
            return
        get_state_manager().touch_activity()
        entry_id = entry_id_override if entry_id_override is not None else self._get_selected_entry_id()
        if entry_id is None:
            QMessageBox.information(self, t("delete"), t("select_entry_delete"))
            return
        if QMessageBox.question(
            self, t("delete"), t("confirm_delete"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            self._entry_manager.delete_entry(entry_id, soft_delete=True)
            self._load_table()
        except Exception as exc:
            self._show_error(exc)

    def _copy_to_clipboard(self, entry_id, text, kind):
        if get_state_manager().is_locked():
            QMessageBox.information(self, t("app_title"), t("session_locked_action"))
            return
        data_type = {"password": "password", "all": "all", "login": "username"}.get(kind, "text")
        self._clipboard_service.copy_text(text or "", data_type=data_type, source_entry_id=entry_id)

    def _copy_selected_login(self, entry_id: int):
        get_state_manager().touch_activity()
        try:
            entry = self._entry_manager.get_entry(entry_id)
            self._copy_to_clipboard(entry_id, (entry.get("username", "") or "").strip(), "login")
        except Exception as exc:
            self._show_error(exc)

    def _copy_selected_password(self, entry_id: int):
        get_state_manager().touch_activity()
        try:
            entry = self._entry_manager.get_entry(entry_id)
            self._copy_to_clipboard(entry_id, entry.get("password", "") or "", "password")
        except Exception as exc:
            self._show_error(exc)

    def _copy_selected_all(self, entry_id: int):
        get_state_manager().touch_activity()
        try:
            entry = self._entry_manager.get_entry(entry_id)
            data = "\n".join(
                [
                    str(entry.get("title", "") or ""),
                    str(entry.get("username", "") or ""),
                    str(entry.get("password", "") or ""),
                    str(entry.get("url", "") or ""),
                    str(entry.get("notes", "") or ""),
                ]
            ).strip()
            self._copy_to_clipboard(entry_id, data, "all")
        except Exception as exc:
            self._show_error(exc)

    def _on_copy_login(self):
        entry_id = self._get_selected_entry_id()
        if entry_id is None:
            QMessageBox.information(self, t("copy_login"), t("select_entry_edit"))
            return
        self._copy_selected_login(entry_id)

    def _on_copy_password(self):
        entry_id = self._get_selected_entry_id()
        if entry_id is None:
            QMessageBox.information(self, t("copy_password"), t("select_entry_edit"))
            return
        self._copy_selected_password(entry_id)

    def _on_copy_all(self):
        entry_id = self._get_selected_entry_id()
        if entry_id is None:
            QMessageBox.information(self, t("clipboard_copy_all"), t("select_entry_edit"))
            return
        self._copy_selected_all(entry_id)

    def _on_clear_clipboard(self):
        self._clipboard_service.clear(reason="manual")

    def _on_change_password(self):
        get_state_manager().touch_activity()
        from .change_password_dialog import ChangePasswordDialog
        d = ChangePasswordDialog(self)
        d.exec()

    def _on_logs(self):
        from .view_windows import AuditLogViewer
        self._audit_log_window = self._touch_and_open_side_window(AuditLogViewer, "logs")

    def _on_about(self):
        QMessageBox.about(self, t("app_title"), t("about_text"))

    def _on_settings(self):
        get_state_manager().touch_activity()
        from .settings_dialog import SettingsDialog
        d = SettingsDialog(self)
        if d.exec():
            self._buffer_seconds = int(config.get(config.CLIPBOARD_TIMEOUT, "30") or "30")
            get_state_manager().set_clipboard_timeout(self._buffer_seconds)
            get_panic_mode().set_stealth_enabled(int(config.get(config.PANIC_STEALTH_MODE, "0") or "0") > 0)
            self._start_activity_monitor()
            self._apply_theme_and_language()

    def _selected_entry_ids(self) -> List[int]:
        selected_ids = set()
        sm = self._table.selectionModel()
        if sm is not None:
            for idx in sm.selectedRows():
                item = self._table.item(idx.row(), 0)
                if item:
                    eid = item.data(Qt.ItemDataRole.UserRole)
                    if eid is not None:
                        selected_ids.add(int(eid))
        return list(selected_ids)

    def _on_export_vault(self):
        if not self._require_unlocked():
            return
        get_state_manager().touch_activity()
        if not self._all_entries_cache:
            QMessageBox.information(self, t("s6_export"), t("vault_empty"))
            return
        dlg = ExportDialog(self, lambda: [self._entry_manager.get_entry(r["id"]) for r in self._all_entries_cache], self._selected_entry_ids())
        dlg.exec()

    def _on_import_vault(self):
        get_state_manager().touch_activity()

        def _create(entry_data):
            return self._entry_manager.create_entry(entry_data)

        def _list():
            return self._entry_manager.get_all_entries()

        def _delete_all():
            rows = database_db.get_all_vault_entries()
            for row in rows:
                database_db.delete_vault_entry(int(row[0]))

        importer = VaultImporter(create_entry=_create, list_entries=_list, delete_all=_delete_all)
        dlg = ImportDialog(self, importer)
        if dlg.exec():
            self._load_table()

    def _on_share_entry(self):
        get_state_manager().touch_activity()
        entry_id = self._get_selected_entry_id()
        if entry_id is None:
            QMessageBox.information(self, t("s6_share"), t("select_entry_edit"))
            return

        def _provider():
            return self._entry_manager.get_entry(entry_id)

        dlg = ShareDialog(self, _provider)
        dlg.exec()

    def _on_qr_viewer(self):
        get_state_manager().touch_activity()
        dlg = QRViewerDialog(self)
        dlg.exec()

    def _apply_theme_and_language(self):
        from .theme import apply_theme
        apply_theme(QApplication.instance())
        self.setWindowTitle(t("app_title"))
        self.menuBar().clear()
        self._build_menu()
        sm = get_state_manager()
        self._status_label.setText(t("status_locked") if sm.is_locked() else t("status_unlocked"))
        self._buffer_label.setText(t("buffer_timer") % str(sm.get_clipboard_seconds_left()))
        self._table.setHorizontalHeaderLabels(
            [t("title"), t("login"), t("url"), t("last_modified"), t("notes"), t("password_field")]
        )
        self._refresh_localized_ui()
        clip = self._clipboard_service.get_status()
        self._apply_clipboard_status(clip)

    def _mask_preview(self, value: str) -> str:
        v = value or ""
        if len(v) <= 3:
            return "•••"
        return v[:3] + "••••••"

    def _on_clipboard_status_changed(self, status: Dict):
        # callback может приходить из таймера, UI обновляем через main-thread очередь
        QTimer.singleShot(0, lambda: self._apply_clipboard_status(status))

    def _apply_clipboard_status(self, status: Dict):
        if not status.get("active"):
            self._clipboard_status_label.setText(t("clipboard_status_idle"))
            self.statusBar().showMessage(t("clipboard_cleared_status"), 1500)
            return
        data_type = status.get("data_type", "text")
        source = status.get("source_entry_id")
        source_label = str(source) if source is not None else t("clipboard_source_unknown")
        self._clipboard_status_label.setText(t("clipboard_copied_type") % data_type)
        self.statusBar().showMessage(t("clipboard_preview_hidden") % (data_type, source_label), 1500)

    def _on_external_clipboard_change(self, _new_value: str):
        QTimer.singleShot(0, self._clipboard_service.clear_if_active_data_replaced)

    def closeEvent(self, event):
        """Quits the application and cleans up clipboard and tray. / Завершает приложение и очищает буфер и трей."""
        event.accept()
        self._cleanup_on_exit()
        QApplication.quit()
