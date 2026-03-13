# тесты конфига

import unittest
from core import config


class TestConfig(unittest.TestCase):
    def test_unknown_key_default(self):
        # для несуществующего ключа возвращается переданное значение по умолчанию
        self.assertEqual(config.get("_nonexistent_", "def"), "def")

    def test_unknown_key_none(self):
        # если ключа нет и default=None, возвращается None (чтобы отличать «нет значения» от пустой строки)
        self.assertIsNone(config.get("_nonexistent_", None))
