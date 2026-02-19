import sqlite3
import shutil
import threading
from pathlib import Path
from contextlib import contextmanager
from src.database.models import all_tables, schema_version

class Database:
    def __init__(self, path):
        self._path = Path(path)
        self._conn = None
        self._lock = threading.RLock()

    def _get_connection(self):
        if self._conn is None:
            self._conn = sqlite3.connect(str(self._path))
            self._conn.row_factory = sqlite3.Row
        return self._conn

    @contextmanager
    def cursor(self):
        with self._lock:
            conn = self._get_connection()
            cur = conn.cursor()
            try:
                yield cur
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                cur.close()

    def init_schema(self):
        with self.cursor() as cur:
            for sql in all_tables:
                cur.executescript(sql)
            cur.execute("PRAGMA user_version = " + str(schema_version))

    def get_schema_version(self):
        with self.cursor() as cur:
            cur.execute("PRAGMA user_version")
            row = cur.fetchone()
        return row[0] if row else 0

    def close(self):
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def execute(self, sql, params=None):
        with self._lock:
            conn = self._get_connection()
            cur = conn.cursor()
            if params:
                cur.execute(sql, params)
            else:
                cur.execute(sql)
            conn.commit()
            return cur

    def fetchall(self, sql, params=None):
        with self.cursor() as cur:
            if params:
                cur.execute(sql, params)
            else:
                cur.execute(sql)
            return list(cur.fetchall())

    def fetchone(self, sql, params=None):
        with self.cursor() as cur:
            if params:
                cur.execute(sql, params)
            else:
                cur.execute(sql)
            return cur.fetchone()

def backup_database(db_path, backup_path):
    shutil.copy2(db_path, backup_path)

def restore_database(backup_path, db_path):
    shutil.copy2(backup_path, db_path)
