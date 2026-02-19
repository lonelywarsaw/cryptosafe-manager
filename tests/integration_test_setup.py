import unittest
import tempfile
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.config import Config, get_config
from src.database.db import Database
from src.database.audit import register_audit_handlers
from src.core.events import event_bus, entry_added

class TestIntegrationSetup(unittest.TestCase):
    def test_config_loading(self):
        with tempfile.TemporaryDirectory() as d:
            config = get_config(config_dir=Path(d), env="development")
            self.assertEqual(config.config_dir, Path(d))
            self.assertIn("cryptosafe", str(config.database_path))

    def test_first_run_db_creation(self):
        with tempfile.TemporaryDirectory() as d:
            db_path = Path(d) / "vault.db"
            db = Database(db_path)
            db.init_schema()
            self.assertTrue(db_path.exists())
            self.assertEqual(db.get_schema_version(), 1)
            db.close()

    def test_audit_subscribes_and_logs(self):
        with tempfile.TemporaryDirectory() as d:
            db = Database(Path(d) / "audit.db")
            db.init_schema()
            register_audit_handlers(db)
            event_bus.publish(entry_added, {"entry_id": 1, "details": "test"})
            rows = db.fetchall("SELECT * FROM audit_log")
            self.assertGreaterEqual(len(rows), 1)
            db.close()

if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestIntegrationSetup)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)
