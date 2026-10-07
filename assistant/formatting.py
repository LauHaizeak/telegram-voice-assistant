from __future__ import annotations

from datetime import date, datetime, time

from .calendar_service import Event

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]

HELP = (
    "Envoie-moi un vocal (ou un texte), par exemple :\n"
    "• « Ajoute à l'agenda demain à 14h réunion avec Paul »\n"
    "• « Note que je dois rappeler le garage »\n"
    "• « Lis mon agenda de demain »\n\n"
    "Commandes : /agenda (aujourd'hui), /demain, /semaine, /notes"
)


def format_day(day: date, today: date | None = None) -> str:
    if today is not None:
        delta = (day - today).days
        if delta == 0:
            return "aujourd'hui"
        if delta == 1:
            return "demain"
    return f"{JOURS[day.weekday()]} {day.day} {MOIS[day.month - 1]}"


def format_time(value: time) -> str:
    return f"{value.hour}h{value.minute:02d}" if value.minute else f"{value.hour}h"


def format_agenda(events: list[Event], first_day: date, days: int, today: date) -> str:
    label = "cette semaine" if days > 1 else format_day(first_day, today)
    if not events:
        return f"Rien de prévu {label}."
    lines = [f"📅 Agenda {label} :"]
    current: date | None = None
    for event in events:
        event_day = event.start if event.all_day else event.start.date()  # type: ignore[union-attr]
        if days > 1 and event_day != current:
            current = event_day
            lines.append(f"\n{format_day(event_day, today).capitalize()}")
        if event.all_day:
            lines.append(f"• Toute la journée : {event.title}")
        else:
            assert isinstance(event.start, datetime)
            lines.append(f"• {format_time(event.start.time())} : {event.title}")
    return "\n".join(lines)
