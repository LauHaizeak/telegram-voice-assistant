"""Essaie l'agent sur des phrases libres. Lecture réelle (mails, agenda), écritures simulées."""

import sys
import time
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from assistant.__main__ import build_services  # noqa: E402

PHRASES = sys.argv[1:] or [
    "Lis le dernier mail sur ma boîte principale",
    "euh t'as vu passer un truc de la banque ces derniers jours ?",
    "fais-moi un petit point sur mes mails non lus de toutes mes boîtes",
    "c'est quoi les deux derniers mails que j'ai reçus sur ma deuxième boîte ?",
    "qu'est-ce que j'ai jeudi ?",
    "rappelle-moi d'appeler maman après-demain à 18h",
    "euh note qu'il faut racheter des piles pour la télécommande",
    "envoie un mail à paul pour lui dire que je serai en retard demain",
]


def main() -> None:
    import logging
    logging.basicConfig(format="   [outil] %(message)s", level=logging.WARNING)
    logging.getLogger("assistant.agent").setLevel(logging.INFO)
    config, calendar, notes, mail, agent, _ = build_services()
    calendar.create_event = lambda title, day, start, duration: (
        print(f"   [simulé] agenda : {title} {day} {start} {duration}") or SimpleNamespace(id="test"))
    notes.add_note = lambda text, when: print(f"   [simulé] note : {text}")
    for phrase in PHRASES:
        t = time.perf_counter()
        reply = agent.run(phrase, datetime.now(config.timezone))
        print(f"\n>> {phrase}\n   ({time.perf_counter() - t:.1f} s)")
        if reply is None:
            print("   Ollama indisponible")
            continue
        print("   " + reply.text.replace("\n", "\n   "))
        if reply.mail_draft:
            print(f"   [brouillon, non envoyé] {reply.mail_draft}")


if __name__ == "__main__":
    main()
