"""Форматирование записей журнала для экспорта: JSON Lines и CSV."""

import csv
import io
import json
from typing import Any, Dict, List


def format_json_lines(rows: List[Dict[str, Any]]) -> str:
    """Сериализует строки в JSON Lines (по одному объекту на строку)."""
    lines = [json.dumps(r, ensure_ascii=False, sort_keys=True) for r in rows]
    return "\n".join(lines)


def format_csv(rows: List[Dict[str, Any]], fieldnames: List[str]) -> str:
    """Формирует CSV с заголовком по fieldnames."""
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow({k: r.get(k, "") for k in fieldnames})
    return buf.getvalue()
