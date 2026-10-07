"""Assistant d'installation : configure .env, Google et l'identifiant Telegram, sans éditer de fichier."""

from __future__ import annotations

import json
import shutil
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ENV_FILE = ROOT / ".env"
CREDENTIALS = ROOT / "credentials.json"
TOKEN = ROOT / "data" / "token.json"

GOOGLE_STEPS = [
    ("Créer un projet Google Cloud (nom libre, ex. « Assistant vocal »)",
     "https://console.cloud.google.com/projectcreate"),
    ("Activer l'API Google Calendar (bouton « Activer »)",
     "https://console.cloud.google.com/apis/library/calendar-json.googleapis.com"),
    ("Activer l'API Google Docs (bouton « Activer »)",
     "https://console.cloud.google.com/apis/library/docs.googleapis.com"),
    ("Écran de consentement : type « Externe », puis ajoute ton adresse Gmail dans « Utilisateurs test »",
     "https://console.cloud.google.com/apis/credentials/consent"),
    ("Créer un ID client OAuth de type « Application de bureau », puis cliquer « Télécharger JSON »",
     "https://console.cloud.google.com/apis/credentials/oauthclient"),
]


def read_env() -> dict[str, str]:
    if not ENV_FILE.exists():
        shutil.copy(ROOT / ".env.example", ENV_FILE)
    values = {}
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def write_env(key: str, value: str) -> None:
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        if line.split("=", 1)[0].strip() == key:
            lines[i] = f"{key}={value}"
            break
    else:
        lines.append(f"{key}={value}")
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def telegram(token: str, method: str, params: str = "") -> dict:
    url = f"https://api.telegram.org/bot{token}/{method}{params}"
    with urllib.request.urlopen(url, timeout=40) as response:
        return json.load(response)


def step_telegram_token(env: dict[str, str]) -> str:
    token = env.get("TELEGRAM_BOT_TOKEN", "")
    while True:
        if token:
            try:
                me = telegram(token, "getMe")["result"]
                print(f"✓ Bot Telegram : @{me['username']}")
                write_env("TELEGRAM_BOT_TOKEN", token)
                return token
            except (urllib.error.URLError, KeyError):
                print("✗ Ce jeton ne fonctionne pas.")
        print("\n— Bot Telegram —")
        print("Sur ton téléphone, ouvre @BotFather dans Telegram, envoie /newbot et choisis un nom.")
        webbrowser.open("https://t.me/BotFather")
        token = input("Colle ici le jeton qu'il te donne : ").strip()


def step_telegram_user(token: str, env: dict[str, str]) -> None:
    if env.get("ALLOWED_USER_IDS"):
        print("✓ Identifiant Telegram déjà configuré")
        return
    me = telegram(token, "getMe")["result"]
    print(f"\nEnvoie maintenant n'importe quel message à @{me['username']} dans Telegram…")
    webbrowser.open(f"https://t.me/{me['username']}")
    offset = 0
    while True:
        updates = telegram(token, "getUpdates", f"?timeout=30&offset={offset}")["result"]
        for update in updates:
            offset = update["update_id"] + 1
            sender = (update.get("message") or {}).get("from")
            if sender:
                write_env("ALLOWED_USER_IDS", str(sender["id"]))
                telegram(token, "getUpdates", f"?offset={offset}&timeout=0")
                print(f"✓ C'est toi : {sender.get('first_name', '')} (id {sender['id']}). Seul toi pourras utiliser le bot.")
                return


def find_downloaded_client_secret() -> Path | None:
    downloads = Path.home() / "Downloads"
    if not downloads.exists():
        downloads = Path.home() / "Téléchargements"
    candidates = sorted(downloads.glob("client_secret*.json"), key=lambda p: p.stat().st_mtime)
    return candidates[-1] if candidates else None


def step_google_credentials() -> None:
    if CREDENTIALS.exists():
        print("✓ Fichier Google credentials.json présent")
        return
    already = find_downloaded_client_secret()
    if already:
        shutil.copy(already, CREDENTIALS)
        print(f"✓ Fichier Google trouvé dans tes téléchargements : {already.name}")
        return
    print("\n— Google (une seule fois) —")
    print("Je vais ouvrir les pages une par une. Fais l'action, puis appuie sur Entrée.\n")
    for i, (label, url) in enumerate(GOOGLE_STEPS, 1):
        if CREDENTIALS.exists():
            break
        print(f"{i}/{len(GOOGLE_STEPS)} {label}")
        webbrowser.open(url)
        input("   Entrée quand c'est fait… ")
    print("J'attends le fichier JSON téléchargé (client_secret_….json)…")
    while not CREDENTIALS.exists():
        found = find_downloaded_client_secret()
        if found:
            shutil.copy(found, CREDENTIALS)
            print(f"✓ Récupéré : {found.name}")
            break
        time.sleep(2)


def step_google_login() -> None:
    from assistant.google_auth import load_credentials

    if TOKEN.exists():
        print("✓ Connexion Google déjà faite")
        return
    print("\nUne page Google va s'ouvrir : choisis ton compte et clique « Autoriser ».")
    print("(Si Google affiche « application non validée » : Paramètres avancés → Accéder.)")
    load_credentials(CREDENTIALS, TOKEN, interactive=True)
    print("✓ Google connecté")


def main() -> None:
    print("=== Installation de l'assistant vocal ===")
    env = read_env()
    token = step_telegram_token(env)
    step_telegram_user(token, env)
    step_google_credentials()
    step_google_login()
    print("\n✓ Tout est prêt. Le bot va démarrer.\n")


if __name__ == "__main__":
    main()
