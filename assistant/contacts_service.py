from __future__ import annotations

import time
from dataclasses import dataclass

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

FIELDS = "names,emailAddresses,phoneNumbers"


def _retry(call):
    try:
        return call()
    except HttpError as e:
        if e.resp.status != 400:
            raise
        time.sleep(3)
        return call()


@dataclass
class Contact:
    name: str
    emails: list[str]
    phones: list[str]


class ContactsService:
    """Google Contacts (lecture seule) de toutes les boîtes, y compris les « autres contacts » Gmail."""

    def __init__(self, creds_by_address: dict[str, Credentials]) -> None:
        self._apis = {address: build("people", "v1", credentials=creds, cache_discovery=False)
                      for address, creds in creds_by_address.items()}
        self._warmed: set[str] = set()

    def search(self, query: str, limit: int = 8) -> list[Contact]:
        found: dict[tuple, Contact] = {}
        for address, api in self._apis.items():
            if address not in self._warmed:
                # L'API People demande une recherche vide pour préparer son cache, puis quelques secondes
                api.people().searchContacts(query="", readMask=FIELDS).execute()
                api.otherContacts().search(query="", readMask=FIELDS).execute()
                self._warmed.add(address)
                time.sleep(2)
            results = _retry(lambda: api.people().searchContacts(query=query, readMask=FIELDS, pageSize=limit).execute())
            others = _retry(lambda: api.otherContacts().search(query=query, readMask=FIELDS, pageSize=limit).execute())
            for r in results.get("results", []) + others.get("results", []):
                person = r["person"]
                contact = Contact(
                    name=(person.get("names") or [{}])[0].get("displayName", ""),
                    emails=[e["value"] for e in person.get("emailAddresses", [])],
                    phones=[p.get("canonicalForm") or p["value"] for p in person.get("phoneNumbers", [])],
                )
                key = (contact.name.lower(), tuple(contact.emails), tuple(contact.phones))
                found.setdefault(key, contact)
        return list(found.values())[:limit]
