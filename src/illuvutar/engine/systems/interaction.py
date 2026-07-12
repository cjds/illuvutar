from illuvutar.engine.entities.store import EntityStore
from illuvutar.engine.physics.adjacency import get_adjacent_entities


class InteractionSystem:
    def __init__(self, store: EntityStore):
        self._store = store

    def run(self, tick: int, interact_intents: list[dict]) -> list[dict]:
        events = []
        for intent in interact_intents:
            adj = get_adjacent_entities(intent["entity_id"], self._store)
            if intent.get("target_id") in adj:
                events.append({"kind": "interaction", "actor": intent["entity_id"], "target": intent["target_id"]})
        return events
