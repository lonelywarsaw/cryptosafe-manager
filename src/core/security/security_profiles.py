"""Профили безопасности Standard / Enhanced / Paranoid и применение настроек."""

from typing import Any, Dict, List, Tuple

from core import config

PROFILE_STANDARD = "standard"
PROFILE_ENHANCED = "enhanced"
PROFILE_PARANOID = "paranoid"

PROFILES = (PROFILE_STANDARD, PROFILE_ENHANCED, PROFILE_PARANOID)

_PROFILE_SETTINGS: Dict[str, Dict[str, str]] = {
    PROFILE_STANDARD: {
        config.AUTO_LOCK_MINUTES: "5",
        config.CLIPBOARD_SECURITY_LEVEL: "basic",
        config.CLIPBOARD_TIMEOUT: "30",
        config.LOCK_ON_FOCUS_LOST: "0",
        config.LOCK_ON_MINIMIZE: "0",
        config.ACTIVITY_SENSITIVITY: "medium",
        config.MEMORY_LOCK_ENABLED: "0",
    },
    PROFILE_ENHANCED: {
        config.AUTO_LOCK_MINUTES: "3",
        config.CLIPBOARD_SECURITY_LEVEL: "advanced",
        config.CLIPBOARD_TIMEOUT: "20",
        config.LOCK_ON_FOCUS_LOST: "0",
        config.LOCK_ON_MINIMIZE: "1",
        config.ACTIVITY_SENSITIVITY: "high",
        config.MEMORY_LOCK_ENABLED: "1",
    },
    PROFILE_PARANOID: {
        config.AUTO_LOCK_MINUTES: "1",
        config.CLIPBOARD_SECURITY_LEVEL: "paranoid",
        config.CLIPBOARD_TIMEOUT: "15",
        config.LOCK_ON_FOCUS_LOST: "1",
        config.LOCK_ON_MINIMIZE: "1",
        config.ACTIVITY_SENSITIVITY: "high",
        config.MEMORY_LOCK_ENABLED: "1",
    },
}


def profile_settings(name: str) -> Dict[str, str]:
    """Return preset config key/value dict for a profile name."""
    return dict(_PROFILE_SETTINGS.get(name, {}))


def describe_profile(name: str) -> str:
    """Возвращает локализованное описание профиля."""
    try:
        from gui.strings import t

        key = f"profile_desc_{name}"
        text = t(key)
        if text != key:
            return text
    except Exception:
        pass
    labels = {
        PROFILE_STANDARD: "Баланс удобства и защиты (рекомендуется).",
        PROFILE_ENHANCED: "Усиленная защита: короче таймауты, блокировка при сворачивании.",
        PROFILE_PARANOID: "Максимальная защита: быстрая блокировка, строгий буфер обмена.",
    }
    return labels.get(name, "")


def validate_profile(name: str) -> Tuple[bool, str]:
    """Проверяет имя профиля и допустимость авто-блокировки.

    Returns:
        (успех, сообщение об ошибке).
    """
    if name not in PROFILES:
        return False, "Неизвестный профиль"
    minutes = int(_PROFILE_SETTINGS[name].get(config.AUTO_LOCK_MINUTES, "5"))
    if minutes < 1:
        return False, "Авто-блокировка не может быть меньше 1 минуты"
    return True, ""


def snapshot_current_settings() -> Dict[str, str]:
    """Снимок текущих настроек, затрагиваемых профилями."""
    keys = set()
    for profile in _PROFILE_SETTINGS.values():
        keys.update(profile.keys())
    keys.add(config.SECURITY_PROFILE)
    return {k: config.get(k) or "" for k in keys}


def apply_profile(name: str, *, revert_on_error: bool = True) -> None:
    """Применяет набор настроек профиля в config; при ошибке откатывает снимок."""
    ok, msg = validate_profile(name)
    if not ok:
        raise ValueError(msg)
    backup = snapshot_current_settings() if revert_on_error else {}
    try:
        for key, value in _PROFILE_SETTINGS[name].items():
            config.set(key, value)
        config.set(config.SECURITY_PROFILE, name)
    except Exception:
        if revert_on_error:
            for key, value in backup.items():
                if value:
                    config.set(key, value)
        raise
