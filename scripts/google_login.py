"""Connexion Google, une fois par boîte : python scripts/google_login.py [adresse ...]

Sans argument, connecte chaque adresse de GMAIL_ADDRESSES qui n'a pas encore de jeton valide.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from googleapiclient.discovery import build  # noqa: E402

from assistant.config import DATA_DIR, load_config  # noqa: E402
from assistant.google_auth import load_credentials, token_path  # noqa: E402


def login(emails: list[str] | None = None) -> None:
    config = load_config()
    for email in emails or config.gmail_addresses:
        if not emails:
            try:
                load_credentials(config.google_credentials_file, DATA_DIR, email)
                print(f"✓ {email} déjà connecté")
                continue
            except SystemExit:
                pass
        print(f"\nUne page Google va s'ouvrir : choisis le compte {email} et clique « Autoriser ».")
        print("(Si Google affiche « application non validée » : Paramètres avancés → Accéder.)")
        token = token_path(DATA_DIR, email)
        token.unlink(missing_ok=True)
        creds = load_credentials(config.google_credentials_file, DATA_DIR, email, interactive=True)
        actual = build("gmail", "v1", credentials=creds, cache_discovery=False) \
            .users().getProfile(userId="me").execute()["emailAddress"]
        if actual.lower() != email.lower():
            token.unlink(missing_ok=True)
            raise SystemExit(f"✗ Tu as choisi {actual} au lieu de {email}. Relance et choisis le bon compte.")
        print(f"✓ {email} connecté")


if __name__ == "__main__":
    login(sys.argv[1:] or None)
