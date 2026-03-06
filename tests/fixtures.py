# Временная БД для тестов — создаём перед тестом, удаляем после.
import os
import tempfile
import unittest


def get_test_db_path():
    # Создаём временный файл под БД.
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    return path


class TestDatabaseFixture(unittest.TestCase):
    # Перед каждым тестом поднимаем свою БД, после теста — удаляем.

    def setUp(self):
        self._db_path = get_test_db_path()
        import database.db as db
        db.set_db_path(self._db_path)
        db.init_db()

    def tearDown(self):
        import database.db as db
        db.set_db_path(None)
        if os.path.exists(self._db_path):
            try:
                os.unlink(self._db_path)
            except OSError:
                pass
