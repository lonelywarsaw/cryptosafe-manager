# Техническое описание — CryptoSafe Manager

## Архитектура

MVC-подобное разделение:

| Слой | Каталог | Назначение |
|------|---------|------------|
| View | `src/gui/` | PyQt6: главное окно, диалоги, трей |
| Controller | `src/core/` | Конфиг, крипто, события, vault, clipboard, audit, import/export, security |
| Model | `src/database/` | SQLite: записи, аудит, key_store, история IE |

Связь компонентов — шина событий `core/events.py` (sync и async).

## Криптография

| Этап | Механизм |
|------|----------|
| Мастер-пароль | Argon2id → `auth_hash` в `key_store` |
| Ключ записей | PBKDF2-HMAC-SHA256 + соль → 32 байта в кэше (`key_manager`) |
| Запись | AES-256-GCM, nonce 12 байт, BLOB `nonce ‖ ciphertext ‖ tag` |
| Экспорт/шаринг | Отдельный HKDF `info`; одноразовый `data_key` на операцию |
| Аудит | HMAC-SHA256 + hash chain (`previous_hash`) |

## Схема БД (SCHEMA_VERSION 5)

- `vault_entries` — зашифрованные записи
- `audit_log` — подписанные события
- `key_store` — `auth_hash`, `enc_salt`
- `shared_entries`, `import_export_history` — спринт 6
- Настройки приложения — отдельный `config.db` (`core/config.py`)

## Спринт 7: `core/security/`

- `side_channel_protection` — `secrets.compare_digest`
- `memory_guard` — secure wipe, опционально `VirtualLock` (Windows)
- `activity_monitor` — фоновый idle + Windows `GetLastInputInfo`
- `panic_mode` — цепочка обработчиков + аудит
- `security_profiles` — пресеты Standard / Enhanced / Paranoid

## Спринт 8: резервные копии

Формат `cryptosafe-backup-v1` в ZIP: `vault.db`, `manifest.json` (SHA-256, schema_version, entry_count).

## Сборка

```bash
pip install pyinstaller
python scripts/build_executable.py
```

Результат: `dist/CryptoSafeManager/`.

## Тесты

```bash
pytest tests/ -q --ignore=tests/test_integration.py
python scripts/generate_test_report.py
```

Отчёты: `tests/report/summary.md`, `coverage.xml`, `junit.xml`.
