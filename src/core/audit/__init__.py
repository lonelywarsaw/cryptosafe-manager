"""Audit package: event registration and log integrity verification. / Пакет аудита: регистрация событий и проверка целостности журнала."""

from .audit_logger import register
from .integrity import verify_integrity

__all__ = ["register", "verify_integrity"]
