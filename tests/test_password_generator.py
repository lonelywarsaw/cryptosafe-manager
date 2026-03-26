import unittest

from core.vault.password_generator import AMBIGUOUS, PasswordGenConfig, PasswordGenerator, SYMBOLS
from core.crypto.authentication import validate_password_strength


class TestPasswordGenerator(unittest.TestCase):
    def test_generation_charset_and_ambiguous_exclusion(self):
        gen = PasswordGenerator()
        cfg = PasswordGenConfig(
            length=16,
            use_upper=True,
            use_lower=True,
            use_digits=True,
            use_symbols=True,
            exclude_ambiguous=True,
        )

        pwd = gen.generate(cfg)
        self.assertEqual(len(pwd), 16)
        for ch in pwd:
            self.assertNotIn(ch, AMBIGUOUS)

        # проверяем, что присутствуют символы из каждого выбранного набора
        has_upper = any("A" <= c <= "Z" and c not in ("I", "O") for c in pwd)
        has_lower = any("a" <= c <= "z" and c not in ("l",) for c in pwd)
        has_digits = any("2" <= c <= "9" for c in pwd)  # т.к. 0 и 1 убираем
        has_symbols = any(c in SYMBOLS for c in pwd)

        self.assertTrue(has_upper)
        self.assertTrue(has_lower)
        self.assertTrue(has_digits)
        self.assertTrue(has_symbols)

    def test_length_bounds(self):
        gen = PasswordGenerator()
        cfg = PasswordGenConfig(length=8)
        pwd = gen.generate(cfg)
        self.assertEqual(len(pwd), 8)

        cfg2 = PasswordGenConfig(length=64)
        pwd2 = gen.generate(cfg2)
        self.assertEqual(len(pwd2), 64)

    def test_generator_10k_unique_and_strength(self):
        # (TEST-4, спринт3) 10,000 паролей: без дублей, соблюдение наборов и валидатор силы
        gen = PasswordGenerator()
        cfg = PasswordGenConfig(
            length=16,
            use_upper=True,
            use_lower=True,
            use_digits=True,
            use_symbols=True,
            exclude_ambiguous=True,
        )

        seen = set()
        upper_present = True
        lower_present = True
        digits_present = True
        symbols_present = True

        for _ in range(10_000):
            pwd = gen.generate(cfg)
            self.assertEqual(len(pwd), 16)
            self.assertNotIn(pwd, seen, "Дубликат пароля обнаружен (должно быть 0)!")
            seen.add(pwd)

            # (SEC-3 / DIALOG-2, косвенно) пароль должен проходить валидатор силы
            ok, msg = validate_password_strength(pwd)
            if not ok:
                self.fail("Сгенерированный пароль не прошёл validate_password_strength: %s" % msg)

            # наборы символов должны присутствовать
            has_upper = any("A" <= c <= "Z" and c not in ("I", "O") for c in pwd)
            has_lower = any("a" <= c <= "z" and c not in ("l",) for c in pwd)
            has_digit = any(c.isdigit() for c in pwd)
            has_symbol = any(c in SYMBOLS for c in pwd)

            if not has_upper:
                upper_present = False
            if not has_lower:
                lower_present = False
            if not has_digit:
                digits_present = False
            if not has_symbol:
                symbols_present = False

        self.assertEqual(len(seen), 10_000)
        self.assertTrue(upper_present)
        self.assertTrue(lower_present)
        self.assertTrue(digits_present)
        self.assertTrue(symbols_present)

