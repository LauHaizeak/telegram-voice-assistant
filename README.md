# Assistant vocal Telegram

Un assistant personnel sur Telegram. Tu lui parles normalement, en vocal ou en texte, et il s'occupe de tes mails Gmail (plusieurs boîtes), de ton Google Agenda et de tes notes Google Docs.

Tout tourne sur ton PC : Whisper transcrit la voix et une IA locale (Ollama) comprend la demande. Rien ne passe par un service d'IA en ligne.

## Ce qu'il sait faire

- **Mails** : « Résume-moi le dernier mail de ma boîte pro », « Quelqu'un m'a écrit pour une facture ? », « Fais-moi un point sur mes non lus ».
- **Envoyer un mail** : « Envoie un mail à Paul pour lui dire que je serai en retard ». Il retrouve l'adresse dans tes mails et rédige le texte. Le mail ne part que si tu appuies sur **Envoyer**.
- **Agenda** : « Qu'est-ce que j'ai jeudi ? », « Mets-moi un rdv chez le coiffeur jeudi prochain vers 11h ». Chaque ajout a un bouton **Annuler**.
- **Notes** : « Note qu'il faut racheter des piles ».
- **Commandes** : `/agenda`, `/demain`, `/semaine`, `/notes`, `/mails`.

Compte 5 à 15 secondes par réponse. Après 5 minutes sans demande, l'IA et Whisper libèrent la carte graphique, et la réponse suivante prend un peu plus longtemps.

## Installation (Windows)

1. Télécharge le projet et dézippe-le.
2. Double-clique sur **`Lancer-assistant.bat`**. Il installe Python, Ollama et les dépendances, puis te guide pour :
   - créer le bot Telegram avec @BotFather ;
   - activer les API Google (Agenda, Docs, Gmail) et ajouter tes adresses en « utilisateurs test » ;
   - donner tes adresses Gmail (la première sert aussi pour l'agenda et les notes) ;
   - autoriser chaque boîte, une page Google par adresse.
3. Télécharge le modèle d'IA une fois : `ollama pull qwen3.8:27b` (ou mets le nom d'un modèle déjà installé dans `OLLAMA_MODEL` du `.env`).

Le bot démarre ensuite en arrière-plan.

## Démarrer et arrêter

- **`Demarrer-assistant.ps1`** : lance le bot en arrière-plan, sans fenêtre. S'il plante, il redémarre tout seul. Si le bot tourne déjà, il ne lance pas de doublon.
- **`Arreter-assistant.ps1`** : l'arrête.

Fais un raccourci de chacun sur le Bureau, avec la cible `powershell -ExecutionPolicy Bypass -File "<chemin>\Demarrer-assistant.ps1"`.

En cas de souci, regarde `data\bot.log`.

## Ajouter une boîte mail

Ajoute l'adresse dans `GMAIL_ADDRESSES` du `.env` et dans les « utilisateurs test » Google. Lance ensuite `python scripts\google_login.py` et relance le bot.

## Pour les développeurs

- `assistant/agent.py` : l'IA et ses outils (chercher_mails, lire_agenda, ajouter_evenement, ajouter_note, envoyer_mail).
- `assistant/bot.py` : le bot Telegram (vocaux, boutons Envoyer et Annuler).
- `assistant/transcribe.py` : Whisper, déchargé après 5 minutes sans vocal.
- `assistant/mail_service.py`, `calendar_service.py`, `notes_service.py` : Gmail, Agenda et Docs.
- `assistant/intents.py` : règles de secours, utilisées seulement si Ollama ne répond pas.
- `pytest` lance les tests. `python scripts\test_agent.py "ta phrase"` essaie l'IA sans rien écrire dans l'agenda ni les notes.
