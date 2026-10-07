from datetime import date, datetime, time, timedelta

import pytest

from assistant.intents import IntentType, parse

# Mercredi 7 octobre 2026, 10h
NOW = datetime(2026, 10, 7, 10, 0)


def test_add_event_tomorrow_with_time():
    intent = parse("Ajoute à l'agenda demain à 14h réunion avec Paul.", NOW)
    assert intent.type is IntentType.ADD_EVENT
    assert intent.day == date(2026, 10, 8)
    assert intent.start == time(14, 0)
    assert intent.title == "Réunion avec Paul"


def test_add_event_named_date_and_minutes():
    intent = parse("Ajoute un rendez-vous le 15 novembre à 9h30 dentiste", NOW)
    assert intent.day == date(2026, 11, 15)
    assert intent.start == time(9, 30)
    assert intent.title == "Dentiste"


def test_add_event_spoken_hours_and_weekday():
    intent = parse("Mets dans mon agenda vendredi à trois heures et demie de l'après-midi le garage", NOW)
    assert intent.day == date(2026, 10, 9)
    assert intent.start == time(15, 30)
    assert intent.title == "Garage"


def test_add_event_without_time_is_all_day():
    intent = parse("Ajoute à l'agenda le 1er décembre anniversaire de Léa", NOW)
    assert intent.day == date(2026, 12, 1)
    assert intent.start is None
    assert intent.title == "Anniversaire de Léa"


def test_add_event_duration():
    intent = parse("Planifie demain à 10h sport pendant 2 heures", NOW)
    assert intent.start == time(10, 0)
    assert intent.duration == timedelta(hours=2)
    assert intent.title == "Sport"


def test_past_date_goes_to_next_year():
    intent = parse("Ajoute à l'agenda le 3 mars contrôle technique", NOW)
    assert intent.day == date(2027, 3, 3)


def test_rdv_shortcut():
    intent = parse("Rendez-vous lundi midi déjeuner avec Marc", NOW)
    assert intent.type is IntentType.ADD_EVENT
    assert intent.day == date(2026, 10, 12)
    assert intent.start == time(12, 0)
    assert intent.title == "Déjeuner avec Marc"


@pytest.mark.parametrize(
    "text, content",
    [
        ("Note que je dois rappeler le garage.", "Je dois rappeler le garage"),
        ("Prends note : acheter du pain", "Acheter du pain"),
        ("Note ceci, idée de cadeau pour Julie", "Idée de cadeau pour Julie"),
    ],
)
def test_note(text, content):
    intent = parse(text, NOW)
    assert intent.type is IntentType.NOTE
    assert intent.title == content


@pytest.mark.parametrize(
    "text, day, span",
    [
        ("Lis mon agenda", date(2026, 10, 7), 1),
        ("Qu'est-ce que j'ai demain ?", date(2026, 10, 8), 1),
        ("Lis-moi mon agenda de la semaine", date(2026, 10, 7), 5),
        ("Qu'est-ce que j'ai de prévu cette semaine", date(2026, 10, 7), 5),
        ("Mon agenda de vendredi", date(2026, 10, 9), 1),
    ],
)
def test_read_agenda(text, day, span):
    intent = parse(text, NOW)
    assert intent.type is IntentType.READ_AGENDA
    assert intent.day == day
    assert intent.days_span == span


def test_unknown():
    assert parse("Quel temps fait-il ?", NOW).type is IntentType.UNKNOWN
