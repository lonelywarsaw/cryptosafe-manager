# Тесты конфига — чтение, значение по умолчанию для неизвестного ключа.
import unittest

from core import config


class TestConfigurationLoading(unittest.TestCase):
    # Читаем из конфига, проверяем дефолты.

    def test_get_returns_default_for_unknown_key(self):
        self.assertEqual(config.get("__test_unknown_key_xyz__", "default"), "default")

    def test_get_returns_default_none(self):
        self.assertIsNone(config.get("__test_unknown_abc__", None))
