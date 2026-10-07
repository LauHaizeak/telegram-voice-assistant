"""Connexion Google à faire une seule fois : ouvre le navigateur et enregistre data/token.json."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402

from assistant.config import DATA_DIR, ROOT  # noqa: E402
from assistant.google_auth import load_credentials  # noqa: E402

if __name__ == "__main__":
    load_dotenv(ROOT / ".env")
    import os

    credentials = ROOT / os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
    load_credentials(credentials, DATA_DIR / "token.json", interactive=True)
    print("Connexion Google OK, jeton enregistré dans data/token.json")
