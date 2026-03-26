import secrets
import string
from dataclasses import dataclass
from typing import Dict, List


# Генератор паролей (спринт3):
# - только криптостойкая случайность через secrets.choice/randbelow
# - поддержка набора символов (upper/lower/digits/symbols)
# - исключение неоднозначных: l, I, 1, 0, O
# - гарантируем минимум 1 символ из каждого выбранного набора


AMBIGUOUS = set(["l", "I", "1", "0", "O"])
SYMBOLS = "!@#$%^&*"


@dataclass(frozen=True)
class PasswordGenConfig:
    length: int = 16
    use_upper: bool = True
    use_lower: bool = True
    use_digits: bool = True
    use_symbols: bool = True
    exclude_ambiguous: bool = True


class PasswordGenerator:
    def __init__(self):
        pass

    def _get_charset(self, cfg: PasswordGenConfig) -> Dict[str, str]:
        upper = string.ascii_uppercase
        lower = string.ascii_lowercase
        digits = string.digits

        if cfg.exclude_ambiguous:
            upper = "".join([c for c in upper if c not in AMBIGUOUS])
            lower = "".join([c for c in lower if c not in AMBIGUOUS])
            digits = "".join([c for c in digits if c not in AMBIGUOUS])

        return {
            "upper": upper if cfg.use_upper else "",
            "lower": lower if cfg.use_lower else "",
            "digits": digits if cfg.use_digits else "",
            "symbols": SYMBOLS if cfg.use_symbols else "",
        }

    def generate(self, cfg: PasswordGenConfig = PasswordGenConfig()) -> str:
        # длина (спринт3 GEN-2)
        length = int(cfg.length)
        if length < 8:
            length = 8
        if length > 64:
            length = 64

        charsets = self._get_charset(cfg)
        selected_sets: List[str] = [s for s in charsets.values() if s]
        if not selected_sets:
            # чтобы не генерировать пустоту
            raise ValueError("Не выбран ни один набор символов для пароля")

        # генерируем по минимум одному символу из каждого набора (GEN-3)
        required_chars: List[str] = [secrets.choice(s) for s in selected_sets]

        remaining = length - len(required_chars)
        all_chars = "".join(selected_sets)

        out_chars: List[str] = list(required_chars)
        for _ in range(max(0, remaining)):
            out_chars.append(secrets.choice(all_chars))

        # перемешиваем, чтобы порядок required не был виден
        # secrets.randbelow используем для Fisher-Yates
        for i in range(len(out_chars) - 1, 0, -1):
            j = secrets.randbelow(i + 1)
            out_chars[i], out_chars[j] = out_chars[j], out_chars[i]

        return "".join(out_chars)

