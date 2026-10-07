import logging

from .bot import Assistant, state_file
from .calendar_service import CalendarService
from .config import load_config
from .google_auth import load_credentials
from .notes_service import NotesService
from .transcribe import Transcriber


def main() -> None:
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)

    config = load_config()
    creds = load_credentials(config.google_credentials_file, config.google_token_file)
    assistant = Assistant(
        config,
        Transcriber(config.whisper_model, config.whisper_device, config.whisper_compute_type),
        CalendarService(creds, config.calendar_id, config.timezone),
        NotesService(creds, config.notes_doc_id, state_file()),
    )
    logging.info("Bot démarré. Ctrl+C pour arrêter.")
    assistant.build_app().run_polling()


if __name__ == "__main__":
    main()
