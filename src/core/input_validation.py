# валидация и очистка ввода: обрезка длины, удаление управляющих и непечатаемых символов

import re

# максимальные длины полей, чтобы не класть в бд слишком длинные строки
MAX_TITLE_LEN = 500
MAX_USERNAME_LEN = 500
MAX_URL_LEN = 2000
MAX_NOTES_LEN = 2000
MAX_MASTER_PASSWORD_LEN = 512
# символы управления и непечатаемые (null, переносы и т.п.) вырезаются
CONTROL_OR_NONPRINT = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitize_text(text, max_len=None):
    # строка: обрезка пробелов по краям, удаление управляющих символов, обрезка по max_len
    if text is None:
        return ""
    s = str(text).strip()
    s = CONTROL_OR_NONPRINT.sub("", s)
    if max_len is not None and len(s) > max_len:
        s = s[:max_len]
    return s


def validate_title(title):
    # заголовок очищается; возвращается (очищенная строка, True если не пустая)
    s = sanitize_text(title, MAX_TITLE_LEN)
    return s, len(s) > 0


def sanitize_username(value):
    return sanitize_text(value, MAX_USERNAME_LEN)


def sanitize_url(value):
    return sanitize_text(value, MAX_URL_LEN)


def sanitize_notes(value):
    return sanitize_text(value, MAX_NOTES_LEN)
