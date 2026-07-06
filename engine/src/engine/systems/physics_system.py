from engine.entities.store import EntityStore
from engine.entities.components import Position
from engine.physics.passability import PassabilityMap
from engine.physics.collision import MoveIntent, resolve_conflicts


class PhysicsSystem:
    def __init__(self, store: EntityStore, passability: PassabilityMap):
        self._store = store
        self._passability = passability

    def run(self, tick: int, move_intents: list[MoveIntent]) -> dict[str, bool]:
        results = resolve_conflicts(move_intents, self._store, self._passability)
        for intent in move_intents:
            if results.get(intent.entity_id, False):
                self._store.set_component(intent.entity_id, Position(x=intent.to_x, y=intent.to_y))
        return results
