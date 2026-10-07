from __future__ import annotations

import json
from pathlib import Path

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
]


def token_path(data_dir: Path, email: str) -> Path:
    return data_dir / f"token_{email}.json"


def load_credentials(credentials_file: Path, data_dir: Path, email: str, interactive: bool = False) -> Credentials:
    """Jeton OAuth de la boîte `email`, rafraîchi si besoin ; `interactive` ouvre la page Google."""
    token_file = token_path(data_dir, email)
    granted = set(json.loads(token_file.read_text(encoding="utf-8")).get("scopes", [])) if token_file.exists() else set()
    if granted >= set(SCOPES):
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)
        if creds.valid:
            return creds
        if creds.refresh_token:
            try:
                creds.refresh(Request())
                return creds
            except RefreshError:
                pass

    if not interactive:
        raise SystemExit(f"Connexion Google absente ou à renouveler pour {email}. Lance : python scripts/google_login.py")
    if not credentials_file.exists():
        raise SystemExit(f"Fichier OAuth introuvable : {credentials_file} (voir README).")
    flow = InstalledAppFlow.from_client_secrets_file(str(credentials_file), SCOPES)
    creds = flow.run_local_server(port=0, login_hint=email)
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(creds.to_json(), encoding="utf-8")
    return creds
