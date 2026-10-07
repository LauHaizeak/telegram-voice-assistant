"""Compréhension des commandes (texte transcrit) en français, sans LLM."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from enum import Enum


class IntentType(str, Enum):
    ADD_EVENT = "add_event"
    READ_AGENDA = "read_agenda"
    NOTE = "note"
    READ_MAIL = "read_mail"
    SEND_MAIL = "send_mail"
    UNKNOWN = "unknown"


@dataclass
class Intent:
    type: IntentType
    text: str
    title: str = ""
    day: date | None = None
    start: time | None = None
    duration: timedelta = field(default_factory=lambda: timedelta(hours=1))
    days_span: int = 1


MONTHS = {
    "janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
    "juillet": 7, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12,
}
WEEKDAYS = {
    "lundi": 0, "mardi": 1, "mercredi": 2, "jeudi": 3,
    "vendredi": 4, "samedi": 5, "dimanche": 6,
}
NUMBER_WORDS = {
    "une": 1, "un": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "six": 6,
    "sept": 7, "huit": 8, "neuf": 9, "dix": 10, "onze": 11, "douze": 12,
}
_NUMS = "|".join(sorted(NUMBER_WORDS, key=len, reverse=True))

_POLITE = r"(?:(?:euh|heu|alors|bon|ok|okay|ben|salut|bonjour|coucou|hey|dis|assistant)[\s,.!]+)*(?:(?:est-ce que tu peux|est ce que tu peux|est-ce que tu pourrais|tu pourrais|pourrais-tu|peux-tu|tu peux|je veux que tu|j'aimerais que tu|stp|s'il te plait|s'il te plait,)\s+)?"

NOTE_RE = re.compile(
    r"^" + _POLITE +
    r"(?:prends?\s+(?:en\s+)?note|note(?:r)?|ajoute(?:r)?\s+(?:une\s+)?note|"
    r"(?:une\s+)?nouvelle\s+note|rappelle-toi|souviens-toi)\b"
    r"(?:\s*(?:que|ceci|ca|cela|ce qui suit))?\s*[:,.]?\s*"
)
READ_RE = re.compile(
    r"\b(?:lis|lire|li|donne|montre|dis-moi|dis moi|quel est|c'est quoi|qu'est-ce que j'ai|"
    r"qu'est ce que j'ai|qu'ai-je|j'ai quoi|resume|qu'est-ce qu'il y a)\b.*"
    r"\b(?:agenda|programme|planning|rendez-vous|rdv|journee|semaine|prevu|aujourd'hui|demain)\b"
    r"|^(?:mon\s+)?(?:agenda|programme|planning)\b"
)
READ_MAIL_RE = re.compile(
    r"^" + _POLITE +
    r"(?:lis|lire|montre|donne|dis-moi|dis moi|quels?|"
    r"qu'est-ce que j'ai|qu'est ce que j'ai|resume|check)\b.*"
    r"\b(?:mails?|emails?|messages?)\b"
)
SEND_MAIL_RE = re.compile(
    r"^" + _POLITE +
    r"(?:envoie|envoyer|envoyes|envoyes-moi|envoies)\b.*"
    r"\b(?:mail|email|message)\b"
)
ADD_RE = re.compile(
    r"^" + _POLITE +
    r"(?:ajoute(?:r)?|mets?|mettre|cree(?:r)?|planifie(?:r)?|programme(?:r)?|inscris)\b"
    r"(?:\s+(?:a|dans)\s+(?:l'|mon\s+|l\s)?(?:agenda|calendrier|planning))?"
    r"(?:\s+(?:un|une)\s+(?:rendez-vous|rdv|evenement|rappel))?"
    r"|^(?:nouveau\s+|nouvel\s+)?(?:rendez-vous|rdv|evenement)\b"
)
AGENDA_WORDS_RE = re.compile(r"\b(?:a|dans)\s+(?:l'|mon\s+|l\s)?(?:agenda|calendrier|planning)\b")

DAY_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bapres[- ]demain\b"), "after_tomorrow"),
    (re.compile(r"\bdemain\b"), "tomorrow"),
    (re.compile(r"\baujourd'hui\b|\bce soir\b|\bcet apres-midi\b|\bce matin\b"), "today"),
    (re.compile(r"\b(?:cette|la) semaine\b"), "week"),
    (re.compile(r"\b(?:le\s+)?(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b"), "numeric"),
    (re.compile(r"\b(?:le\s+)?(1er|\d{1,2})\s+(" + "|".join(MONTHS) + r")(?:\s+(\d{4}))?\b"), "named"),
    (re.compile(r"\b(?:(?:le|ce)\s+)?(" + "|".join(WEEKDAYS) + r")(\s+prochain)?\b"), "weekday"),
]
TIME_RE = re.compile(
    r"(?:\b(?:a|vers|pour|de|des)\s+)?"
    r"(?:\b(midi|minuit)\b|\b(\d{1,2})\s*(?:h|heures?\b|:)\s*(\d{2})?\b|"
    r"\b(" + _NUMS + r")\s+heures?\b(?:\s+(?:et\s+)?(demie|quart))?)"
    r"(?:\s+(du matin|du soir|de l'apres-midi))?"
)
DURATION_RE = re.compile(
    r"\b(?:pendant|durant|pour)\s+(\d+|" + _NUMS + r")\s*(h\b|heures?\b|minutes?\b|min\b)"
)


class _Text:
    """Texte normalisé pour la détection, aligné caractère par caractère sur l'original."""

    def __init__(self, raw: str) -> None:
        orig = unicodedata.normalize("NFC", re.sub(r"\s+", " ", raw)).strip(" .!?")
        norm = "".join(
            c for c in unicodedata.normalize("NFD", orig.lower()) if unicodedata.category(c) != "Mn"
        ).replace("’", "'")
        if len(norm) != len(orig):
            orig = norm
        self.orig = orig
        self.norm = norm

    def cut(self, start: int, end: int) -> None:
        blank = " " * (end - start)
        self.orig = self.orig[:start] + blank + self.orig[end:]
        self.norm = self.norm[:start] + blank + self.norm[end:]


def _next_weekday(today: date, weekday: int, force_next: bool) -> date:
    delta = (weekday - today.weekday()) % 7
    if delta == 0 and force_next:
        delta = 7
    return today + timedelta(days=delta)


def _num(token: str) -> int:
    return int(token) if token.isdigit() else NUMBER_WORDS[token]


def _extract_day(t: _Text, today: date) -> tuple[date | None, int]:
    for pattern, kind in DAY_PATTERNS:
        for m in pattern.finditer(t.norm):
            if kind in ("today", "tomorrow", "after_tomorrow", "week", "weekday"):
                t.cut(*m.span())
                if kind == "today":
                    return today, 1
                if kind == "tomorrow":
                    return today + timedelta(days=1), 1
                if kind == "after_tomorrow":
                    return today + timedelta(days=2), 1
                if kind == "week":
                    return today, 7 - today.weekday()
                return _next_weekday(today, WEEKDAYS[m.group(1)], bool(m.group(2))), 1
            if kind == "numeric":
                d, mo = int(m.group(1)), int(m.group(2))
            else:
                d = 1 if m.group(1) == "1er" else int(m.group(1))
                mo = MONTHS[m.group(2)]
            y = int(m.group(3)) if m.group(3) else today.year
            y = y + 2000 if y < 100 else y
            try:
                found = date(y, mo, d)
            except ValueError:
                continue
            if not m.group(3) and found < today:
                found = found.replace(year=found.year + 1)
            t.cut(*m.span())
            return found, 1
    return None, 1


def _extract_time(t: _Text) -> time | None:
    for m in TIME_RE.finditer(t.norm):
        word, hour, minute, hour_word, fraction, period = m.groups()
        if word:
            h, mi = (12, 0) if word == "midi" else (0, 0)
        elif hour is not None:
            h, mi = int(hour), int(minute or 0)
        else:
            h = NUMBER_WORDS[hour_word]
            mi = {"demie": 30, "quart": 15}.get(fraction or "", 0)
        if period in ("du soir", "de l'apres-midi") and h < 12:
            h += 12
        if h > 23 or mi > 59:
            continue
        t.cut(*m.span())
        return time(h, mi)
    return None


def _extract_duration(t: _Text) -> timedelta | None:
    m = DURATION_RE.search(t.norm)
    if not m:
        return None
    value = _num(m.group(1))
    t.cut(*m.span())
    return timedelta(minutes=value) if m.group(2).startswith("min") else timedelta(hours=value)


_LEADING = re.compile(r"^(?:(?:pour|avec|que|de|d'|le|la|les|un|une|qui|et|a|à)\s+)+", re.IGNORECASE)
_TRAILING = re.compile(r"(?:\s+(?:le|la|a|à|pour|de|et|avec))+$", re.IGNORECASE)


def _clean_title(t: _Text) -> str:
    for m in AGENDA_WORDS_RE.finditer(t.norm):
        t.cut(*m.span())
    title = re.sub(r"\s+", " ", t.orig).strip(" ,.:;-")
    title = _LEADING.sub("", title)
    title = _TRAILING.sub("", title)
    title = title.strip(" ,.:;-")
    return title[:1].upper() + title[1:]


def parse(raw_text: str, now: datetime) -> Intent:
    t = _Text(raw_text)
    today = now.date()

    note = NOTE_RE.match(t.norm)
    if note:
        content = t.orig[note.end():].strip(" :,")
        return Intent(IntentType.NOTE, raw_text, title=content[:1].upper() + content[1:])

    if READ_MAIL_RE.search(t.norm):
        return Intent(IntentType.READ_MAIL, raw_text)

    if SEND_MAIL_RE.search(t.norm):
        return Intent(IntentType.SEND_MAIL, raw_text)

    add = ADD_RE.match(t.norm)
    if add:
        t.cut(*add.span())
        day, _ = _extract_day(t, today)
        duration = _extract_duration(t)
        start = _extract_time(t)
        intent = Intent(IntentType.ADD_EVENT, raw_text, title=_clean_title(t) or "Rendez-vous")
        intent.day = day or today
        intent.start = start
        if duration:
            intent.duration = duration
        return intent

    if READ_RE.search(t.norm):
        day, span = _extract_day(t, today)
        return Intent(IntentType.READ_AGENDA, raw_text, day=day or today, days_span=span)

    return Intent(IntentType.UNKNOWN, raw_text)
