# совместимость с JSON Bitwarden (спринт 6, EXP-4)

import json
from typing import Any, Dict, List


def entries_to_bitwarden(entries: List[Dict[str, Any]]) -> str:
    items = []
    for e in entries:
        items.append(
            {
                "type": 1,
                "name": e.get("title", "") or "",
                "login": {
                    "username": e.get("username", "") or "",
                    "password": e.get("password", "") or "",
                    "uris": [{"uri": e.get("url", "") or ""}] if e.get("url") else [],
                },
                "notes": e.get("notes", "") or "",
                "folder": e.get("category", "") or "",
            }
        )
    return json.dumps({"encrypted": False, "items": items}, ensure_ascii=False, indent=2)


def bitwarden_to_entries(text: str) -> List[Dict[str, Any]]:
    data = json.loads(text)
    if data.get("encrypted"):
        raise ValueError("Зашифрованный экспорт Bitwarden не поддерживается")
    out: List[Dict[str, Any]] = []
    for item in data.get("items") or []:
        login = item.get("login") or {}
        uris = login.get("uris") or []
        url = uris[0].get("uri", "") if uris else ""
        out.append(
            {
                "title": item.get("name", "") or "",
                "username": login.get("username", "") or "",
                "password": login.get("password", "") or "",
                "url": url,
                "category": item.get("folder", "") or "",
                "notes": item.get("notes", "") or "",
            }
        )
    return out
