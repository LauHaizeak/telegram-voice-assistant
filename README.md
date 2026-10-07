# Assistant vocal Telegram

Un bot Telegram personnel : tu lui envoies un vocal depuis ton téléphone, il le transcrit en local avec Whisper (sur ta carte NVIDIA), comprend la demande et agit sur ton Google Agenda ou tes notes Google Docs. Tout tourne sur ton PC, rien n'est hébergé ailleurs.

## Ce qu'il sait faire

| Tu dis | Il fait |
|---|---|
| « Ajoute à l'agenda demain à 14h réunion avec Paul » | Crée l'événement (1 h par défaut) et propose un bouton **Annuler** |
| « Rendez-vous vendredi à trois heures et demie de l'après-midi garage » | Idem, à 15h30 |
| « Ajoute à l'agenda le 1er décembre anniversaire de Léa » | Événement sur toute la journée (pas d'heure dite) |
| « Planifie demain à 10h sport pendant 2 heures » | Événement de 2 h |
| « Note que je dois rappeler le garage » | Ajoute une ligne datée dans le Google Doc « Notes – Assistant vocal » |
| « Lis mon agenda », « Qu'est-ce que j'ai demain ? », « … cette semaine » | Lit l'agenda |

Commandes : `/start` (aide + agenda du jour), `/agenda`, `/demain`, `/semaine`, `/notes` (lien vers le doc).
Les messages texte marchent aussi, pratique pour tester.

## Installation (une seule fois)

### 1. Python et dépendances

Python 3.11 ou plus récent.

```bash
git clone https://github.com/LauHaizeak/telegram-voice-assistant.git
cd telegram-voice-assistant
python -m venv .venv
# Windows : .venv\Scripts\activate    |    Linux/macOS : source .venv/bin/activate
pip install -r requirements.txt
```

**GPU** : faster-whisper a besoin des bibliothèques CUDA 12 et cuDNN 9. Le plus simple :
```bash
pip install nvidia-cublas-cu12 "nvidia-cudnn-cu12==9.*"
```
La RTX 5090 n'a pas été testée ici. Si Whisper plante au démarrage sur le GPU, mets `WHISPER_DEVICE=cpu` et `WHISPER_COMPUTE_TYPE=int8` dans `.env` pour avancer, puis on règle le GPU ensemble.

### 2. Créer le bot Telegram

1. Dans Telegram, ouvre **@BotFather**, envoie `/newbot`, choisis un nom.
2. Copie le jeton qu'il te donne.
3. `cp .env.example .env` puis colle le jeton dans `TELEGRAM_BOT_TOKEN`.

### 3. Autoriser Google (Agenda + Docs)

1. Va sur https://console.cloud.google.com/ et crée un projet (ex. « Assistant vocal »).
2. **APIs et services → Bibliothèque** : active **Google Calendar API** et **Google Docs API**.
3. **Écran de consentement OAuth** : type « Externe », ajoute ton adresse Gmail dans **Utilisateurs test**.
4. **Identifiants → Créer → ID client OAuth → Application de bureau**, télécharge le JSON et enregistre-le sous `credentials.json` à la racine du projet.
5. Lance une fois :
   ```bash
   python scripts/google_login.py
   ```
   Le navigateur s'ouvre, accepte. Le jeton est enregistré dans `data/token.json`.

### 4. Lancer

```bash
python -m assistant
```

Envoie un message à ton bot. Au premier message, il te répond ton identifiant Telegram : mets-le dans `ALLOWED_USER_IDS` du `.env` et relance. Ensuite, seul toi peux l'utiliser.

## Tests

```bash
pytest
```

## Organisation du code

- `assistant/intents.py` : compréhension des phrases (règles en français, sans IA externe)
- `assistant/transcribe.py` : Whisper local
- `assistant/calendar_service.py`, `assistant/notes_service.py` : Google Agenda et Google Docs
- `assistant/bot.py` : le bot Telegram
