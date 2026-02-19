import json
import os
from pathlib import Path

default_db_name = "cryptosafe.db"
default_config_dir = Path.home() / ".cryptosafe"
app_config_file = "app_config.json"

class Config:
    def __init__(self, config_dir=None, env="production"):
        self.env = env if env in ("development", "production") else "production"
        self._config_dir = Path(config_dir) if config_dir else default_config_dir
        self._config_dir.mkdir(parents=True, exist_ok=True)
        self._cache = {}
        self._load_file()

    def _config_path(self):
        return self._config_dir / app_config_file

    def _load_file(self):
        p = self._config_path()
        if not p.exists():
            return
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("theme") in ("light", "dark", "system"):
                self._cache["theme"] = data["theme"]
            if data.get("language") in ("ru", "en"):
                self._cache["language"] = data["language"]
            if "clipboard_timeout" in data and 0 <= int(data["clipboard_timeout"]) <= 300:
                self._cache["clipboard_timeout"] = int(data["clipboard_timeout"])
            if "auto_lock_minutes" in data and 0 <= int(data["auto_lock_minutes"]) <= 120:
                self._cache["auto_lock_minutes"] = int(data["auto_lock_minutes"])
        except Exception:
            pass

    def _save_file(self):
        try:
            data = {
                "theme": self._cache.get("theme", "light"),
                "language": self._cache.get("language", "ru"),
                "clipboard_timeout": self._cache.get("clipboard_timeout", 30),
                "auto_lock_minutes": self._cache.get("auto_lock_minutes", 5),
            }
            with open(self._config_path(), "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=0)
        except Exception:
            pass

    @property
    def config_dir(self):
        return self._config_dir

    @property
    def database_path(self):
        if "database_path" not in self._cache:
            self._cache["database_path"] = self._config_dir / default_db_name
        return self._cache["database_path"]

    def set_database_path(self, path):
        self._cache["database_path"] = Path(path)

    @property
    def encryption_enabled(self):
        return self._cache.get("encryption_enabled", True)

    def set_encryption_enabled(self, value):
        self._cache["encryption_enabled"] = value

    @property
    def clipboard_timeout(self):
        return self._cache.get("clipboard_timeout", 30)

    def set_clipboard_timeout(self, seconds):
        if seconds < 0 or seconds > 300:
            raise ValueError("Clipboard timeout 0-300")
        self._cache["clipboard_timeout"] = seconds
        self._save_file()

    @property
    def auto_lock_minutes(self):
        return self._cache.get("auto_lock_minutes", 5)

    def set_auto_lock_minutes(self, minutes):
        if minutes < 0 or minutes > 120:
            raise ValueError("Auto-lock 0-120 min")
        self._cache["auto_lock_minutes"] = minutes
        self._save_file()

    @property
    def theme(self):
        return self._cache.get("theme", "light")

    def set_theme(self, value):
        if value in ("light", "dark", "system"):
            self._cache["theme"] = value
            self._save_file()

    @property
    def language(self):
        return self._cache.get("language", "ru")

    def set_language(self, value):
        if value in ("ru", "en"):
            self._cache["language"] = value
            self._save_file()

    def load_from_db(self, db):
        try:
            keys = ["app_theme", "app_language", "app_clipboard_timeout", "app_auto_lock_minutes"]
            names = ["theme", "language", "clipboard_timeout", "auto_lock_minutes"]
            for key, name in zip(keys, names):
                row = db.fetchone("SELECT setting_value FROM settings WHERE setting_key = ?", (key,))
                if not row or row[0] is None:
                    continue
                val = row[0].decode("utf-8") if isinstance(row[0], bytes) else str(row[0])
                if name == "theme" and val in ("light", "dark", "system"):
                    self._cache["theme"] = val
                elif name == "language" and val in ("ru", "en"):
                    self._cache["language"] = val
                elif name == "clipboard_timeout":
                    v = int(val)
                    if 0 <= v <= 300:
                        self._cache["clipboard_timeout"] = v
                elif name == "auto_lock_minutes":
                    v = int(val)
                    if 0 <= v <= 120:
                        self._cache["auto_lock_minutes"] = v
        except Exception:
            pass

    def save_to_db(self, db):
        try:
            opts = [
                ("app_theme", self._cache.get("theme", "light")),
                ("app_language", self._cache.get("language", "ru")),
                ("app_clipboard_timeout", str(self._cache.get("clipboard_timeout", 30))),
                ("app_auto_lock_minutes", str(self._cache.get("auto_lock_minutes", 5))),
            ]
            with db.cursor() as cur:
                for key, val in opts:
                    cur.execute("DELETE FROM settings WHERE setting_key = ?", (key,))
                    cur.execute("INSERT INTO settings (setting_key, setting_value, encrypted) VALUES (?, ?, 0)",
                                (key, val.encode("utf-8")))
        except Exception:
            pass

def get_config(config_dir=None, env=None):
    env = env or os.environ.get("CRYPTOSAFE_ENV", "production")
    return Config(config_dir=config_dir, env=env)
