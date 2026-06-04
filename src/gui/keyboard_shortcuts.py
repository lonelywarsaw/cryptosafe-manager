"""UX-1: keyboard shortcuts registry and help text. / Реестр горячих клавиш (спринт 7, UX-1)."""

from __future__ import annotations

from typing import List, Tuple

# (keys, strings.py label key) — shown in Help and user docs
SHORTCUT_REFERENCE: List[Tuple[str, str]] = [
    ("Ctrl+N", "shortcut_add"),
    ("Ctrl+E / F2", "shortcut_edit"),
    ("Enter", "shortcut_edit_enter"),
    ("Delete", "shortcut_delete"),
    ("Ctrl+F", "shortcut_focus_search"),
    ("Esc", "shortcut_escape_search"),
    ("Ctrl+Shift+U", "shortcut_copy_login"),
    ("Ctrl+Shift+C", "shortcut_copy_password"),
    ("Ctrl+Shift+A", "shortcut_copy_all"),
    ("Ctrl+Shift+B", "shortcut_clear_clipboard"),
    ("Ctrl+Shift+P", "shortcut_show_passwords"),
    ("Ctrl+Shift+O", "shortcut_unlock"),
    ("Ctrl+Shift+L", "shortcut_lock"),
    ("Ctrl+Shift+J", "shortcut_audit_log"),
    ("Ctrl+,", "shortcut_settings"),
    ("Ctrl+Shift+Esc", "shortcut_panic"),
]

# QAction / QShortcut bindings (single primary key each)
KEY_ADD = "Ctrl+N"
KEY_EDIT = "Ctrl+E"
KEY_COPY_LOGIN = "Ctrl+Shift+U"
KEY_COPY_PASSWORD = "Ctrl+Shift+C"
KEY_COPY_ALL = "Ctrl+Shift+A"
KEY_CLEAR_CLIPBOARD = "Ctrl+Shift+B"
KEY_FOCUS_SEARCH = "Ctrl+F"
KEY_UNLOCK = "Ctrl+Shift+O"
KEY_LOCK = "Ctrl+Shift+L"
KEY_AUDIT_LOG = "Ctrl+Shift+J"
KEY_SETTINGS = "Ctrl+,"


def format_shortcuts_help() -> str:
    """Plain-text shortcut list for Help dialog and docs."""
    from gui.strings import t

    lines = [t("shortcuts_help_title"), ""]
    for keys, label_key in SHORTCUT_REFERENCE:
        lines.append(f"  {keys} — {t(label_key)}")
    lines.append("")
    lines.append(t("shortcuts_nav_hint"))
    return "\n".join(lines)
