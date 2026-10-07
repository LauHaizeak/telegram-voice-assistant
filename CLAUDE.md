# CLAUDE.md

Assistant vocal Telegram personnel de Kevin. Tout tourne en local sur son PC (RTX 5090) : vocal Telegram → faster-whisper → IA locale via Ollama (appel d'outils) → Gmail (plusieurs boîtes), Google Agenda, Google Docs.

## Règles

- Répondre et documenter en français.
- Python 3.11+, `python-telegram-bot` v21+ (asyncio). Tout appel bloquant (Whisper, Ollama, API Google) passe par `asyncio.to_thread`.
- Aucun service d'IA distant : l'IA est le modèle Ollama de `OLLAMA_MODEL` (par défaut `qwen3.8:27b`, déjà installé ; ne pas en télécharger d'autres sans demander à Kevin).
- C'est l'IA qui comprend les demandes et choisit les outils (`assistant/agent.py`). Pas de règles codées au cas par cas : on ajoute un outil ou on précise sa description. `assistant/intents.py` ne sert qu'en secours quand Ollama ne répond pas.
- Whisper et le modèle Ollama se déchargent de la carte graphique après 5 min sans utilisation.
- Aucun mail ne part sans que Kevin appuie sur le bouton « Envoyer ».
- Ne jamais committer `.env`, `credentials*.json` ni `data/` (jetons OAuth, journaux, vocaux de test).
- Toute nouvelle tournure ajoutée à `intents.py` doit avoir son cas dans `tests/test_intents.py`. Les tests figent « maintenant » au mercredi 7 octobre 2026 10h.

## Commandes

- `pip install -r requirements.txt`
- `pytest` : tests (sans GPU, sans réseau)
- `python scripts/google_login.py` : connecte chaque boîte de `GMAIL_ADDRESSES` (une fois)
- `python scripts/test_agent.py "phrase"` : essaie l'IA sur une phrase (écritures simulées)
- `Demarrer-assistant.ps1` / `Arreter-assistant.ps1` : bot en arrière-plan, relancé s'il plante ; journal dans `data/bot.log`
