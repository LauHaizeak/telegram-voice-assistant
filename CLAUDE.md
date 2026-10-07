# CLAUDE.md

Assistant vocal Telegram personnel de Kevin. Il tourne en local sur son PC (GPU RTX 5090) : vocal Telegram → faster-whisper → règles d'intention FR → Google Calendar / Google Docs.

## Règles

- Répondre et documenter en français.
- Python 3.11+, `python-telegram-bot` v21 (asyncio). Tout appel bloquant (Whisper, API Google) passe par `asyncio.to_thread`.
- Pas de service cloud tiers ni de LLM distant : la compréhension reste dans `assistant/intents.py`.
- Ne jamais committer `.env`, `credentials.json` ni `data/` (jeton OAuth, id du doc de notes).
- Toute nouvelle tournure vocale ajoutée à `intents.py` doit avoir son cas dans `tests/test_intents.py`. Les tests figent « maintenant » au mercredi 7 octobre 2026 10h.

## Commandes

- `pip install -r requirements.txt`
- `pytest` : tests (sans GPU ni réseau)
- `python scripts/google_login.py` : connexion Google, une fois
- `python -m assistant` : lancer le bot
