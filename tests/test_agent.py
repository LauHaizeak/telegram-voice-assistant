from datetime import datetime
from zoneinfo import ZoneInfo

from assistant.agent import Agent, AgentReply, _calls_written_as_text

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


class FakeMail:
    def __init__(self):
        self.done = []

    def archive(self, box, mail_id):
        self.done.append(("archive", box, mail_id))

    def mark_read(self, box, mail_id):
        self.done.append(("lu", box, mail_id))

    def trash(self, box, mail_id):
        self.done.append(("corbeille", box, mail_id))


def agent_with_known_mail() -> tuple[Agent, FakeMail]:
    mail = FakeMail()
    agent = Agent(None, None, mail, ADDRESSES, ZoneInfo("Europe/Paris"), "test")
    agent._refs["M1"] = {"boite": ADDRESSES[0], "id": "abc", "objet": "Promo", "de": "Boutique"}
    return agent, mail


def test_trash_waits_for_kevins_confirmation():
    agent, mail = agent_with_known_mail()
    reply = AgentReply(text="")
    agent._manage_mails({"action": "corbeille", "references": ["m1"]}, reply)
    assert mail.done == []
    assert reply.mails_to_trash == [agent._refs["M1"]]


def test_archive_and_mark_read_are_immediate():
    agent, mail = agent_with_known_mail()
    agent._manage_mails({"action": "archiver", "references": ["M1"]}, AgentReply(text=""))
    agent._manage_mails({"action": "marquer_lu", "references": ["M1"]}, AgentReply(text=""))
    assert mail.done == [("archive", ADDRESSES[0], "abc"), ("lu", ADDRESSES[0], "abc")]


def test_unknown_mail_reference_does_nothing():
    agent, mail = agent_with_known_mail()
    result = agent._manage_mails({"action": "corbeille", "references": ["M9"]}, AgentReply(text=""))
    assert "inconnues" in result and mail.done == []


def test_system_prompt_gives_the_real_weekdays():
    prompt = make_agent()._system_prompt(NOW)
    assert "mercredi 2026-10-07 (aujourd'hui)" in prompt
    assert "jeudi 2026-10-08 (demain)" in prompt
    assert "lundi 2026-10-12" in prompt
