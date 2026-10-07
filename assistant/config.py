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
    gmail_addresses: tuple[str, ...]
    ollama_model: str
    sms_gateway_url: str
    sms_gateway_user: str
    sms_gateway_password: str
    voice_name: str
    voice_replies: str


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
    gmail_addrs = tuple(dict.fromkeys(
        part for part in os.getenv("GMAIL_ADDRESSES", "").replace(" ", "").split(",") if part
    ))
    if not gmail_addrs:
        raise SystemExit("GMAIL_ADDRESSES manquant dans .env : la première adresse sert aussi à l'agenda et aux notes.")
    # texte : toujours par écrit, la voix ne se charge jamais ; auto : vocal si on lui parle en vocal ; vocal : toujours
    voice_replies = os.getenv("VOICE_REPLIES", "texte").strip().lower()
    if voice_replies not in ("auto", "vocal"):
        voice_replies = "texte"
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
        gmail_addresses=gmail_addrs,
        ollama_model=os.getenv("OLLAMA_MODEL", "qwen3.8:27b"),
        sms_gateway_url=os.getenv("SMS_GATEWAY_URL", "").strip(),
        sms_gateway_user=os.getenv("SMS_GATEWAY_USER", "sms").strip(),
        sms_gateway_password=os.getenv("SMS_GATEWAY_PASSWORD", "").strip(),
        voice_name=os.getenv("VOICE_NAME", "fr_FR-siwis-medium").strip(),
        voice_replies=voice_replies,
    )
