import logging

from .agent import Agent
from .bot import Assistant, state_file
from .calendar_service import CalendarService
from .config import DATA_DIR, load_config
from .google_auth import load_credentials
from .mail_service import MailService
from .notes_service import NotesService
from .transcribe import Transcriber


def build_services():
    config = load_config()
    creds = {}
    for email in config.gmail_addresses:
        try:
            creds[email] = load_credentials(config.google_credentials_file, DATA_DIR, email)
        except SystemExit as e:
            logging.warning("%s", e)
    primary = config.gmail_addresses[0]
    if primary not in creds:
        raise SystemExit(f"Pas de connexion Google pour {primary}. Lance : python scripts/google_login.py")

    # L'agenda et les notes utilisent la première adresse de GMAIL_ADDRESSES
    calendar = CalendarService(creds[primary], config.calendar_id, config.timezone)
    notes = NotesService(creds[primary], config.notes_doc_id, state_file())
    mail = MailService(creds, config.gmail_addresses)
    agent = Agent(calendar, notes, mail, list(config.gmail_addresses), config.timezone, config.ollama_model)
    return config, calendar, notes, mail, agent


def main() -> None:
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)

    config, calendar, notes, mail, agent = build_services()
    transcriber = Transcriber(config.whisper_model, config.whisper_device, config.whisper_compute_type)
    assistant = Assistant(config, transcriber, calendar, notes, mail, agent)
    logging.info("Bot démarré (IA : %s). Ctrl+C pour arrêter.", config.ollama_model)
    assistant.build_app().run_polling()


if __name__ == "__main__":
    main()
