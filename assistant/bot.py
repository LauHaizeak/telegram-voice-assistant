from __future__ import annotations

import asyncio
import json
import logging
import tempfile
import uuid
from datetime import datetime, timedelta
from functools import partial
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from .agent import Agent
from .calendar_service import CalendarService
from .config import DATA_DIR, Config
from .formatting import HELP, format_agenda, format_day, format_time
from .intents import Intent, IntentType, parse
from .mail_service import MailService
from .notes_service import NotesService
from .sms_service import SmsService
from .transcribe import Transcriber
from .voice import Speaker

log = logging.getLogger(__name__)
SETTINGS_FILE = DATA_DIR / "reglages.json"


def _confirmation_text(reply) -> str:
    parts = []
    if reply.mail_draft:
        d = reply.mail_draft
        parts.append(f"✉️ À : {d['destinataire']}\nObjet : {d['objet']}\n\n{d['corps']}")
    if reply.sms_draft:
        d = reply.sms_draft
        parts.append(f"📱 SMS à {d['nom'] + ' ' if d['nom'] else ''}({d['numero']}) :\n{d['texte']}")
    if reply.mails_to_trash:
        parts.append("🗑️ À mettre à la corbeille :\n" + "\n".join(f"• {m['de']} : {m['objet']}" for m in reply.mails_to_trash))
    if reply.events_added:
        parts.append("📅 Événement ajouté à l'agenda.")
    return "\n\n".join(parts)[:4000]


class Assistant:
    def __init__(
        self,
        config: Config,
        transcriber: Transcriber,
        calendar: CalendarService,
        notes: NotesService,
        mail: MailService,
        agent: Agent,
        sms: SmsService,
        speaker: Speaker,
    ) -> None:
        self.speaker = speaker
        try:
            self.settings = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.settings = {}
        self.config = config
        self.transcriber = transcriber
        self.calendar = calendar
        self.notes = notes
        self.mail = mail
        self.agent = agent
        self.pending_mails: dict[str, dict] = {}
        self.pending_trash: dict[str, list[dict]] = {}
        self.sms = sms
        self.pending_sms: dict[str, dict] = {}
        self.shown_lists: dict[str, tuple[str, dict]] = {}

    def now(self) -> datetime:
        return datetime.now(self.config.timezone)

    def build_app(self) -> Application:
        app = Application.builder().token(self.config.telegram_token).build()
        allowed = filters.User(user_id=list(self.config.allowed_user_ids))

        app.add_handler(CommandHandler("start", self.on_start, filters=allowed))
        app.add_handler(CommandHandler(["agenda", "aujourdhui"], partial(self.on_agenda, offset=0, days=1), filters=allowed))
        app.add_handler(CommandHandler("demain", partial(self.on_agenda, offset=1, days=1), filters=allowed))
        app.add_handler(CommandHandler("semaine", self.on_week, filters=allowed))
        app.add_handler(CommandHandler("notes", self.on_notes, filters=allowed))
        app.add_handler(CommandHandler("mails", self.on_list_unread_mails, filters=allowed))
        for mode in ("vocal", "texte", "auto"):
            app.add_handler(CommandHandler(mode, partial(self.on_reply_mode, mode=mode), filters=allowed))
        app.add_handler(MessageHandler(allowed & (filters.VOICE | filters.AUDIO), self.on_voice))
        app.add_handler(MessageHandler(allowed & filters.TEXT & ~filters.COMMAND, self.on_text))
        app.add_handler(CallbackQueryHandler(self.on_cancel, pattern=r"^cancel:"))
        app.add_handler(CallbackQueryHandler(self.on_confirm_send, pattern=r"^(send|drop)_mail:"))
        app.add_handler(CallbackQueryHandler(self.on_confirm_trash, pattern=r"^(trash|keep)_mails:"))
        app.add_handler(CallbackQueryHandler(self.on_confirm_sms, pattern=r"^(send|drop)_sms:"))
        app.add_handler(CallbackQueryHandler(self.on_tick, pattern=r"^tick:"))
        app.add_handler(CommandHandler("courses", self.on_shopping_list, filters=allowed))
        app.add_handler(MessageHandler(filters.ALL, self.on_unauthorized))
        return app

    async def on_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text("Salut Kevin ! " + HELP)
        await self.on_agenda(update, context, offset=0, days=1)

    async def on_agenda(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, offset: int, days: int
    ) -> None:
        today = self.now().date()
        await self._send_agenda(update, today + timedelta(days=offset), days)

    async def on_week(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        today = self.now().date()
        await self._send_agenda(update, today, 7 - today.weekday())

    async def on_notes(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        url = await asyncio.to_thread(lambda: self.notes.doc_url)
        await update.message.reply_text(f"📝 Tes notes : {url}")

    async def on_list_unread_mails(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        counts = [(a, await asyncio.to_thread(self.mail.get_unread_count, a)) for a in self.config.gmail_addresses]
        lines = [f"• {address} : {count}" for address, count in counts if count]
        await update.message.reply_text("📧 Mails non lus :\n" + "\n".join(lines) if lines else "✅ Aucun mail non lu")

    async def on_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        media = update.message.voice or update.message.audio
        status = await update.message.reply_text("🎧 Transcription…")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "message.ogg"
            tg_file = await media.get_file()
            await tg_file.download_to_drive(path)
            text = await asyncio.to_thread(self.transcriber.transcribe, path)
        if not text:
            await status.edit_text("Je n'ai rien entendu, tu peux répéter ?")
            return
        await status.edit_text(f"🗣️ « {text} »")
        await self._handle(update, text, from_voice=True)

    async def on_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._handle(update, update.message.text)

    async def on_cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if query.from_user.id not in self.config.allowed_user_ids:
            await query.answer()
            return
        event_id = query.data.split(":", 1)[1]
        await asyncio.to_thread(self.calendar.delete_event, event_id)
        await query.answer("Supprimé")
        await query.edit_message_text(query.message.text + "\n\n❌ Annulé, l'événement a été supprimé.")

    async def on_unauthorized(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        if update.message and user and not self.config.allowed_user_ids:
            await update.message.reply_text(
                f"Ton identifiant Telegram est {user.id}. "
                "Ajoute-le dans ALLOWED_USER_IDS du fichier .env puis relance le bot."
            )
        elif user:
            log.warning("Message ignoré d'un utilisateur non autorisé : %s", user.id)

    def _wants_voice(self, from_voice: bool) -> bool:
        mode = self.settings.get("reponse", self.config.voice_replies)
        return mode == "vocal" or (mode == "auto" and from_voice)

    async def on_reply_mode(self, update: Update, context: ContextTypes.DEFAULT_TYPE, mode: str) -> None:
        self.settings["reponse"] = mode
        SETTINGS_FILE.write_text(json.dumps(self.settings), encoding="utf-8")
        await update.message.reply_text({
            "vocal": "🔊 Je réponds maintenant toujours en vocal.",
            "texte": "💬 Je réponds maintenant toujours par écrit.",
            "auto": "🔁 Je réponds en vocal à tes vocaux et par écrit à tes messages écrits.",
        }[mode])

    async def _handle(self, update: Update, text: str, from_voice: bool = False) -> None:
        oral = self._wants_voice(from_voice)
        await update.message.chat.send_action(ChatAction.RECORD_VOICE if oral else ChatAction.TYPING)
        try:
            reply = await asyncio.to_thread(self.agent.run, text, self.now(), oral)
        except Exception:
            log.exception("Erreur de l'agent sur %r", text)
            await update.message.reply_text("⚠️ Une erreur est survenue, regarde data\\bot.log.")
            return
        if reply is None:
            log.warning("Ollama indisponible, passage sur les règles")
            await self._handle_with_rules(update, text)
            return

        buttons = [[InlineKeyboardButton("Annuler l'événement", callback_data=f"cancel:{eid}")]
                   for eid in reply.events_added]
        if reply.mail_draft:
            draft_id = uuid.uuid4().hex[:12]
            self.pending_mails[draft_id] = reply.mail_draft
            buttons.append([InlineKeyboardButton("✉️ Envoyer", callback_data=f"send_mail:{draft_id}"),
                            InlineKeyboardButton("Ne pas envoyer", callback_data=f"drop_mail:{draft_id}")])
        if reply.sms_draft:
            sms_id = uuid.uuid4().hex[:12]
            self.pending_sms[sms_id] = reply.sms_draft
            buttons.append([InlineKeyboardButton("📱 Envoyer le SMS", callback_data=f"send_sms:{sms_id}"),
                            InlineKeyboardButton("Ne pas envoyer", callback_data=f"drop_sms:{sms_id}")])
        if reply.list_shown and reply.list_shown[1]:
            buttons += self._tick_buttons(*reply.list_shown)
        if reply.mails_to_trash:
            trash_id = uuid.uuid4().hex[:12]
            self.pending_trash[trash_id] = reply.mails_to_trash
            label = "🗑️ Corbeille" if len(reply.mails_to_trash) == 1 else f"🗑️ Corbeille ({len(reply.mails_to_trash)})"
            buttons.append([InlineKeyboardButton(label, callback_data=f"trash_mails:{trash_id}"),
                            InlineKeyboardButton("Garder", callback_data=f"keep_mails:{trash_id}")])
        markup = InlineKeyboardMarkup(buttons) if buttons else None
        if oral:
            try:
                audio = await asyncio.to_thread(self.speaker.speak, reply.text)
                await update.message.reply_voice(audio)
                if markup:
                    # Les boutons restent en texte sous le vocal, avec ce qui va réellement partir
                    await update.message.reply_text(_confirmation_text(reply), reply_markup=markup)
                return
            except Exception:
                log.exception("Synthèse vocale impossible, réponse par écrit")
        await update.message.reply_text(reply.text[:4000], reply_markup=markup)

    async def _handle_with_rules(self, update: Update, text: str) -> None:
        intent = parse(text, self.now())
        try:
            if intent.type is IntentType.ADD_EVENT:
                await self._add_event(update, intent)
            elif intent.type is IntentType.NOTE:
                await self._add_note(update, intent)
            elif intent.type is IntentType.READ_AGENDA:
                await self._send_agenda(update, intent.day, intent.days_span)
            elif intent.type is IntentType.READ_MAIL:
                await self._read_mails(update)
            elif intent.type is IntentType.SEND_MAIL:
                await update.message.reply_text("L'IA est indisponible pour le moment, je ne peux pas rédiger de mail.")
            else:
                await update.message.reply_text("Je n'ai pas compris. " + HELP)
        except Exception:
            log.exception("Erreur en traitant %r", text)
            await update.message.reply_text("⚠️ Une erreur est survenue, regarde les logs du bot.")

    async def _add_event(self, update: Update, intent: Intent) -> None:
        event = await asyncio.to_thread(
            self.calendar.create_event, intent.title, intent.day, intent.start, intent.duration
        )
        when = format_day(intent.day, self.now().date())
        when += f" à {format_time(intent.start)}" if intent.start else " (toute la journée)"
        button = InlineKeyboardMarkup(
            [[InlineKeyboardButton("Annuler", callback_data=f"cancel:{event.id}")]]
        )
        await update.message.reply_text(f"✅ Ajouté : {intent.title}, {when}.", reply_markup=button)

    async def _add_note(self, update: Update, intent: Intent) -> None:
        if not intent.title:
            await update.message.reply_text("Que veux-tu que je note ?")
            return
        await asyncio.to_thread(self.notes.add_note, intent.title, self.now())
        await update.message.reply_text(f"📝 Noté : {intent.title}")

    async def _send_agenda(self, update: Update, first_day, days: int) -> None:
        events = await asyncio.to_thread(self.calendar.list_events, first_day, days)
        await update.message.reply_text(
            format_agenda(events, first_day, days, self.now().date())
        )

    async def _read_mails(self, update: Update) -> None:
        lines = []
        for address in self.config.gmail_addresses:
            emails = await asyncio.to_thread(self.mail.list_emails, address, 3)
            lines += [f"\n{address} :"] + [f"• {e.sender[:40]} : {e.subject[:60]}" for e in emails] if emails else []
        await update.message.reply_text("📧 Derniers non lus :" + "\n".join(lines) if lines else "✅ Aucun mail non lu")

    async def on_confirm_send(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if query.from_user.id not in self.config.allowed_user_ids:
            await query.answer()
            return
        action, draft_id = query.data.split(":", 1)
        draft = self.pending_mails.pop(draft_id, None)
        if draft is None:
            await query.answer("Ce brouillon n'existe plus")
            await query.edit_message_reply_markup(None)
            return
        if action == "drop_mail":
            await query.answer("Pas envoyé")
            await query.edit_message_text(query.message.text + "\n\n🗑️ Mail non envoyé.")
            return
        try:
            await asyncio.to_thread(self.mail.send_email, draft["boite"], draft["destinataire"],
                                    draft["objet"], draft["corps"])
            await query.answer("✅ Mail envoyé")
            await query.edit_message_text(query.message.text + f"\n\n✅ Envoyé à {draft['destinataire']}.")
        except Exception:
            log.exception("Erreur envoi mail")
            await query.answer("❌ Erreur envoi")
            await query.edit_message_text(query.message.text + "\n\n❌ Erreur lors de l'envoi")


    def _tick_buttons(self, list_name: str, items: list) -> list[list[InlineKeyboardButton]]:
        list_id = uuid.uuid4().hex[:8]
        self.shown_lists[list_id] = (list_name, {str(n): i for n, i in enumerate(items)})
        return [[InlineKeyboardButton(f"✅ {i.title}"[:60], callback_data=f"tick:{list_id}:{n}")]
                for n, i in enumerate(items[:30])]

    async def on_shopping_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        items = await asyncio.to_thread(self.agent.tasks.items, "Courses")
        if not items:
            await update.message.reply_text("🛒 La liste de courses est vide.")
            return
        await update.message.reply_text(f"🛒 Courses ({len(items)}) : appuie sur un article pour le cocher.",
                                        reply_markup=InlineKeyboardMarkup(self._tick_buttons("Courses", items)))

    async def on_tick(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if query.from_user.id not in self.config.allowed_user_ids:
            await query.answer()
            return
        _, list_id, n = query.data.split(":", 2)
        shown = self.shown_lists.get(list_id)
        item = shown[1].pop(n, None) if shown else None
        if item is None:
            await query.answer("Déjà coché")
            return
        await asyncio.to_thread(self.agent.tasks.complete, shown[0], item.id)
        await query.answer(f"Coché : {item.title}")
        remaining = [[b for b in row if b.callback_data != query.data] for row in query.message.reply_markup.inline_keyboard]
        remaining = [row for row in remaining if row]
        if not shown[1]:
            await query.edit_message_text(query.message.text + f"\n\n🎉 Tout est coché sur « {shown[0]} ».")
        else:
            await query.edit_message_reply_markup(InlineKeyboardMarkup(remaining))

    async def on_confirm_sms(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if query.from_user.id not in self.config.allowed_user_ids:
            await query.answer()
            return
        action, sms_id = query.data.split(":", 1)
        draft = self.pending_sms.pop(sms_id, None)
        if draft is None:
            await query.answer("Déjà traité")
            await query.edit_message_reply_markup(None)
            return
        if action == "drop_sms":
            await query.answer("Pas envoyé")
            await query.edit_message_text(query.message.text + "\n\n🗑️ SMS non envoyé.")
            return
        await query.answer("Envoi…")
        try:
            state = await asyncio.to_thread(self.sms.send, draft["numero"], draft["texte"])
        except Exception:
            log.exception("Erreur SMS")
            await query.edit_message_text(
                query.message.text + "\n\n❌ SMS non envoyé : le téléphone ne répond pas (même Wi-Fi ? appli ouverte ?).")
            return
        labels = {"Sent": "✅ SMS envoyé", "Delivered": "✅ SMS reçu par le destinataire",
                  "Failed": "❌ Le téléphone n'a pas pu envoyer le SMS"}
        await query.edit_message_text(query.message.text + "\n\n" + labels.get(state, f"⏳ SMS en cours ({state})"))

    async def on_confirm_trash(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if query.from_user.id not in self.config.allowed_user_ids:
            await query.answer()
            return
        action, trash_id = query.data.split(":", 1)
        mails = self.pending_trash.pop(trash_id, None)
        if mails is None:
            await query.answer("Déjà traité")
            await query.edit_message_reply_markup(None)
            return
        if action == "keep_mails":
            await query.answer("Gardé")
            await query.edit_message_text(query.message.text + "\n\n👍 Rien n'a été supprimé.")
            return
        try:
            for m in mails:
                await asyncio.to_thread(self.mail.trash, m["boite"], m["id"])
            await query.answer("Mis à la corbeille")
            await query.edit_message_text(
                query.message.text + f"\n\n🗑️ {len(mails)} mail(s) à la corbeille (récupérable 30 jours dans Gmail).")
        except Exception:
            log.exception("Erreur corbeille")
            await query.answer("❌ Erreur")
            await query.edit_message_text(query.message.text + "\n\n❌ La mise à la corbeille a échoué.")


def state_file() -> Path:
    return DATA_DIR / "state.json"
