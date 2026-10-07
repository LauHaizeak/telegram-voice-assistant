"""Assistant piloté par le LLM local (Ollama) : il choisit les outils, remplit leurs paramètres et rédige la réponse."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

import requests

from .calendar_service import CalendarService
from .contacts_service import ContactsService
from .mail_service import MailService
from .notes_service import NotesService
from .sms_service import SmsService

log = logging.getLogger(__name__)

OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"
JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MAX_STEPS = 6


def _tool(name: str, description: str, properties: dict, required: list[str] | None = None) -> dict:
    return {"type": "function", "function": {
        "name": name, "description": description,
        "parameters": {"type": "object", "properties": properties, "required": required or []},
    }}


TOOLS = [
    _tool("chercher_mails",
          "Cherche des mails dans les boîtes Gmail de Kevin et renvoie, pour chacun, une référence (M1, M2…), "
          "l'expéditeur, l'objet, la date et le contenu. Utilise-le pour lire, résumer ou retrouver des mails.",
          {"boite": {"type": "string", "description": "Adresse de la boîte, ou vide pour toutes les boîtes"},
           "recherche": {"type": "string", "description": "Requête de recherche Gmail, par exemple 'is:unread', "
                         "'from:paul', 'newer_than:2d', 'subject:facture'. Vide = tous les mails récents."},
           "nombre": {"type": "integer", "description": "Nombre de mails à récupérer par boîte (1 à 10)"}}),
    _tool("lire_agenda", "Liste les événements de l'agenda Google de Kevin sur une période.",
          {"date_debut": {"type": "string", "description": "AAAA-MM-JJ"},
           "nombre_jours": {"type": "integer", "description": "Nombre de jours à couvrir, 1 par défaut"}},
          ["date_debut"]),
    _tool("ajouter_evenement", "Ajoute un événement ou un rappel dans l'agenda de Kevin.",
          {"titre": {"type": "string"}, "date": {"type": "string", "description": "AAAA-MM-JJ"},
           "heure": {"type": "string", "description": "HH:MM, ou vide pour toute la journée"},
           "duree_minutes": {"type": "integer", "description": "60 par défaut"}},
          ["titre", "date"]),
    _tool("ajouter_note", "Ajoute une note dans le document de notes de Kevin.",
          {"contenu": {"type": "string"}}, ["contenu"]),
    _tool("envoyer_mail",
          "Prépare un mail à envoyer. Le mail n'est PAS envoyé : Kevin devra confirmer avec un bouton.",
          {"boite": {"type": "string", "description": "Adresse d'envoi, vide = boîte principale"},
           "destinataire": {"type": "string", "description": "Adresse mail du destinataire"},
           "objet": {"type": "string"}, "corps": {"type": "string"}},
          ["destinataire", "objet", "corps"]),
    _tool("chercher_contact",
          "Cherche une personne dans les contacts Google de Kevin (toutes ses boîtes) et renvoie son nom, "
          "ses adresses mail et ses numéros de téléphone.",
          {"nom": {"type": "string", "description": "Prénom, nom ou surnom tel que Kevin l'a dit"}}, ["nom"]),
    _tool("envoyer_sms",
          "Prépare un SMS envoyé depuis le téléphone de Kevin. Le SMS n'est PAS envoyé : Kevin devra "
          "confirmer avec un bouton.",
          {"numero": {"type": "string", "description": "Numéro au format international, par exemple +33612345678"},
           "nom": {"type": "string", "description": "Nom du destinataire"},
           "texte": {"type": "string"}},
          ["numero", "texte"]),
    _tool("gerer_mails",
          "Agit sur des mails déjà trouvés avec chercher_mails, désignés par leurs références (M1, M2…). "
          "« corbeille » demande d'abord la confirmation de Kevin avec un bouton (récupérable 30 jours dans "
          "la corbeille Gmail) ; « archiver » et « marquer_lu » sont faits tout de suite.",
          {"action": {"type": "string", "enum": ["corbeille", "archiver", "marquer_lu"]},
           "references": {"type": "array", "items": {"type": "string"}, "description": "Par exemple ['M1']"}},
          ["action", "references"]),
]

CONVERSATION_TIMEOUT = timedelta(minutes=30)
TURNS_KEPT = 4


def _calls_written_as_text(content: str) -> list[dict]:
    """Mistral écrit parfois ses appels d'outils dans le texte ([TOOL_CALLS][{...}]) au lieu du champ prévu."""
    start = content.find("[{")
    if start == -1:
        return []
    try:
        items = json.loads(content[start:content.rfind("}]") + 2])
    except ValueError:
        return []
    known = {t["function"]["name"] for t in TOOLS}
    return [{"function": {"name": i["name"], "arguments": i.get("arguments") or {}}}
            for i in items if isinstance(i, dict) and i.get("name") in known]


@dataclass
class AgentReply:
    text: str
    events_added: list[str] = field(default_factory=list)
    mail_draft: dict | None = None
    mails_to_trash: list[dict] = field(default_factory=list)
    sms_draft: dict | None = None


class Agent:
    """Une seule conversation (Kevin), oubliée après 30 min sans message."""

    def __init__(self, calendar: CalendarService, notes: NotesService, mail: MailService,
                 addresses: list[str], tz, model: str,
                 contacts: ContactsService | None = None, sms: SmsService | None = None) -> None:
        self.calendar = calendar
        self.notes = notes
        self.mail = mail
        self.contacts = contacts
        self.sms = sms
        self.addresses = addresses
        self.tz = tz
        self.model = model
        self._turns: list[list[dict]] = []
        self._refs: dict[str, dict] = {}
        self._last_message: datetime | None = None

    def _system_prompt(self, now: datetime) -> str:
        days = "\n".join(
            f"- {JOURS[(now + timedelta(days=i)).weekday()]} {(now + timedelta(days=i)).date().isoformat()}"
            + (" (aujourd'hui)" if i == 0 else " (demain)" if i == 1 else "")
            for i in range(15)
        )
        return (
            "Tu es l'assistant personnel de Kevin. Il te parle surtout par messages vocaux transcrits, "
            "avec des hésitations et des fautes de transcription : comprends l'intention.\n"
            f"Nous sommes le {JOURS[now.weekday()]} {now.date().isoformat()}, il est {now:%H:%M} (heure de Paris).\n"
            f"Calendrier des prochains jours :\n{days}\n"
            f"Boîtes mail de Kevin : {', '.join(self.addresses)}. La première est sa boîte principale.\n\n"
            "Utilise les outils pour agir ou pour récupérer les informations, puis réponds à Kevin en français, "
            "de façon naturelle et courte, comme à l'oral. Respecte exactement ce qu'il demande (nombre de mails, "
            "résumé ou détail, boîte, période). Ne recopie jamais un mail brut : résume-le.\n"
            "Ne dis jamais qu'une action est faite (note, événement, mail) sans avoir appelé l'outil "
            "correspondant dans ce tour.\n"
            "Tu te souviens des échanges récents : « ce mail », « celui d'avant », « les deux premiers » "
            "désignent des mails déjà trouvés, utilise leurs références M1, M2… sans refaire de recherche. "
            "Ne montre pas ces références à Kevin.\n"
            "N'invente jamais d'adresse mail ni de numéro. Pour écrire à quelqu'un, cherche-le d'abord avec "
            "chercher_contact, puis si besoin dans ses mails (chercher_mails avec 'from:prénom' ou 'to:prénom'). "
            "S'il y a plusieurs personnes possibles, demande laquelle ; si tu ne trouves rien, demande l'adresse "
            "ou le numéro. Un SMS part toujours vers un numéro de mobile.\n"
            "Ta réponse est lue dans Telegram : texte simple, sans astérisques, sans titres ni mise en forme "
            "Markdown, avec au plus quelques tirets.\n"
            "Si la demande n'a rien à voir avec tes outils, réponds simplement."
        )

    def run(self, text: str, now: datetime) -> AgentReply | None:
        """Renvoie None si Ollama est indisponible (le bot passe alors sur les règles)."""
        if self._last_message and now - self._last_message > CONVERSATION_TIMEOUT:
            self._turns, self._refs = [], {}
        self._last_message = now
        turn = [{"role": "user", "content": text}]
        reply = AgentReply(text="")
        for _ in range(MAX_STEPS):
            history = [m for t in self._turns[-TURNS_KEPT:] for m in t]
            messages = [{"role": "system", "content": self._system_prompt(now)}] + history + turn
            message = self._chat(messages)
            if message is None:
                return None
            turn.append(message)
            calls = message.get("tool_calls") or _calls_written_as_text(message.get("content") or "")
            if not calls:
                reply.text = (message.get("content") or "").strip() or "C'est fait."
                self._remember(turn)
                return reply
            for call in calls:
                name = call["function"]["name"]
                args = call["function"].get("arguments") or {}
                if isinstance(args, str):
                    args = json.loads(args or "{}")
                log.info("Outil %s %s", name, args)
                try:
                    result = self._execute(name, args, reply)
                except Exception as e:
                    log.exception("Erreur outil %s", name)
                    result = f"Erreur : {e}"
                turn.append({"role": "tool", "tool_name": name, "content": result})
        reply.text = "Je n'ai pas réussi à aller au bout, tu peux reformuler ?"
        self._remember(turn)
        return reply

    def _remember(self, turn: list[dict]) -> None:
        # Les contenus de mails déjà lus sont raccourcis pour ne pas saturer la mémoire du modèle
        for older in self._turns:
            for m in older:
                if m["role"] == "tool" and len(m["content"]) > 1200:
                    m["content"] = m["content"][:1200] + " […]"
        self._turns = (self._turns + [turn])[-TURNS_KEPT:]

    def _chat(self, messages: list[dict]) -> dict | None:
        try:
            r = requests.post(OLLAMA_CHAT_URL, json={
                "model": self.model, "messages": messages, "tools": TOOLS, "stream": False, "think": False,
                "keep_alive": "5m", "options": {"temperature": 0.2, "num_ctx": 16384},
            }, timeout=180)
            r.raise_for_status()
            return r.json()["message"]
        except (requests.ConnectionError, requests.Timeout) as e:
            log.error("Ollama indisponible : %s", e)
            return None

    def _execute(self, name: str, args: dict, reply: AgentReply) -> str:
        if name == "chercher_mails":
            return self._search_mails(args)
        if name == "lire_agenda":
            first = date.fromisoformat(args["date_debut"])
            events = self.calendar.list_events(first, int(args.get("nombre_jours") or 1))
            if not events:
                return "Aucun événement sur cette période."
            return "\n".join(
                f"- {e.start.isoformat() if e.all_day else e.start.strftime('%Y-%m-%d %H:%M')}"
                f"{' (toute la journée)' if e.all_day else ''} : {e.title}" for e in events)
        if name == "ajouter_evenement":
            day = date.fromisoformat(args["date"])
            start = time.fromisoformat(args["heure"]) if args.get("heure") else None
            duration = timedelta(minutes=int(args.get("duree_minutes") or 60))
            event = self.calendar.create_event(args["titre"], day, start, duration)
            reply.events_added.append(event.id)
            return f"Événement ajouté : {args['titre']}, le {day.isoformat()}" + (f" à {args['heure']}" if start else "")
        if name == "ajouter_note":
            self.notes.add_note(args["contenu"], datetime.now(self.tz))
            return "Note ajoutée."
        if name == "envoyer_mail":
            account = self._resolve(args.get("boite"))[0]
            reply.mail_draft = {"boite": account, "destinataire": args["destinataire"],
                                "objet": args["objet"], "corps": args["corps"]}
            return (f"Brouillon prêt depuis {account}, en attente de la confirmation de Kevin. "
                    "Montre-lui le destinataire, l'objet et le texte, et dis-lui d'appuyer sur Envoyer.")
        if name == "gerer_mails":
            return self._manage_mails(args, reply)
        if name == "chercher_contact":
            if not self.contacts:
                return "Les contacts Google ne sont pas connectés."
            people = self.contacts.search(args["nom"])
            if not people:
                return f"Aucun contact trouvé pour « {args['nom']} »."
            lines = "\n".join(f"- {c.name or '(sans nom)'} | mails : {', '.join(c.emails) or 'aucun'} | "
                              f"téléphones : {', '.join(c.phones) or 'aucun'}" for c in people)
            if len(people) > 1:
                lines += ("\nPlusieurs correspondances : ne choisis pas toi-même, montre-les à Kevin "
                          "(nom et adresse ou numéro) et demande-lui laquelle utiliser.")
            return lines
        if name == "envoyer_sms":
            if not self.sms or not self.sms.configured:
                return "L'envoi de SMS n'est pas encore configuré (application du téléphone). Dis-le à Kevin."
            reply.sms_draft = {"numero": args["numero"], "nom": args.get("nom") or "", "texte": args["texte"]}
            return ("SMS prêt, en attente de la confirmation de Kevin. Montre-lui le destinataire et le texte, "
                    "et dis-lui d'appuyer sur Envoyer.")
        return f"Outil inconnu : {name}"

    def _manage_mails(self, args: dict, reply: AgentReply) -> str:
        refs = [r.strip().upper() for r in args.get("references") or []]
        unknown = [r for r in refs if r not in self._refs]
        if unknown or not refs:
            return f"Références inconnues : {', '.join(unknown) or 'aucune'}. Cherche d'abord les mails."
        mails = [self._refs[r] for r in refs]
        action = args.get("action")
        if action == "corbeille":
            reply.mails_to_trash.extend(mails)
            return ("En attente de la confirmation de Kevin : dis-lui quels mails vont à la corbeille "
                    "et qu'il doit appuyer sur le bouton.")
        for m in mails:
            if action == "archiver":
                self.mail.archive(m["boite"], m["id"])
            elif action == "marquer_lu":
                self.mail.mark_read(m["boite"], m["id"])
            else:
                return f"Action inconnue : {action}"
        return f"Fait ({action}) pour {len(mails)} mail(s)."

    def _resolve(self, wanted: str | None) -> list[str]:
        if not wanted:
            return self.addresses
        key = "".join(c for c in wanted.lower() if c.isalnum())
        hits = [a for a in self.addresses if key and key in "".join(c for c in a.lower() if c.isalnum())]
        return hits or self.addresses

    def _search_mails(self, args: dict) -> str:
        count = max(1, min(int(args.get("nombre") or 5), 10))
        query = (args.get("recherche") or "").strip() or "in:inbox"
        accounts = self._resolve(args.get("boite"))
        blocks = []
        for account in accounts:
            emails = self.mail.list_emails(account, count, query=query)
            for e in emails:
                ref = next((r for r, m in self._refs.items() if m["id"] == e.id), f"M{len(self._refs) + 1}")
                self._refs[ref] = {"boite": account, "id": e.id, "objet": e.subject, "de": e.sender}
                body = self.mail.get_body(account, e.id, limit=1500 if count > 3 else 3000)
                blocks.append(f"Réf {ref} [{account}] De : {e.sender} | Objet : {e.subject} | "
                              f"Reçu : {e.timestamp:%Y-%m-%d %H:%M} | {'lu' if e.is_read else 'non lu'}\n{body}")
        return "\n\n".join(blocks) or f"Aucun mail trouvé ({query}) dans {', '.join(accounts)}."
