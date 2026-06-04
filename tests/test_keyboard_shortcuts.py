"""UX-1: keyboard shortcuts registry and localized labels."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gui import keyboard_shortcuts as kbd
from gui import strings


@pytest.mark.parametrize("lang", ("ru", "en"))
def test_shortcut_reference_labels_exist(lang: str) -> None:
    for _keys, label_key in kbd.SHORTCUT_REFERENCE:
        assert label_key in strings.STRINGS[lang], f"missing {label_key} in {lang}"


def test_format_shortcuts_help_non_empty() -> None:
    text = kbd.format_shortcuts_help()
    assert "Ctrl+N" in text
    assert strings.t("shortcut_add") in text
    assert strings.t("shortcuts_nav_hint") in text


def test_primary_key_constants_non_empty() -> None:
    assert kbd.KEY_ADD
    assert kbd.KEY_SETTINGS == "Ctrl+,"
