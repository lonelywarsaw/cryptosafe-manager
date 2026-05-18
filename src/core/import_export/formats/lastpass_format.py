# LastPass CSV (спринт 6, IMP-1)

import csv
import io
from typing import Any, Dict, List

LASTPASS_FIELDS = ("url", "username", "password", "extra", "name", "grouping", "fav")


def lastpass_to_entries(text: str) -> List[Dict[str, Any]]:
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
