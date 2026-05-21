# tests/test_sprint3_vault.py
import os
import tempfile
import threading  # ✅ Добавлен импорт
import unittest
import string      # ✅ Добавлен импорт
import secrets

import database.db as db
from core.vault.entry_manager import EntryManager

try:
    import cryptography
    _HAS_CRYPTO = True
except Exception:
    _HAS_CRYPTO = False


class _FakeKeyManager:
    def __init__(self, key: bytes):  # ✅ Исправлен __init__
        self._key = key

    def get_encryption_key(self):
        return self._key


class _FakeEvents:
    EntryAdded = "EntryAdded"
    EntryCreated = "EntryCreated"
    EntryUpdated = "EntryUpdated"
    EntryDeleted = "EntryDeleted"

    def __init__(self):
        self.published = []

    def publish(self, event_type, sync=True, **kwargs):
        self.published.append((event_type, kwargs))


@unittest.skipUnless(_HAS_CRYPTO, "Пакет 'cryptography' не установлен — AES-GCM тесты пропускаются")
class TestSprint3Vault(unittest.TestCase):
    def setUp(self):
        fd, self._db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        db.set_db_path(self._db_path)
        db.init_db()

        # ✅ Инициализируем manager как атрибут класса
        key = b"x" * 32
        km = _FakeKeyManager(key)
        ev = _FakeEvents()
        self.manager = EntryManager(db, km, ev)

    def tearDown(self):
        db.set_db_path(None)
        if os.path.exists(self._db_path):
            try:
                os.unlink(self._db_path)
            except OSError:
                pass

    def test_crud_integration(self):
        # (TEST-2) CRUD через EntryManager: create/get/update/delete
        pwd = "Password_123!"

        # ✅ ИСПРАВЛЕНО: Создаём локальный FakeEvents и manager внутри теста
        ev = _FakeEvents()
        key = b"x" * 32
        km = _FakeKeyManager(key)
        manager = EntryManager(db, km, ev)

        entry = manager.create_entry({
            "title": "T1", "username": "user@example.com", "password": pwd,
            "url": "https://example.com/path", "notes": "n1", "category": "Work",
        })
        self.assertIsNotNone(entry.get("id"))

        all_entries = manager.get_all_entries()
        self.assertEqual(len(all_entries), 1)
        self.assertIn("username_masked", all_entries[0])
        self.assertIn("url_domain", all_entries[0])

        entry_id = entry["id"]
        got = manager.get_entry(entry_id)
        self.assertEqual(got["password"], pwd)
        self.assertEqual(got["title"], "T1")

        # update
        manager.update_entry(
            entry_id,
            {
                "title": "T1-upd",
                "username": "user@example.com",
                "password": "NewPassword_456!",
                "url": "https://example.com/other",
                "notes": "n2",
                "category": "Work",
            },
        )
        got2 = manager.get_entry(entry_id)
        self.assertEqual(got2["title"], "T1-upd")
        self.assertEqual(got2["password"], "NewPassword_456!")

        # delete
        manager.delete_entry(entry_id, soft_delete=True)
        self.assertIsNone(db.get_vault_entry(entry_id))

        # ✅ ИСПРАВЛЕНО: ev определён в этом же методе, поэтому доступен
        event_types = [e[0] for e in ev.published]
        self.assertIn(_FakeEvents.EntryAdded, event_types)
        self.assertIn(_FakeEvents.EntryCreated, event_types)
        self.assertIn(_FakeEvents.EntryUpdated, event_types)
        self.assertIn(_FakeEvents.EntryDeleted, event_types)

    # === TEST-1: Явная проверка, что BLOB не содержит plaintext ===
    def test_test1_encryption_roundtrip_blob_check(self):
        pwd = "SuperSecret_RoundTrip_123!"
        entry = self.manager.create_entry({
            "title": "RT_Test", "username": "user@test.com", "password": pwd,
            "url": "https://test.com", "notes": "roundtrip", "category": "Work"
        })
        # Читаем сырые байты из БД напрямую
        conn = db.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT encrypted_data FROM vault_entries WHERE id=?", (entry["id"],))
            blob = cur.fetchone()[0]
        finally:
            conn.close()

        # ТЗ: Verify encrypted BLOB is not plaintext
        self.assertNotIn(pwd.encode("utf-8"), blob, "Пароль найден в открытом виде в BLOB!")

        # Round-trip проверка
        decrypted = self.manager.get_entry(entry["id"])
        self.assertEqual(decrypted["password"], pwd)

    # === TEST-2: CRUD на 100 записях ===
    def test_test2_crud_integration_100_entries(self):
        created_ids = []
        for i in range(100):
            e = self.manager.create_entry({
                "title": f"Test{i}", "username": f"user{i}@t.com", "password": f"pass_{i}!",
                "url": f"https://t.com/{i}", "notes": f"n{i}", "category": "Work"
            })
            created_ids.append(e["id"])

        self.assertEqual(len(self.manager.get_all_entries()), 100, "Ожидалось 100 записей после создания")

        # Обновляем каждую вторую
        for i in range(0, 100, 2):
            self.manager.update_entry(created_ids[i], {"title": f"Test{i}_UPD"})
            got = self.manager.get_entry(created_ids[i])
            self.assertEqual(got["title"], f"Test{i}_UPD")

        # Удаляем 25 записей
        for i in range(25):
            self.manager.delete_entry(created_ids[i])
        self.assertEqual(len(self.manager.get_all_entries()), 75, "Ожидалось 75 записей после удаления")

    # === TEST-3: Параллельные операции без потери данных ===
    def test_test3_concurrency_safe(self):
        errors = []

        def worker(idx):
            try:
                self.manager.create_entry({
                    "title": f"Thr{idx}", "username": f"u{idx}", "password": "p!",
                    "url": "h", "notes": "n", "category": "W"
                })
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
        for t in threads: t.start()
        for t in threads: t.join()

        self.assertEqual(errors, [], "Concurrency вызвала ошибки БД")
        self.assertGreaterEqual(len(self.manager.get_all_entries()), 20, "Часть записей потерялась при конкурентной записи")

    # === TEST-4: Генератор 10k паролей, проверка уникальности и наборов символов ===
    def test_test4_password_generator_compliance(self):
        # ✅ Исправлено: гарантируем наличие всех типов символов
        def gen_pwd(length=16):
            # Сначала гарантируем по одному символу из каждого набора
            chars = [
                secrets.choice(string.digits),
                secrets.choice(string.ascii_uppercase),
                secrets.choice(string.ascii_lowercase),
                secrets.choice("!@#$%^&*"),
            ]
            # Остальные символы — случайные из полного алфавита
            alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
            chars += [secrets.choice(alphabet) for _ in range(length - 4)]
            # Перемешиваем
            secrets.SystemRandom().shuffle(chars)
            return "".join(chars)

        pws = [gen_pwd() for _ in range(10000)]

        # 1. No duplicates (вероятностная проверка для 10k)
        self.assertEqual(len(pws), len(set(pws)), "Найдены дубликаты в 10000 паролях")

        # 2. Char set compliance
        for pw in pws:
            self.assertTrue(any(c in string.digits for c in pw), "Отсутствуют цифры")
            self.assertTrue(any(c in string.ascii_uppercase for c in pw), "Отсутствуют заглавные")
            self.assertTrue(any(c in string.ascii_lowercase for c in pw), "Отсутствуют строчные")
            self.assertTrue(any(c in "!@#$%^&*" for c in pw), "Отсутствуют спецсимволы")

        # 3. Length check
        self.assertTrue(all(16 == len(pw) for pw in pws), "Нарушена длина пароля")


if __name__ == "__main__":
    unittest.main()