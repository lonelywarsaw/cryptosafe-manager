# импорт с валидацией и режимами merge/replace/dry-run (спринт 6, IMP)

import json
import re
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from core import events

from .formats.bitwarden_format import bitwarden_to_entries
from .formats.csv_format import csv_to_entries
from .formats.json_format import FORMAT_ID, parse_encrypted_export
from .formats.lastpass_format import lastpass_to_entries

DEFAULT_MAX_BYTES = 10 * 1024 * 1024
DEFAULT_TIMEOUT_SEC = 30

CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
SCRIPT_TAG = re.compile(r"<\s*script", re.IGNORECASE)
FIELD_LIMITS = {
    "title": 512,
    "username": 512,
    "password": 1024,
    "url": 2048,
    "notes": 8192,
    "category": 256,
}


class ImportResult:
    def __init__(self):
        self.added: List[Dict[str, Any]] = []
        self.updated: List[Dict[str, Any]] = []
        self.skipped: List[Dict[str, Any]] = []
        self.errors: List[str] = []


def _sanitize_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    out = {}
    for key, limit in FIELD_LIMITS.items():
        val = str(entry.get(key) or "")
        val = CONTROL_CHARS.sub("", val)
        if key == "notes":
            val = SCRIPT_TAG.sub("", val)
        out[key] = val[:limit].strip()
    return out


def _validate_entry(entry: Dict[str, Any]) -> bool:
    return bool(entry.get("title") or entry.get("username") or entry.get("password"))


def detect_format(text: str, path: Optional[str] = None) -> str:
    stripped = text.strip()
    if stripped.startswith("{"):
        data = json.loads(stripped)
        if data.get("format") == FORMAT_ID:
            return "encrypted_json"
        if "items" in data:
            return "bitwarden"
        if data.get("format", "").startswith("cryptosafe-share"):
            return "share"
    if path and path.lower().endswith(".csv"):
        return "csv"
    if "url,username,password" in stripped.split("\n", 1)[0].lower():
        return "lastpass_csv"
    return "csv"


class VaultImporter:
    def __init__(
        self,
        *,
        create_entry: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
        list_entries: Optional[Callable[[], List[Dict[str, Any]]]] = None,
        delete_all: Optional[Callable[[], None]] = None,
        max_bytes: int = DEFAULT_MAX_BYTES,
        timeout_sec: int = DEFAULT_TIMEOUT_SEC,
    ):
        self._create = create_entry
        self._list = list_entries or (lambda: [])
        self._delete_all = delete_all
        self._max_bytes = max_bytes
        self._timeout_sec = timeout_sec

    def _guard_io(self, path: Path, started: float) -> bytes:
        if time.monotonic() - started > self._timeout_sec:
            raise TimeoutError("Превышено время импорта")
        size = path.stat().st_size
        if size > self._max_bytes:
            raise ValueError(f"Файл больше лимита ({self._max_bytes} байт)")
        return path.read_bytes()

    def parse_file(
        self,
        path: str,
        *,
        export_password: str = "",
        private_key_pem: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        started = time.monotonic()
        p = Path(path)
        raw = self._guard_io(p, started)
        text = raw.decode("utf-8", errors="replace")
        fmt = detect_format(text, str(p))
        if fmt == "encrypted_json":
            data = json.loads(text)
            if data.get("format") != FORMAT_ID:
                raise ValueError("Неверный зашифрованный пакет")
            return [_sanitize_entry(e) for e in parse_encrypted_export(data, export_password, private_key_pem=private_key_pem)]
        if fmt == "bitwarden":
            entries = bitwarden_to_entries(text)
        elif fmt == "lastpass_csv":
            entries = lastpass_to_entries(text)
        else:
            entries = csv_to_entries(text)
        return [_sanitize_entry(e) for e in entries if _validate_entry(_sanitize_entry(e))]

    def import_file(
        self,
        path: str,
        mode: str,
        *,
        export_password: str = "",
        duplicate_policy: str = "skip",
        private_key_pem: Optional[str] = None,
    ) -> ImportResult:
        # mode: merge | replace | dry_run
        if mode not in ("merge", "replace", "dry_run"):
            raise ValueError("mode должен быть merge, replace или dry_run")
        entries = self.parse_file(path, export_password=export_password, private_key_pem=private_key_pem)
        result = self._apply(entries, mode, duplicate_policy)
        if mode != "dry_run":
            events.publish(
                events.VaultImported,
                sync=True,
                mode=mode,
                added=len(result.added),
                updated=len(result.updated),
            )
        return result

    def _find_duplicate(self, entry: Dict[str, Any], existing: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        title = (entry.get("title") or "").lower()
        user = (entry.get("username") or "").lower()
        for e in existing:
            if (e.get("title") or "").lower() == title and (e.get("username") or "").lower() == user:
                return e
        return None

    def _apply(self, entries: List[Dict[str, Any]], mode: str, duplicate_policy: str) -> ImportResult:
        result = ImportResult()
        existing = self._list()
        if mode == "replace":
            if mode != "dry_run" and self._delete_all:
                self._delete_all()
            existing = []

        for entry in entries:
            if not _validate_entry(entry):
                result.skipped.append(entry)
                continue
            dup = self._find_duplicate(entry, existing)
            if dup:
                if duplicate_policy == "skip":
                    result.skipped.append(entry)
                    continue
                if duplicate_policy == "update":
                    if mode == "dry_run":
                        result.updated.append(entry)
                        continue
            if mode == "dry_run":
                result.added.append(entry)
                continue
            if not self._create:
                result.errors.append("create_entry не задан")
                break
            created = self._create(entry)
            result.added.append(created)
            existing.append(created)
        return result
