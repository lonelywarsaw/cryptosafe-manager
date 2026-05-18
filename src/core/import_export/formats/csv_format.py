# CSV экспорт/импорт (спринт 6, EXP-3)

import csv
import io
from typing import Any, Dict, List

CSV_FIELDS = ("title", "username", "password", "url", "category", "notes")


def entries_to_csv(entries: List[Dict[str, Any]]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_FIELDS, extrasaction="ignore")
    writer.writeheader()
    for e in entries:
        row = {f: (e.get(f) or "") for f in CSV_FIELDS}
        writer.writerow(row)
    return buf.getvalue()


def csv_to_entries(text: str) -> List[Dict[str, Any]]:
    buf = io.StringIO(text.strip())
    reader = csv.DictReader(buf)
    if not reader.fieldnames:
        raise ValueError("Пустой CSV")
    out: List[Dict[str, Any]] = []
    for row in reader:
        item = {f: (row.get(f) or "").strip() for f in CSV_FIELDS}
        if any(item.values()):
            out.append(item)
    return out
