from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from datetime import datetime
from email.mime.text import MIMEText

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


@dataclass
class Email:
    id: str
    sender: str
    subject: str
    snippet: str
    timestamp: datetime
    is_read: bool


class MailService:
    """Plusieurs boîtes Gmail, chacune avec son propre jeton OAuth."""

    def __init__(self, creds_by_address: dict[str, Credentials], addresses: tuple[str, ...]) -> None:
        self._addresses = addresses
        self._apis = {address: build("gmail", "v1", credentials=creds, cache_discovery=False)
                      for address, creds in creds_by_address.items()}

    def _messages(self, address: str):
        if address not in self._apis:
            raise ValueError(f"Pas de connexion Google pour {address} : lancer scripts/google_login.py")
        return self._apis[address].users().messages()

    def list_emails(self, address: str, max_results: int = 5, query: str = "is:unread") -> list[Email]:
        found = self._messages(address).list(userId="me", q=query, maxResults=max_results).execute()
        return [self._details(address, m["id"]) for m in found.get("messages", [])]

    def get_unread_count(self, address: str) -> int:
        if address not in self._apis:
            return 0
        found = self._messages(address).list(userId="me", q="is:unread", maxResults=1).execute()
        return found.get("resultSizeEstimate", 0)

    def get_body(self, address: str, message_id: str, limit: int = 4000) -> str:
        msg = self._messages(address).get(userId="me", id=message_id, format="full").execute()
        parts, plain, html = [msg.get("payload", {})], [], []
        while parts:
            part = parts.pop()
            parts.extend(part.get("parts", []))
            data = part.get("body", {}).get("data")
            if data:
                text = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
                (plain if part.get("mimeType") == "text/plain" else html).append(text)
        body = "\n".join(plain) or re.sub(r"<[^>]+>", " ", "\n".join(html))
        return re.sub(r"\s+", " ", body).strip()[:limit] or msg.get("snippet", "")

    def send_email(self, address: str, to: str, subject: str, body: str) -> str:
        message = MIMEText(body)
        message["to"] = to
        message["subject"] = subject
        message["from"] = address
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
        return self._messages(address).send(userId="me", body={"raw": raw}).execute()["id"]

    def _details(self, address: str, message_id: str) -> Email:
        msg = self._messages(address).get(
            userId="me", id=message_id, format="metadata", metadataHeaders=["from", "subject"]
        ).execute()
        headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}
        return Email(
            id=message_id,
            sender=headers.get("from", "Inconnu"),
            subject=headers.get("subject", "(sans objet)"),
            snippet=msg.get("snippet", ""),
            timestamp=datetime.fromtimestamp(int(msg.get("internalDate", 0)) / 1000),
            is_read="UNREAD" not in msg.get("labelIds", []),
        )
