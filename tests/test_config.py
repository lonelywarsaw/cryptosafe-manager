import unittest
import tempfile
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.config import Config, get_config
from src.database.db import Database

class TestConfig(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config = Config(config_dir=Path(self.temp_dir), env="development")

    def test_database_path(self):
        self.assertEqual(self.config.database_path.name, "cryptosafe.db")
        self.config.set_database_path("/tmp/other.db")
        self.assertEqual(self.config.database_path.name, "other.db")
        self.assertEqual(self.config.database_path.as_posix(), "/tmp/other.db")

    def test_clipboard_timeout_validation(self):
        self.config.set_clipboard_timeout(60)
        self.assertEqual(self.config.clipboard_timeout, 60)
        with self.assertRaises(ValueError):
            self.config.set_clipboard_timeout(400)
        with self.assertRaises(ValueError):
            self.config.set_clipboard_timeout(-1)

    def test_auto_lock_validation(self):
        self.config.set_auto_lock_minutes(10)
        self.assertEqual(self.config.auto_lock_minutes, 10)
        with self.assertRaises(ValueError):
            self.config.set_auto_lock_minutes(200)

    def test_get_config_factory(self):
        c = get_config(env="development")
        self.assertEqual(c.env, "development")

    def test_load_save_from_db(self):
        db_path = Path(self.temp_dir) / "test.db"
        db = Database(db_path)
        db.init_schema()
        try:
            self.config.set_theme("dark")
            self.config.set_language("en")
            self.config.set_clipboard_timeout(45)
            self.config.set_auto_lock_minutes(10)
            self.config.save_to_db(db)
            self.config.set_theme("light")
            self.config.set_language("ru")
            self.config.set_clipboard_timeout(30)
            self.config.set_auto_lock_minutes(5)
            self.config.load_from_db(db)
            self.assertEqual(self.config.theme, "dark")
            self.assertEqual(self.config.language, "en")
            self.assertEqual(self.config.clipboard_timeout, 45)
            self.assertEqual(self.config.auto_lock_minutes, 10)
        finally:
            db.close()

if __name__ == "__main__":
    unittest.main()
