"""Clipboard security level and app whitelist from config. / Политика буфера обмена."""

from __future__ import annotations

import os
from typing import FrozenSet, Optional

from core import config

LEVEL_BASIC = "basic"
LEVEL_ADVANCED = "advanced"
LEVEL_PARANOID = "paranoid"

_LEVELS = frozenset({LEVEL_BASIC, LEVEL_ADVANCED, LEVEL_PARANOID})
_PARANOID_TIMEOUT_FACTOR = 0.7


def get_security_level() -> str:
    """Normalized clipboard security level from config."""
    raw = (config.get(config.CLIPBOARD_SECURITY_LEVEL, LEVEL_BASIC) or LEVEL_BASIC).strip().lower()
    return raw if raw in _LEVELS else LEVEL_BASIC


def parse_whitelist(raw: Optional[str] = None) -> FrozenSet[str]:
    """Parse comma/semicolon-separated process names (lowercase, basename)."""
    if raw is None:
        raw = config.get(config.CLIPBOARD_APP_WHITELIST, "") or ""
    names: set[str] = set()
    for chunk in str(raw).replace(";", ",").split(","):
        name = chunk.strip().lower()
        if name:
            names.add(os.path.basename(name))
    return frozenset(names)


def monitors_external_clipboard(level: Optional[str] = None) -> bool:
    """Whether external clipboard changes should trigger protection."""
    level = level or get_security_level()
    return level in (LEVEL_ADVANCED, LEVEL_PARANOID)


def effective_clipboard_timeout(base_timeout: int, level: Optional[str] = None) -> int:
    """Apply level-specific timeout adjustment (paranoid shortens timer)."""
    level = level or get_security_level()
    timeout = max(5, min(300, int(base_timeout)))
    if level == LEVEL_PARANOID:
        return max(5, int(timeout * _PARANOID_TIMEOUT_FACTOR))
    return timeout


def normalize_process_name(name: Optional[str]) -> str:
    if not name:
        return ""
    return os.path.basename(str(name).strip()).lower()


def process_in_whitelist(process_name: Optional[str], whitelist: FrozenSet[str]) -> bool:
    """Match exe name or stem (chrome vs chrome.exe)."""
    norm = normalize_process_name(process_name)
    if not norm or not whitelist:
        return False
    if norm in whitelist:
        return True
    stem = norm[:-4] if norm.endswith(".exe") else norm
    for entry in whitelist:
        entry_stem = entry[:-4] if entry.endswith(".exe") else entry
        if norm == entry_stem or stem == entry or stem == entry_stem:
            return True
    return False


def should_clear_on_external_change(
    *,
    level: Optional[str] = None,
    digest_matches: bool,
    clipboard_empty: bool,
    foreground_process: Optional[str] = None,
    whitelist: Optional[FrozenSet[str]] = None,
) -> bool:
    """Return True if active secret should be cleared after an external clipboard event."""
    level = level or get_security_level()
    if not monitors_external_clipboard(level):
        return False
    if digest_matches:
        return False
    if level == LEVEL_PARANOID and clipboard_empty:
        return True
    if level == LEVEL_PARANOID:
        return True
    if level == LEVEL_ADVANCED:
        wl = whitelist if whitelist is not None else parse_whitelist()
        if process_in_whitelist(foreground_process, wl):
            return False
        return True
    return False
