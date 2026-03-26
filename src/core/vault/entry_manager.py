from typing import Any, Dict, List
from urllib.parse import urlparse

from core.vault.encryption_service import EncryptionServiceAESGCM

# db — это module-уровень API из src/database/db.py
from database import db as database_db


def _mask_username(username: str) -> str:
    username = (username or "").strip()
    if len(username) <= 4:
        return "••••"
    # показываем первые 4 символа, дальше маска
    return username[:4] + "••••"


def _extract_domain(url: str) -> str:
    u = (url or "").strip()
    if not u:
        return ""
    # Если пользователь ввёл без схемы — urlparse вернёт "псевдо-host" в path
    if "://" not in u:
        u = "https://" + u
    parsed = urlparse(u)
    return parsed.netloc or u


class EntryManager:
    # Контроллер CRUD (спринт3).
    # Он шифрует/дешифрует через EncryptionServiceAESGCM,
    # а ключ берётся из KeyManager (кэш после PBKDF2).
    def __init__(self, db_module, key_manager, event_module):
        self._db = db_module
        self._key_manager = key_manager
        self._events = event_module
        self._crypto = EncryptionServiceAESGCM(key_manager)

    def create_entry(self, data_dict: Dict[str, Any]) -> Dict[str, Any]:
        # транзакция: db.py сам коммитит по завершению операции
        created_at = self._crypto.now_timestamp()
        payload = self._crypto.build_payload_for_encrypt(data_dict, created_at=created_at)

        encrypted = self._crypto.encrypt_entry_payload(payload).encrypted_blob

        tags = data_dict.get("tags") or data_dict.get("category") or ""
        entry_id = self._db.insert_vault_entry(encrypted_data=encrypted, tags=tags)

        # событие публикуем здесь (CRUD-3)
        self._events.publish(self._events.EntryCreated, sync=True, entry_id=entry_id)
        # оставляем поддержку существующих подписчиков (аудит/тесты) на EntryAdded
        self._events.publish(self._events.EntryAdded, sync=True, entry_id=entry_id)
        return self.get_entry(entry_id)

    def get_entry(self, entry_id: int) -> Dict[str, Any]:
        row = self._db.get_vault_entry(entry_id)
        if not row:
            raise ValueError("Entry not found")

        _id, encrypted_data, created_at, updated_at, tags = row
        payload = self._crypto.decrypt_entry_payload(encrypted_data)

        # пароль возвращаем как строку: именно это нужно для редактирования/копирования
        # (SEC-1: в памяти хранится только пока окно/действие это требует)
        return {
            "id": _id,
            "title": payload.get("title", ""),
            "username": payload.get("username", ""),
            "password": payload.get("password", ""),
            "url": payload.get("url", ""),
            "notes": payload.get("notes", ""),
            "category": payload.get("category", ""),
            "version": payload.get("version", 1),
            "created_at": created_at or payload.get("created_at"),
            "updated_at": updated_at,
            "tags": tags or "",
        }

    def get_all_entries(self) -> List[Dict[str, Any]]:
        rows = self._db.get_all_vault_entries()
        out: List[Dict[str, Any]] = []
        for r in rows:
            entry_id, encrypted_data, created_at, updated_at, tags = r
            payload = self._crypto.decrypt_entry_payload(encrypted_data)

            # SEC-1: для списка паролей не возвращаем, чтобы UI не держал секрет постоянно
            out.append(
                {
                    "id": entry_id,
                    "title": payload.get("title", ""),
                    "username_masked": _mask_username(payload.get("username", "")),
                    "url_domain": _extract_domain(payload.get("url", "")),
                    "url": payload.get("url", ""),
                    "notes": payload.get("notes", ""),
                    "updated_at": updated_at,
                    "tags": tags or payload.get("category", ""),
                }
            )
        return out

    def update_entry(self, entry_id: int, data_dict: Dict[str, Any]) -> Dict[str, Any]:
        # берём created_at из текущей записи (чтобы payload сохранял целостность таймштампа)
        row = self._db.get_vault_entry(entry_id)
        if not row:
            raise ValueError("Entry not found")
        _, encrypted_data_old, created_at, updated_at_old, tags_old = row

        # транзакционно: db.update_vault_entry сам делает UPDATE и коммит
        created_at_use = created_at or self._crypto.now_timestamp()
        payload = self._crypto.build_payload_for_encrypt(data_dict, created_at=created_at_use)
        encrypted_new = self._crypto.encrypt_entry_payload(payload).encrypted_blob

        tags = data_dict.get("tags") or data_dict.get("category") or tags_old or ""
        self._db.update_vault_entry(entry_id, encrypted_data=encrypted_new, tags=tags)

        self._events.publish(self._events.EntryUpdated, sync=True, entry_id=entry_id)
        return self.get_entry(entry_id)

    def delete_entry(self, entry_id: int, soft_delete: bool = True):
        # soft_delete по ТЗ указан как Should — здесь реализуем только hard delete,
        # но парамет оставляем, чтобы API соответствовал требованиям.
        if soft_delete:
            # из-за отсутствия deleted_entries таблицы (спринт 4) делаем hard delete
            pass

        self._db.delete_vault_entry(entry_id)
        self._events.publish(self._events.EntryDeleted, sync=True, entry_id=entry_id)

