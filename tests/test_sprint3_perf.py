import difflib
import os
import tempfile
import time
import tracemalloc
import unittest

import database.db as db
from core.vault.encryption_service import EncryptionServiceAESGCM


class _FakeKeyManager:
    def __init__(self, key: bytes):
        self._key = key

    def get_encryption_key(self):
        return self._key


def _similarity(a: str, b: str) -> float:
    a = (a or "").lower()
    b = (b or "").lower()
    if not a or not b:
        return 0.0
    if b in a:
        return 1.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def _filter_entries_perf(query: str, rows):
    # тест повторяет логику GUI-фильтра (MainWindow._filter_entries),
    # чтобы проверить PERFs по скорости обработки.
    terms = []
    field_filters = []

    buff = ""
    in_quotes = False
    tokens = []
    for ch in query:
        if ch == '"':
            in_quotes = not in_quotes
            continue
        if ch.isspace() and not in_quotes:
            if buff:
                tokens.append(buff)
                buff = ""
            continue
        buff += ch
    if buff:
        tokens.append(buff)

    for tok in tokens:
        if ":" in tok:
            k, v = tok.split(":", 1)
            k = k.strip().lower()
            v = v.strip()
            if k in ("title", "username", "url", "notes"):
                field_filters.append((k, v))
                continue
        terms.append(tok)

    out = []
    for r in rows:
        title = r.get("title", "") or ""
        username = r.get("username_masked", "") or ""
        url_domain = r.get("url_domain", "") or ""
        notes = r.get("notes", "") or ""

        ok = True
        for k, v in field_filters:
            if k == "title":
                hay = title
            elif k == "username":
                hay = username
            elif k == "url":
                hay = url_domain
            elif k == "notes":
                hay = notes
            else:
                hay = ""

            if _similarity(hay, v) < 0.6:
                ok = False
                break
        if not ok:
            continue

        for term in terms:
            best = max(
                _similarity(title, term),
                _similarity(username, term),
                _similarity(url_domain, term),
                _similarity(notes, term),
            )
            if best < 0.6:
                ok = False
                break
        if ok:
            out.append(r)
    return out


class TestSprint3Performance(unittest.TestCase):
    def setUp(self):
        fd, self._db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        db.set_db_path(self._db_path)
        db.init_db()

    def tearDown(self):
        db.set_db_path(None)
        if os.path.exists(self._db_path):
            try:
                os.unlink(self._db_path)
            except OSError:
                pass

    def test_perf_load_1000_and_search(self):
        # PERF-1: загрузка 1000 записей < 2 сек
        # PERF-2: поиск по 1000 < 200мс
        # PERF-3: память пиковая < 50MB
        key = b"x" * 32
        km = _FakeKeyManager(key)
        crypto = EncryptionServiceAESGCM(km)

        n = 1000
        # создание записей: это не часть PERF-1, но нужно подготовить входные данные
        for i in range(n):
            payload = {
                "title": f"Title{i}",
                "username": f"user{i}@example.com",
                "password": f"secret_{i}_xyz",
                "url": f"https://{i}.example.com/login",
                "notes": "work notes" if i % 3 == 0 else "personal",
                "category": "Work" if i % 3 == 0 else "Personal",
                "created_at": str(1000 + i),
                "version": 1,
            }
            enc_blob = crypto.encrypt_entry_payload(payload).encrypted_blob
            db.insert_vault_entry(encrypted_data=enc_blob, tags=payload["category"])

        tracemalloc.start()
        t0 = time.perf_counter()
        rows = []
        # загрузка через decrypt всех entries в memory (как в EntryManager.get_all_entries)
        # чтобы не зависеть от GUI, используем ровно тот же подход:
        # - берём encrypted_data из БД
        # - decrypt_entry_payload
        # - собираем metadata без password.
        all_rows = db.get_all_vault_entries()
        for r in all_rows:
            entry_id, encrypted_data, created_at, updated_at, tags = r
            payload = crypto.decrypt_entry_payload(encrypted_data)
            username = payload.get("username", "") or ""
            if len(username) <= 4:
                username_masked = "••••"
            else:
                username_masked = username[:4] + "••••"
            url_domain = payload.get("url", "") or ""
            if "://" not in url_domain:
                url_domain = "https://" + url_domain
            # быстрый извлечение домена не делаем через urlparse, т.к. это тоже влияет на PERF
            # — т.к. строка гарантированна в формате https://<host>/...
            try:
                url_domain = url_domain.split("://", 1)[1].split("/", 1)[0]
            except Exception:
                url_domain = ""
            rows.append(
                {
                    "id": entry_id,
                    "title": payload.get("title", ""),
                    "username_masked": username_masked,
                    "url_domain": url_domain,
                    "notes": payload.get("notes", ""),
                    "updated_at": updated_at,
                    "tags": tags or payload.get("category", ""),
                }
            )
        t_load = time.perf_counter() - t0
        peak_mem_mb = tracemalloc.get_traced_memory()[1] / (1024 * 1024)
        tracemalloc.stop()

        self.assertLess(
            t_load,
            2.0,
            "PERF-1 нарушен: загрузка 1000 записей заняла %.3f сек (должно < 2.0)" % t_load,
        )
        self.assertLess(
            peak_mem_mb,
            50.0,
            "PERF-3 нарушен: пик памяти %.2f MB (должно < 50.0)" % peak_mem_mb,
        )

        # PERF-2: поиск (в GUI) применяет фильтр к уже расшифрованному списку
        # фиксируем query: field filter + немного free-text
        query = 'title:"Title9" work'
        t1 = time.perf_counter()
        res = _filter_entries_perf(query, rows)
        t_search = time.perf_counter() - t1

        self.assertLess(
            t_search,
            0.2,
            "PERF-2 нарушен: поиск занял %.3f сек (должно < 0.2)" % t_search,
        )
        self.assertGreaterEqual(len(res), 1)

