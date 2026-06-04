"""User-facing error messages without stack traces. / Сообщения об ошибках для пользователя без трассировок."""

from __future__ import annotations

import re
from typing import Any, Optional

from .strings import t

_TRACE_MARKERS = ("Traceback (most recent call last)", "File \"", "line ", "  File ")


def _looks_like_traceback(text: str) -> bool:
    return any(marker in text for marker in _TRACE_MARKERS)


def user_facing_error(exc: Optional[BaseException] = None, *, fallback_key: str = "error_generic") -> str:
    """Maps an exception to a safe localized message. / Преобразует исключение в безопасное локализованное сообщение.

    Args:
        exc: Caught exception, if any.
        fallback_key: String key when the error cannot be classified.

    Returns:
        Text suitable for QMessageBox (no stack traces or file paths).
    """
    if exc is None:
        return t(fallback_key)

    if isinstance(exc, TimeoutError):
        return t("err_timeout")

    if isinstance(exc, FileNotFoundError):
        return t("err_file_not_found")

    if isinstance(exc, PermissionError):
        return t("err_permission")

    if isinstance(exc, ValueError):
        msg = str(exc).strip()
        if not msg or _looks_like_traceback(msg):
            return t(fallback_key)
        low = msg.lower()
        if "pem" in low or "malformedframing" in low:
            return t("s6_invalid_pem")
        if "превышено время" in low or "timeout" in low:
            return t("err_timeout")
        if "больше лимита" in low or "limit" in low:
            return t("err_file_too_large")
        if "мастер" in low or "master" in low:
            return t("err_wrong_master_password")
        if "экспорт" in low or "export" in low:
            return t("s6_export_failed_generic")
        if "импорт" in low or "import" in low:
            return t("s6_import_failed_generic")
        if len(msg) > 200:
            return t(fallback_key)
        return msg

    if isinstance(exc, OSError):
        err_no = getattr(exc, "errno", None)
        if err_no in (2,):
            return t("err_file_not_found")
        if err_no in (13,):
            return t("err_permission")
        return t(fallback_key)

    name = type(exc).__name__
    if name in ("VerifyMismatchError",):
        return t("wrong_password")
    if "PEM" in name or "MalformedFraming" in name:
        return t("s6_invalid_pem")

    raw = str(exc).strip()
    if not raw or _looks_like_traceback(raw) or re.search(r'[A-Za-z]:\\[^\s]+|/[\w./-]+\.py', raw):
        return t(fallback_key)
    if len(raw) > 200:
        return t(fallback_key)
    return raw


def format_operation_error(
    exc: BaseException,
    *,
    context: str = "generic",
) -> str:
    """Error text for import/export/share/QR operations. / Текст ошибки для импорта/экспорта/обмена/QR."""
    key_map = {
        "export": "s6_export_failed_generic",
        "import": "s6_import_failed_generic",
        "share": "s6_share_failed_generic",
        "qr": "s6_qr_failed_generic",
        "settings": "error_generic",
        "backup": "backup_failed_generic",
        "generic": "error_generic",
    }
    fallback_key = key_map.get(context, "error_generic")
    if context == "backup" and isinstance(exc, FileNotFoundError):
        return t("db_not_found")
    if isinstance(exc, (TimeoutError, FileNotFoundError, PermissionError, OSError)):
        return user_facing_error(exc, fallback_key=fallback_key)
    if isinstance(exc, ValueError):
        msg = user_facing_error(exc, fallback_key=fallback_key)
        raw = str(exc).strip()
        if raw and msg != raw and msg != t(fallback_key):
            return msg
    return t(fallback_key)
