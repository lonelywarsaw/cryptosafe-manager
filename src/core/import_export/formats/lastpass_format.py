"""LastPass CSV import/export compatibility layer. / Слой совместимости импорта/экспорта CSV LastPass."""

import csv
import io
from typing import Any, Dict, List

LASTPASS_FIELDS = ("url", "username", "password", "extra", "name", "grouping", "fav")

def entries_to_lastpass_csv(entries: List[Dict[str, Any]]) -> str:
    """Serializes entries to LastPass-compatible CSV columns. / Сериализует записи в CSV с колонками LastPass."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=LASTPASS_FIELDS, extrasaction="ignore")
    writer.writeheader()
    for e in entries:
        writer.writerow(
            {
                "url": e.get("url", "") or "",
                "username": e.get("username", "") or "",
                "password": e.get("password", "") or "",
                "extra": e.get("notes", "") or "",
                "name": e.get("title", "") or "",
                "grouping": e.get("category", "") or "",
                "fav": "0",
            }
        )
    return buf.getvalue()


def lastpass_to_entries(text: str) -> List[Dict[str, Any]]:
    """Parses LastPass CSV export into vault entry dictionaries. / Разбирает CSV-экспорт LastPass в словари записей."""
    buf = io.StringIO(text.strip())
    reader = csv.DictReader(buf)
    out: List[Dict[str, Any]] = []
    for row in reader:
        title = (row.get("name") or row.get("Name") or "").strip()
        username = (row.get("username") or row.get("Username") or "").strip()
        password = (row.get("password") or row.get("Password") or "").strip()
        url = (row.get("url") or row.get("URL") or "").strip()
        notes = (row.get("extra") or row.get("Extra") or "").strip()
        category = (row.get("grouping") or row.get("Grouping") or "").strip()
        if not any((title, username, password, url)):
            continue
        out.append(
            {
                "title": title or url or username,
                "username": username,
                "password": password,
                "url": url,
                "notes": notes,
                "category": category,
            }
        )
    return out
