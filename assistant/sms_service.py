"""Envoi de SMS depuis le téléphone de Kevin via l'app SMS Gateway for Android (serveur local, même Wi-Fi)."""

from __future__ import annotations

import time

import requests


class SmsService:
    def __init__(self, url: str, user: str, password: str) -> None:
        self._url = url.rstrip("/")
        self._auth = (user, password)

    @property
    def configured(self) -> bool:
        return bool(self._url and self._auth[1])

    def send(self, phone: str, text: str) -> str:
        """Envoie le SMS et renvoie son état final connu (Sent, Delivered, Failed…)."""
        r = requests.post(f"{self._url}/message", auth=self._auth, timeout=15, json={
            "textMessage": {"text": text}, "phoneNumbers": [phone], "withDeliveryReport": True,
        })
        r.raise_for_status()
        message = r.json()
        for _ in range(10):
            state = message.get("state", "Pending")
            if state in ("Sent", "Delivered", "Failed"):
                return state
            time.sleep(1)
            status = requests.get(f"{self._url}/message/{message['id']}", auth=self._auth, timeout=10)
            if status.ok:
                message = status.json()
        return message.get("state", "Pending")
