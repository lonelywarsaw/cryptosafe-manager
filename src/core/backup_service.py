"""Vault backup and restore as .csafe.zip archives. / Резервное копирование и восстановление."""

import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from core import config, events
from database import db as database_db
from database import models

BACKUP_EXTENSION = ".csafe.zip"
MANIFEST_NAME = "manifest.json"
VAULT_DB_NAME = "vault.db"
CONFIG_DB_NAME = "config.db"


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _normalize_backup_dest(dest_path: str) -> str:
    dest_path = (dest_path or "").strip()
    low = dest_path.lower()
    if low.endswith(BACKUP_EXTENSION):
        return dest_path
    if low.endswith(".zip"):
        return dest_path
    return dest_path + BACKUP_EXTENSION


def _vault_db_path() -> str:
    raw = (config.get(config.DB_PATH) or "").strip()
    if raw:
        path = os.path.abspath(os.path.expanduser(os.path.expandvars(raw)))
        if os.path.isfile(path):
            return path
    path = database_db.get_vault_path()
    if os.path.isfile(path):
        return path
    raise FileNotFoundError("База хранилища не найдена")


def create_backup(dest_path: str, *, include_config: bool = True) -> Dict[str, Any]:
    """Write signed zip backup; returns manifest. / Создаёт zip-архив резервной копии."""
    dest_path = _normalize_backup_dest(dest_path)
    parent = os.path.dirname(os.path.abspath(dest_path))
    if parent:
        os.makedirs(parent, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="csafe-backup-") as tmp_dir:
        snapshot = os.path.join(tmp_dir, VAULT_DB_NAME)
        database_db.backup_vault_to(snapshot)

        manifest: Dict[str, Any] = {
            "format": "cryptosafe-backup-v1",
            "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "schema_version": models.SCHEMA_VERSION,
            "vault_checksum": _sha256_file(snapshot),
            "entry_count": _count_entries(snapshot),
            "include_config": bool(include_config),
        }

        with zipfile.ZipFile(dest_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.write(snapshot, arcname=VAULT_DB_NAME)
            if include_config:
                cfg_path = config._config_path()
                if os.path.isfile(cfg_path):
                    manifest["config_checksum"] = _sha256_file(cfg_path)
                    zf.write(cfg_path, arcname=CONFIG_DB_NAME)
            zf.writestr(MANIFEST_NAME, json.dumps(manifest, ensure_ascii=False, indent=2))

    manifest["archive_path"] = dest_path
    events.publish(events.BackupCreated, sync=True, path=dest_path, entries=manifest.get("entry_count", 0))
    return manifest


def _count_entries(db_path: str) -> int:
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM vault_entries")
        row = cur.fetchone()
        return int(row[0]) if row else 0
    finally:
        conn.close()


def validate_backup(archive_path: str) -> Dict[str, Any]:
    """Verify backup format and vault checksum. / Проверяет архив и контрольную сумму."""
    if not os.path.isfile(archive_path):
        raise FileNotFoundError("Архив не найден")
    with zipfile.ZipFile(archive_path, "r") as zf:
        names = set(zf.namelist())
        if MANIFEST_NAME not in names or VAULT_DB_NAME not in names:
            raise ValueError("Неверный формат резервной копии")
        manifest = json.loads(zf.read(MANIFEST_NAME).decode("utf-8"))
        if manifest.get("format") != "cryptosafe-backup-v1":
            raise ValueError("Неподдерживаемая версия резервной копии")
        tmp_dir = tempfile.mkdtemp(prefix="csafe-verify-")
        try:
            vault_tmp = os.path.join(tmp_dir, VAULT_DB_NAME)
            with open(vault_tmp, "wb") as out:
                out.write(zf.read(VAULT_DB_NAME))
            checksum = _sha256_file(vault_tmp)
            if checksum != manifest.get("vault_checksum"):
                raise ValueError("Контрольная сумма vault.db не совпадает")
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
    return manifest


def restore_backup(archive_path: str, *, restore_config: bool = False) -> Dict[str, Any]:
    """Restore vault.db from validated archive. / Восстанавливает vault.db из архива."""
    manifest = validate_backup(archive_path)
    vault_path = _vault_db_path()
    backup_old = vault_path + ".before-restore"
    if os.path.isfile(vault_path):
        shutil.copy2(vault_path, backup_old)

    database_db.close_all_connections()
    try:
        from core.audit.audit_logger import clear_chain_cache

        clear_chain_cache()
    except Exception:
        pass

    with zipfile.ZipFile(archive_path, "r") as zf:
        with open(vault_path, "wb") as out:
            out.write(zf.read(VAULT_DB_NAME))
        if restore_config and CONFIG_DB_NAME in zf.namelist():
            cfg_path = config._config_path()
            if os.path.isfile(cfg_path):
                shutil.copy2(cfg_path, cfg_path + ".before-restore")
            with open(cfg_path, "wb") as out:
                out.write(zf.read(CONFIG_DB_NAME))

    events.publish(events.BackupRestored, sync=True, path=archive_path)
    return manifest
