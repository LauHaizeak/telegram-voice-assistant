from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

DOC_TITLE = "Notes – Assistant vocal"


class NotesService:
    """Ajoute les notes à la suite d'un unique Google Doc."""

    def __init__(self, creds: Credentials, doc_id: str, state_file: Path) -> None:
        self._api = build("docs", "v1", credentials=creds, cache_discovery=False)
        self._state_file = state_file
        self._doc_id = doc_id or self._load_state().get("notes_doc_id", "")

    @property
    def doc_url(self) -> str:
        return f"https://docs.google.com/document/d/{self._ensure_doc()}/edit"

    def add_note(self, text: str, when: datetime) -> None:
        doc_id = self._ensure_doc()
        doc = self._api.documents().get(documentId=doc_id, fields="body/content/endIndex").execute()
        end_index = doc["body"]["content"][-1]["endIndex"] - 1
        entry = f"{when:%d/%m/%Y %H:%M} — {text}\n"
        self._api.documents().batchUpdate(
            documentId=doc_id,
            body={"requests": [{"insertText": {"location": {"index": end_index}, "text": entry}}]},
        ).execute()

    def _ensure_doc(self) -> str:
        if not self._doc_id:
            created = self._api.documents().create(body={"title": DOC_TITLE}).execute()
            self._doc_id = created["documentId"]
            state = self._load_state()
            state["notes_doc_id"] = self._doc_id
            self._state_file.parent.mkdir(parents=True, exist_ok=True)
            self._state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
        return self._doc_id

    def _load_state(self) -> dict:
        if self._state_file.exists():
            return json.loads(self._state_file.read_text(encoding="utf-8"))
        return {}
