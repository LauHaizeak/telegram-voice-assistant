# Assistant vocal Telegram

Un assistant personnel sur Telegram. Tu lui parles normalement, en vocal ou en texte, et il s'occupe de tes mails Gmail (plusieurs boîtes), de ton agenda, de tes notes, de tes contacts et de tes SMS. Il te répond en vocal ou par écrit.

Tout tourne sur ton PC : Whisper transcrit ta voix, une IA locale (Ollama) comprend la demande et Piper lit la réponse. Rien ne passe par un service d'IA en ligne.

## Ce qu'il sait faire

- **Mails** : « Résume-moi le dernier mail de ma boîte pro », « Quelqu'un m'a écrit pour une facture ? », « Fais-moi un point sur mes non lus ».
- **Envoyer un mail** : « Envoie un mail à Paul pour lui dire que je serai en retard ». Il trouve l'adresse dans tes contacts ou tes mails et rédige le texte. Le mail ne part que si tu appuies sur **Envoyer**.
- **Ranger ses mails** : « Supprime-le », « Archive les deux premiers », « Marque-le comme lu ». Il se souvient de ce dont vous venez de parler pendant 30 minutes. La suppression met le mail à la corbeille Gmail, où il reste récupérable 30 jours, et demande d'abord ton accord.
- **Contacts** : il trouve les gens dans tes contacts Google. Si plusieurs personnes correspondent, il te demande laquelle.
- **SMS** : « Envoie un SMS à Paul pour lui dire que j'arrive ». Le SMS part de ton téléphone Android, après le bouton **Envoyer le SMS**.
- **Agenda** : « Qu'est-ce que j'ai jeudi ? », « Mets-moi un rdv chez le coiffeur jeudi prochain vers 11h ». Chaque ajout a un bouton **Annuler**.
- **Notes** : « Note qu'il faut racheter des piles ».
- **Réponse vocale** : il répond en vocal à tes vocaux et par écrit à tes messages écrits. Les boutons de confirmation restent en texte sous le vocal. `/vocal` force le vocal, `/texte` force l'écrit, `/auto` revient au réglage normal.
- **Commandes** : `/agenda`, `/demain`, `/semaine`, `/notes`, `/mails`, `/vocal`, `/texte`, `/auto`.

Compte 5 à 20 secondes par réponse. Après 5 minutes sans demande, l'IA, Whisper et la voix se déchargent, et la réponse suivante prend un peu plus longtemps.

## Installation (Windows)

1. Télécharge le projet et dézippe-le.
2. Double-clique sur **`Lancer-assistant.bat`**. Il installe Python, Ollama et les dépendances, puis te guide pour :
   - créer le bot Telegram avec @BotFather ;
   - activer les API Google (Agenda, Docs, Gmail, People) et ajouter tes adresses en « utilisateurs test » ;
   - donner tes adresses Gmail (la première sert aussi pour l'agenda et les notes) ;
   - autoriser chaque boîte, une page Google par adresse.
3. Télécharge le modèle d'IA une fois : `ollama pull qwen3.8:27b`. Tu peux aussi mettre le nom d'un modèle déjà installé dans `OLLAMA_MODEL` du `.env`.
4. Pour les SMS (facultatif) : installe **SMS Gateway for Android** sur ton téléphone, depuis https://github.com/capcom6/android-sms-gateway/releases. N'autorise que l'envoi de SMS. Active « Local server » et laisse « Cloud server » coupé. Recopie ensuite l'adresse, l'identifiant et le mot de passe affichés dans `SMS_GATEWAY_URL`, `SMS_GATEWAY_USER` et `SMS_GATEWAY_PASSWORD` du `.env`. Le téléphone doit être sur le même Wi-Fi que le PC.

La voix française (`VOICE_NAME`, par défaut `fr_FR-siwis-medium`, féminine) se télécharge toute seule. Pour une voix masculine, mets `fr_FR-tom-medium`.

## Démarrer et arrêter

- **`Demarrer-assistant.ps1`** : lance le bot en arrière-plan, sans fenêtre. S'il plante, il redémarre tout seul, et il ne lance jamais de doublon.
- **`Arreter-assistant.ps1`** : l'arrête.

Fais un raccourci de chacun sur le Bureau, avec la cible `powershell -ExecutionPolicy Bypass -File "<chemin>\Demarrer-assistant.ps1"`. En cas de souci, regarde `data\bot.log`.

## Ajouter une boîte mail

Ajoute l'adresse dans `GMAIL_ADDRESSES` du `.env` et dans les « utilisateurs test » Google. Lance ensuite `python scripts\google_login.py` et relance le bot.

## Carte graphique

Le pic mesuré est de 27,3 Go sur 32 Go (RTX 5090), avec Windows, Whisper et l'IA chargés en même temps. La voix tourne sur le processeur et n'ajoute rien. Si la carte graphique est presque pleine au moment de charger Whisper, le bot décharge d'abord l'IA au lieu de planter.

## Avancement

Fait :
- Vocaux transcrits en local (Whisper large-v3 sur la carte graphique).
- IA locale (Qwen 3.8 via Ollama) qui comprend les demandes libres et choisit elle-même les outils. Les règles fixes ne servent qu'en secours si Ollama ne répond pas.
- Gmail sur plusieurs boîtes : lire, résumer, chercher, envoyer, corbeille, archiver, marquer lu.
- Google Agenda, notes Google Docs, Google Contacts.
- SMS depuis le téléphone Android, en local.
- Réponses vocales en français (Piper).
- Mémoire de conversation pendant 30 minutes.
- Confirmation par bouton avant tout envoi ou suppression.
- Démarrage en arrière-plan avec relance automatique ; modèles déchargés après 5 minutes.

## À faire

- **SMS hors de la maison** : aujourd'hui le téléphone doit être sur le même Wi-Fi que le PC. À étudier : un VPN privé entre les deux appareils, comme Tailscale, plutôt que le mode cloud de l'application.
- **Démarrage avec Windows** : lancer le bot automatiquement à l'ouverture de session.
- **Lecture des SMS reçus** : volontairement désactivée pour l'instant.
- **Plusieurs utilisateurs** (réflexion, pas prioritaire) : pour qu'un proche ait le même assistant avec ses propres comptes, chaque personne aurait son profil. Un profil, c'est son bot Telegram, son identifiant Telegram, son `.env`, ses jetons Google et son téléphone pour les SMS, dans un dossier séparé. Les profils tourneraient sur le même PC et partageraient les modèles (un seul Whisper, une seule IA, une seule voix) pour ne pas doubler la mémoire de la carte graphique. Ses adresses Gmail devraient aussi être ajoutées comme « utilisateurs test » du projet Google.

## Pour les développeurs

- `assistant/agent.py` : l'IA et ses outils (mails, agenda, notes, contacts, SMS).
- `assistant/bot.py` : le bot Telegram (vocaux, réponses vocales, boutons de confirmation).
- `assistant/transcribe.py` : Whisper ; `assistant/voice.py` : la voix Piper.
- `assistant/mail_service.py`, `calendar_service.py`, `notes_service.py`, `contacts_service.py`, `sms_service.py` : les services.
- `assistant/intents.py` : règles de secours.
- `pytest` lance les tests. `python scripts\test_agent.py "ta phrase"` essaie l'IA sans rien écrire dans l'agenda ni les notes.
