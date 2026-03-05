# Тексты кнопок и т.п. Русский и английский.

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import config

STRINGS = {
    "ru": {
        "app_title": "CryptoSafe Manager",
        "file": "Файл", "new": "Новый", "open": "Открыть", "backup": "Резервная копия", "exit": "Выход",
        "edit": "Правка", "add": "Добавить", "edit_": "Изменить", "delete": "Удалить", "copy_login": "Копировать логин", "copy_password": "Копировать пароль",
        "view": "Вид", "logs": "Журнал", "settings": "Настройки", "state_monitor": "Монитор состояния",
        "help": "Справка",
        "status_locked": "Заблокировано", "status_unlocked": "Разблокировано",
        "buffer_timer": "Буфер: %s с",
        "title": "Название", "login": "Логин", "url": "URL", "notes": "Заметки", "password_field": "Пароль", "title_required": "Название — обязательное поле.", "select_entry_edit": "Выберите запись для редактирования.", "select_entry_delete": "Выберите запись для удаления.", "confirm_delete": "Удалить выбранную запись?",
        "security": "Безопасность", "appearance": "Внешний вид", "advanced": "Дополнительно",
        "clipboard_timeout": "Таймаут буфера (сек)", "auto_lock": "Автоблокировка (мин)",
        "theme": "Тема", "language": "Язык", "theme_system": "Системная", "theme_dark": "Тёмная", "theme_light": "Светлая",
        "master_password": "Мастер-пароль", "confirm_password": "Подтверждение",
        "db_location": "Расположение базы данных", "db_location_required": "Выберите расположение базы данных.", "encryption_settings": "Настройки шифрования",
        "backup_export": "Резервная копия и экспорт", "apply": "Применить", "cancel": "Отмена", "ok": "ОК",
        "about": "О программе", "about_text": "CryptoSafe Manager\nЛокальный менеджер паролей.", "enter_master_password": "Введите мастер-пароль:", "master_password_hint": "Мастер-пароль задаётся при первой настройке (мастер первого запуска), не путать с паролями записей в таблице.", "login_title": "Вход", "password_required": "Введите мастер-пароль. Поле не может быть пустым.", "setup_first": "Сначала выполните первичную настройку (мастер-пароль ещё не задан).", "wrong_password": "Неверный мастер-пароль.", "error_generic": "Произошла ошибка. Повторите действие.",
        "password_too_long": "Пароль слишком длинный.", "passwords_dont_match": "Пароли не совпадают.",
        "state_session": "Сессия:", "state_clipboard": "Таймер буфера (с):", "state_inactivity": "Неактивность (с):",
    },
    "en": {
        "app_title": "CryptoSafe Manager",
        "file": "File", "new": "New", "open": "Open", "backup": "Backup", "exit": "Exit",
        "edit": "Edit", "add": "Add", "edit_": "Edit", "delete": "Delete", "copy_login": "Copy login", "copy_password": "Copy password",
        "view": "View", "logs": "Logs", "settings": "Settings", "state_monitor": "State monitor",
        "help": "Help",
        "status_locked": "Locked", "status_unlocked": "Unlocked",
        "buffer_timer": "Buffer: %s s",
        "title": "Title", "login": "Login", "url": "URL", "notes": "Notes", "password_field": "Password", "title_required": "Title is required.", "select_entry_edit": "Select an entry to edit.", "select_entry_delete": "Select an entry to delete.", "confirm_delete": "Delete the selected entry?",
        "security": "Security", "appearance": "Appearance", "advanced": "Advanced",
        "clipboard_timeout": "Clipboard timeout (sec)", "auto_lock": "Auto-lock (min)",
        "theme": "Theme", "language": "Language", "theme_system": "System", "theme_dark": "Dark", "theme_light": "Light",
        "master_password": "Master password", "confirm_password": "Confirm",
        "db_location": "Database location", "db_location_required": "Select database location.", "encryption_settings": "Encryption settings",
        "backup_export": "Backup and export", "apply": "Apply", "cancel": "Cancel", "ok": "OK",
        "about": "About", "about_text": "CryptoSafe Manager\nLocal password manager.", "enter_master_password": "Enter master password:", "master_password_hint": "Master password is set during first-run setup only; it is not the same as entry passwords in the table.", "login_title": "Login", "password_required": "Enter master password. The field cannot be empty.", "setup_first": "Complete initial setup first (master password not set).", "wrong_password": "Incorrect master password.", "error_generic": "An error occurred. Please try again.",
        "password_too_long": "Password is too long.", "passwords_dont_match": "Passwords do not match.",
        "state_session": "Session:", "state_clipboard": "Clipboard timer (s):", "state_inactivity": "Inactivity (s):",
    },
}


def t(key):
    lang = config.get(config.LANGUAGE, "ru")
    return STRINGS.get(lang, STRINGS["ru"]).get(key, key)
