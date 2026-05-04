# главное окно: меню (файл, правка, вид, справка), таблица записей, статус-бар, таймер буфера обмена

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QMenuBar, QStatusBar,
    QLabel, QMessageBox, QFileDialog, QApplication, QTableWidgetItem,
    QLineEdit, QHBoxLayout, QToolBar, QPushButton
)
from PyQt6.QtCore import QTimer, Qt, QEvent
from PyQt6.QtGui import QAction

import difflib
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
from .strings import t
from .widgets.secure_table import SecureTable


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        sm = get_state_manager()
        self._buffer_seconds = int(config.get(config.CLIPBOARD_TIMEOUT, "30") or "30")
        sm.set_clipboard_timeout(self._buffer_seconds)

        # (спринт3) контроллер vault: CRUD + AES-GCM шифрование/дешифрование
        km = get_key_manager()
        self._entry_manager = EntryManager(database_db, km, events)
        self._all_entries_cache: List[Dict] = []
        self._password_revealed: Dict[int, str] = {}  # entry_id -> plaintext password
        self._password_widgets: Dict[int, Tuple[QLabel, QPushButton]] = {}
        self._global_show_passwords = False

        # (спринт4) сервис буфера обмена: авто-очистка, события, Observer
        self._clipboard_service = ClipboardService(create_platform_adapter())
        self._clipboard_service.subscribe(self._on_clipboard_status_changed)
        self._clipboard_monitor = ClipboardMonitor(self._clipboard_service.adapter)
        self._clipboard_monitor.set_on_change(self._on_external_clipboard_change)

        self._build_ui()
        self._build_menu()
        self._build_status_bar()
        self._start_buffer_timer()
        self._clipboard_monitor.start()

    def changeEvent(self, event):
        # (CACHE-2, спринт2) при минимизации — автосброс ключа/блокировка
        super().changeEvent(event)
        try:
            if event.type() == QEvent.Type.WindowStateChange:
                lock_on_min = int(config.get(config.LOCK_ON_MINIMIZE, "1") or "1")
                if lock_on_min > 0 and not get_state_manager().is_locked() and self.isMinimized():
                    self._do_auto_lock()
        except Exception:
            pass

    def focusOutEvent(self, event):
        # (CACHE-2, спринт2) при потере фокуса — автосброс ключа/блокировка
        super().focusOutEvent(event)
        try:
            lock_on_focus = int(config.get(config.LOCK_ON_FOCUS_LOST, "1") or "1")
            if lock_on_focus > 0 and not get_state_manager().is_locked():
                self._do_auto_lock()
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
        self._search.textChanged.connect(self._on_search_changed)
        layout.addWidget(self._search)

        self._table = SecureTable(self)
        # context menu (GUI-2 / GUI-3): правый клик по строке
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._on_context_menu)
        self._load_table()
        layout.addWidget(self._table)

        # toolbar: глобальный toggle видимости паролей (GUI-3, спринт4: локализованный текст)
        tb = QToolBar(t("clipboard_toolbar_title"), self)
        tb.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, tb)
        self._act_toggle_passwords = QAction(t("clipboard_toolbar_show_passwords"), self)
        self._act_toggle_passwords.setCheckable(True)
        self._act_toggle_passwords.setChecked(False)
        self._act_toggle_passwords.setShortcut("Ctrl+Shift+P")
        self._act_toggle_passwords.toggled.connect(self._on_global_toggle_passwords)
        tb.addAction(self._act_toggle_passwords)

    def _build_menu(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu(t("file"))
        file_menu.addAction(t("new"), self._on_new)
        file_menu.addAction(t("open"), self._on_open)
        file_menu.addAction(t("unlock"), self._on_unlock)
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
        edit_menu.addAction(t("clipboard_copy_all"), self._on_copy_all)
        edit_menu.addAction(t("clipboard_manual_clear"), self._on_clear_clipboard)
        edit_menu.addSeparator()
        edit_menu.addAction(t("change_password_title"), self._on_change_password)
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
        if prev == 1 and left == 0:
            try:
                self._clipboard_service.clear(reason="timer_tick")
            except Exception:
                pass
        if left == 5 and self._clipboard_service.get_status().get("active"):
            self.statusBar().showMessage(t("clipboard_warning_soon_clear"), 1500)
        # авто-блокировка: если прошло больше N минут без действий — блокируем сессию
        auto_lock_min = int(config.get(config.AUTO_LOCK_MINUTES, "5") or "5")
        if auto_lock_min > 0 and not sm.is_locked() and sm.get_inactivity_seconds() >= auto_lock_min * 60:
            self._do_auto_lock()

    def _do_auto_lock(self):
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
        # чтобы тесты не зависали из-за модального окна
        try:
            import sys
            if "pytest" in sys.modules:
                return
        except Exception:
            pass
        QMessageBox.information(self, t("app_title"), t("session_locked_inactivity"))

    def _on_unlock(self):
        get_state_manager().touch_activity()
        from .unlock_dialog import UnlockDialog
        d = UnlockDialog(self)
        if d.exec():
            self.set_locked(False)

    def reset_buffer_timer(self):
        sm = get_state_manager()
        sm.reset_clipboard_timer()
        self._buffer_label.setText(t("buffer_timer") % str(sm.get_clipboard_seconds_left()))

    def set_locked(self, locked):
        get_state_manager().set_locked(locked)
        self._status_label.setText(t("status_locked") if locked else t("status_unlocked"))

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

    def _show_error(self):
        # показ общего сообщения об ошибке (без деталей, чтобы не светить реализацию)
        # (спринт3) если тесты под pytest — не показываем модальное окно, чтобы не блокировать run
        try:
            import sys
            if "pytest" in sys.modules:
                return
        except Exception:
            pass
        QMessageBox.warning(self, t("app_title"), t("error_generic"))

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
        path, _ = QFileDialog.getSaveFileName(self, t("backup"), "", "Database (*.db)")
        if path:
            pass

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

            # GUI-3: (eye icon) — ячейка пароля
            cell = QWidget()
            hb = QHBoxLayout(cell)
            hb.setContentsMargins(0, 0, 0, 0)
            label = QLabel(masked_password)
            btn = QPushButton(t("password_show"))
            btn.setMinimumWidth(72)
            hb.addWidget(label)
            hb.addWidget(btn)

            btn.setProperty("entry_id", entry_id)
            btn.clicked.connect(self._on_eye_clicked)

            self._table.setCellWidget(i, 5, cell)
            self._password_widgets[entry_id] = (label, btn)

    def _load_table(self):
        try:
            self._all_entries_cache = self._entry_manager.get_all_entries()
            self._apply_search_filter_and_fill()
        except Exception:
            self._show_error()
            self._table.setRowCount(0)

    def _apply_search_filter_and_fill(self):
        query = (self._search.text() or "").strip()
        if not query:
            self._fill_table(self._all_entries_cache)
            return
        filtered = self._filter_entries(query, self._all_entries_cache)
        self._fill_table(filtered)

    def _on_search_changed(self, _):
        # SEARCH-2: realtime обновление результатов
        try:
            self._apply_search_filter_and_fill()
        except Exception:
            self._show_error()

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
                if k in ("title", "username", "url", "notes"):
                    field_filters.append((k, v))
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
            btn.setText(t("password_show"))
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
            btn.setText(t("password_hide"))
        except Exception:
            # без деталей (SEC-4)
            self._show_error()

    def _on_eye_clicked(self):
        # GUI-3: переключение видимости пароля через кнопку-глаз
        btn = self.sender()
        if not isinstance(btn, QPushButton):
            return
        entry_id = int(btn.property("entry_id"))
        is_shown = entry_id in self._password_revealed
        self._toggle_password_cell(entry_id, show=not is_shown)

    def _on_global_toggle_passwords(self, checked: bool):
        # GUI-3: глобальный toggle + Ctrl+Shift+P
        self._global_show_passwords = bool(checked)
        # показываем/скрываем пароли только у выбранных строк, чтобы не расшифровывать всё подряд
        selected = self._table.selectedItems()
        selected_ids = set()
        for it in selected:
            eid = it.data(Qt.ItemDataRole.UserRole)
            if eid is not None:
                selected_ids.add(int(eid))
        if not selected_ids:
            # если выделения нет — используем текущую строку
            cur_item = self._table.currentItem()
            if cur_item is not None:
                eid = cur_item.data(Qt.ItemDataRole.UserRole)
                if eid is not None:
                    selected_ids.add(int(eid))

        if not selected_ids:
            return

        for eid in selected_ids:
            self._toggle_password_cell(eid, show=self._global_show_passwords)

        if not self._global_show_passwords:
            # скрываем все раскрытые пароли
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
        get_state_manager().touch_activity()
        try:
            from .entry_dialog import EntryDialog
            d = EntryDialog(self, is_edit=False)
            if not d.exec():
                return
            data = d.get_data()
            self._entry_manager.create_entry(data)
            self._load_table()
        except Exception:
            self._show_error()

    def _on_edit(self, entry_id_override=None):
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
        except Exception:
            self._show_error()

    def _on_delete(self, entry_id_override=None):
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
        except Exception:
            self._show_error()

    def _copy_to_clipboard(self, entry_id, text, kind):
        # текст копируется через ClipboardService (спринт4), таймер/события обрабатываются внутри сервиса
        if not text:
            return
        # vault должен быть разблокирован (SEC-4), проверяем state_manager
        if get_state_manager().is_locked():
            QMessageBox.warning(self, t("app_title"), t("error_generic"))
            return
        data_type = "password" if kind == "password" else "username"
        self._clipboard_service.copy_text(text, data_type=data_type, source_entry_id=entry_id)

    def _copy_selected_login(self, entry_id: int):
        get_state_manager().touch_activity()
        try:
            entry = self._entry_manager.get_entry(entry_id)
            self._copy_to_clipboard(entry_id, (entry.get("username", "") or "").strip(), "login")
        except Exception:
            self._show_error()

    def _copy_selected_password(self, entry_id: int):
        get_state_manager().touch_activity()
        try:
            entry = self._entry_manager.get_entry(entry_id)
            self._copy_to_clipboard(entry_id, entry.get("password", "") or "", "password")
        except Exception:
            self._show_error()

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
        except Exception:
            self._show_error()

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
        self._table.setHorizontalHeaderLabels(
            [t("title"), t("login"), t("url"), t("last_modified"), t("notes"), t("password_field")]
        )

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
        left = status.get("remaining_seconds", 0)
        source = status.get("source_entry_id")
        source_label = str(source) if source is not None else t("clipboard_source_unknown")
        self._clipboard_status_label.setText(t("clipboard_copied_status") % (data_type, str(left)))
        self.statusBar().showMessage(t("clipboard_preview_hidden") % (data_type, source_label), 1500)

    def _on_external_clipboard_change(self, _new_value: str):
        self._clipboard_service.clear_if_active_data_replaced()

    def closeEvent(self, event):
        try:
            self._clipboard_monitor.stop()
            self._clipboard_service.clear(reason="app_close")
        except Exception:
            pass
        super().closeEvent(event)
