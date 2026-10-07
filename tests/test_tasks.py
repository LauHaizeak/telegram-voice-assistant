from assistant.tasks_service import Item, TasksService, _key


class FakeTasks(TasksService):
    """Remplace l'API Google par une liste en mémoire."""

    def __init__(self, titles):
        self.store = [Item(str(n), t) for n, t in enumerate(titles)]
        self.inserted = []

    def items(self, name):
        return list(self.store)

    def _list_id(self, name):
        return "liste"

    @property
    def _api(self):
        fake = self

        class Insert:
            def __init__(self, body):
                self.body = body

            def execute(self):
                fake.inserted.append(self.body["title"])
                fake.store.append(Item(str(len(fake.store)), self.body["title"]))

        class Tasks:
            def insert(self, tasklist, body):
                return Insert(body)

        class Api:
            def tasks(self):
                return Tasks()

        return Api()


def test_key_ignores_case_accents_and_spaces():
    assert _key(" Crème fraîche ") == _key("creme fraiche")


def test_add_skips_items_already_on_the_list():
    tasks = FakeTasks(["Lait", "Pain"])
    added, skipped = tasks.add("Courses", ["lait", "piles", "Piles"])
    assert added == ["piles"]
    assert skipped == ["lait", "Piles"]
    assert tasks.inserted == ["Piles"]


def test_match_finds_close_names():
    tasks = FakeTasks(["Pain complet", "Lait", "Piles AA"])
    found, missing = tasks.match("Courses", ["pain", "LAIT", "beurre"])
    assert [i.title for i in found] == ["Pain complet", "Lait"]
    assert missing == ["beurre"]
