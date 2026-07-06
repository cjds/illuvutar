from engine.entities.store import EntityStore
from engine.entities.components import Health


class HealthSystem:
    def __init__(self, store: EntityStore):
        self._store = store

    def run(self, tick: int) -> list[str]:
        dead = []
        for entity_id in self._store.all_ids():
            health = self._store.get_component(entity_id, Health)
            if health and health.current <= 0:
                dead.append(entity_id)
        return dead
