from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"


@dataclass(frozen=True)
class Config:
    telegram_token: str
    allowed_user_ids: frozenset[int]
    timezone: ZoneInfo
    whisper_model: str
    whisper_device: str
    whisper_compute_type: str
    calendar_id: str
    notes_doc_id: str
    google_credentials_file: Path
    google_token_file: Path


def load_config() -> Config:
    load_dotenv(ROOT / ".env")
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit("TELEGRAM_BOT_TOKEN manquant dans .env (voir .env.example).")
    ids = {
        int(part)
        for part in os.getenv("ALLOWED_USER_IDS", "").replace(" ", "").split(",")
        if part
    }
    return Config(
        telegram_token=token,
        allowed_user_ids=frozenset(ids),
        timezone=ZoneInfo(os.getenv("TIMEZONE", "Europe/Paris")),
        whisper_model=os.getenv("WHISPER_MODEL", "large-v3"),
        whisper_device=os.getenv("WHISPER_DEVICE", "cuda"),
        whisper_compute_type=os.getenv("WHISPER_COMPUTE_TYPE", "float16"),
        calendar_id=os.getenv("GOOGLE_CALENDAR_ID", "primary"),
        notes_doc_id=os.getenv("GOOGLE_NOTES_DOC_ID", "").strip(),
        google_credentials_file=ROOT / os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json"),
        google_token_file=DATA_DIR / "token.json",
    )
