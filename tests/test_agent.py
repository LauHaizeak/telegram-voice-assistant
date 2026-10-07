from datetime import datetime
from zoneinfo import ZoneInfo

from assistant.agent import Agent, _calls_written_as_text

NOW = datetime(2026, 10, 7, 10, 0, tzinfo=ZoneInfo("Europe/Paris"))
ADDRESSES = ["perso.martin@gmail.com", "atelier.martin@gmail.com", "64boutique@gmail.com"]


def make_agent() -> Agent:
    return Agent(None, None, None, ADDRESSES, ZoneInfo("Europe/Paris"), "test")


def test_tool_calls_written_in_text_are_recovered():
    content = '[TOOL_CALLS][{"name": "ajouter_note", "arguments": {"contenu": "piles"}}]'
    assert _calls_written_as_text(content) == [{"function": {"name": "ajouter_note", "arguments": {"contenu": "piles"}}}]


def test_unknown_tool_written_in_text_is_ignored():
    assert _calls_written_as_text('[{"name": "supprimer_tout", "arguments": {}}]') == []
    assert _calls_written_as_text("Voici ta réponse.") == []


def test_mailbox_is_resolved_from_a_partial_name():
    agent = make_agent()
    assert agent._resolve("atelier") == ["atelier.martin@gmail.com"]
    assert agent._resolve("Boutique") == ["64boutique@gmail.com"]
    assert agent._resolve("") == ADDRESSES
    assert agent._resolve("inconnue") == ADDRESSES


def test_system_prompt_gives_the_real_weekdays():
    prompt = make_agent()._system_prompt(NOW)
    assert "mercredi 2026-10-07 (aujourd'hui)" in prompt
    assert "jeudi 2026-10-08 (demain)" in prompt
    assert "lundi 2026-10-12" in prompt
