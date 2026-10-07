"""Listes Google Tasks (courses, etc.) de la boîte principale."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


@dataclass
class Item:
    id: str
    title: str


def _key(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower().strip())
    return "".join(c for c in text if c.isalnum())


class TasksService:
    def __init__(self, creds: Credentials) -> None:
        self._api = build("tasks", "v1", credentials=creds, cache_discovery=False)
        self._list_ids: dict[str, str] = {}

    def _list_id(self, name: str) -> str:
        key = _key(name)
        if key not in self._list_ids:
            for tl in self._api.tasklists().list(maxResults=100).execute().get("items", []):
                self._list_ids[_key(tl["title"])] = tl["id"]
        if key not in self._list_ids:
            created = self._api.tasklists().insert(body={"title": name.strip().capitalize()}).execute()
            self._list_ids[key] = created["id"]
        return self._list_ids[key]

    def items(self, name: str) -> list[Item]:
        found = self._api.tasks().list(tasklist=self._list_id(name), showCompleted=False, maxResults=100).execute()
        return [Item(t["id"], t["title"]) for t in found.get("items", []) if t.get("title")]

    def add(self, name: str, titles: list[str]) -> tuple[list[str], list[str]]:
        """Ajoute les articles absents ; renvoie (ajoutés, déjà présents)."""
        existing = {_key(i.title) for i in self.items(name)}
        added, skipped = [], []
        for title in titles:
            title = title.strip()
            if not title:
                continue
            if _key(title) in existing:
                skipped.append(title)
                continue
            self._api.tasks().insert(tasklist=self._list_id(name), body={"title": title[:1].upper() + title[1:]}).execute()
            existing.add(_key(title))
            added.append(title)
        return added, skipped

    def complete(self, name: str, item_id: str) -> None:
        self._api.tasks().patch(tasklist=self._list_id(name), task=item_id, body={"status": "completed"}).execute()

    def delete(self, name: str, item_id: str) -> None:
        self._api.tasks().delete(tasklist=self._list_id(name), task=item_id).execute()

    def match(self, name: str, titles: list[str]) -> tuple[list[Item], list[str]]:
        """Retrouve les articles de la liste correspondant aux noms donnés ; renvoie (trouvés, introuvables)."""
        items = self.items(name)
        found, missing = [], []
        for title in titles:
            key = _key(title)
            hit = next((i for i in items if _key(i.title) == key), None) or \
                next((i for i in items if key and (key in _key(i.title) or _key(i.title) in key)), None)
            (found.append(hit) if hit else missing.append(title))
        return found, missing
