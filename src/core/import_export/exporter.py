# экспорт хранилища (спринт 6, EXP)

import json
import os
import secrets
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from core import events
from core.crypto.authentication import verify_master_password

from .export_crypto import derive_export_material
from .formats.bitwarden_format import entries_to_bitwarden
from .formats.csv_format import entries_to_csv
from .formats.json_format import build_encrypted_export


class ExportOptions:
    def __init__(
        self,
        *,
        include_notes: bool = True,
        compress: bool = False,
        key_bits: int = 256,
        entry_ids: Optional[List[int]] = None,
        recipient_public_key_pem: Optional[str] = None,
    ):
        self.include_notes = include_notes
        self.compress = compress
        self.key_bits = key_bits
        self.entry_ids = entry_ids
        self.recipient_public_key_pem = recipient_public_key_pem


class VaultExporter:
    def __init__(self, entry_provider):
        # entry_provider: callable() -> List[dict] полных записей (с password)
        self._entries = entry_provider

    def _select_entries(self, options: ExportOptions) -> List[Dict[str, Any]]:
        all_entries = self._entries()
        if not options.entry_ids:
            return all_entries
        ids = set(options.entry_ids)
        return [e for e in all_entries if e.get("id") in ids]

    def export_encrypted_json(
        self,
        export_password: str,
        *,
        master_password: Optional[str] = None,
        options: Optional[ExportOptions] = None,
    ) -> Dict[str, Any]:
        if master_password is not None and not verify_master_password(master_password):
            raise PermissionError("Неверный мастер-пароль")
        options = options or ExportOptions()
        if options.key_bits not in (128, 256):
            raise ValueError("Поддерживается key_bits 128 или 256")
        entries = self._select_entries(options)
        data_key = secrets.token_bytes(16 if options.key_bits == 128 else 32)
        _ = derive_export_material()  # ARC-2: отделение от vault-ключа
        package = build_encrypted_export(
            entries,
            export_password,
            include_notes=options.include_notes,
            compress=options.compress,
            data_key=data_key,
            recipient_public_key_pem=options.recipient_public_key_pem,
        )
        events.publish(
            events.VaultExported,
            sync=True,
            format="encrypted_json",
            entry_count=len(entries),
            selective=bool(options.entry_ids),
        )
        return package

    def write_encrypted_json_file(
        self,
        path: str,
        export_password: str,
        *,
        master_password: Optional[str] = None,
        options: Optional[ExportOptions] = None,
    ) -> str:
        package = self.export_encrypted_json(
            export_password,
            master_password=master_password,
            options=options,
        )
        return self._write_temp_json(path, package)

    def export_csv(self, *, encrypt: bool = False, export_password: str = "", options: Optional[ExportOptions] = None) -> str:
        options = options or ExportOptions()
        entries = self._select_entries(options)
        text = entries_to_csv(entries)
        if encrypt:
            if not export_password:
                raise ValueError("Нужен пароль для шифрования CSV")
            pkg = build_encrypted_export(
                [{"title": "csv-export", "username": "", "password": "", "url": "", "notes": text, "category": ""}],
                export_password,
                include_notes=True,
            )
            return json.dumps(pkg, ensure_ascii=False)
        events.publish(events.VaultExported, sync=True, format="csv", entry_count=len(entries), selective=bool(options.entry_ids))
        return text

    def export_bitwarden(self, options: Optional[ExportOptions] = None) -> str:
        options = options or ExportOptions()
        entries = self._select_entries(options)
        events.publish(events.VaultExported, sync=True, format="bitwarden", entry_count=len(entries), selective=bool(options.entry_ids))
        return entries_to_bitwarden(entries)

    @staticmethod
    def _write_temp_json(path: str, package: Dict[str, Any]) -> str:
        target = Path(path)
        fd, tmp = tempfile.mkstemp(suffix=target.suffix or ".json", dir=str(target.parent or "."))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(package, f, ensure_ascii=False, indent=2)
            if target.exists():
                target.unlink()
            os.replace(tmp, str(target))
        finally:
            if os.path.exists(tmp):
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
        return str(target)
