from dataclasses import dataclass
from engine.entities.store import EntityStore
from engine.entities.components import PhysicsComponent, Tags
from engine.physics.passability import PassabilityMap


@dataclass
class MoveIntent:
    entity_id: str
    from_x: int
    from_y: int
    to_x: int
    to_y: int
    is_god: bool = False


def resolve_conflicts(
    intents: list[MoveIntent],
    store: EntityStore,
    passability: PassabilityMap,
) -> dict[str, bool]:
    results: dict[str, bool] = {}
    by_destination: dict[tuple[int, int], list[MoveIntent]] = {}

    for intent in intents:
        if not passability.can_enter(intent.entity_id, intent.to_x, intent.to_y, store):
            results[intent.entity_id] = False
            continue
        key = (intent.to_x, intent.to_y)
        by_destination.setdefault(key, []).append(intent)

    for (x, y), competing in by_destination.items():
        shareable = []
        blocking = []
        for intent in competing:
            tags = store.get_component(intent.entity_id, Tags)
            if tags and tags.has("can_share_tile"):
                shareable.append(intent)
            else:
                blocking.append(intent)

        for intent in shareable:
            results[intent.entity_id] = True

        if not blocking:
            continue
        if len(blocking) == 1:
            results[blocking[0].entity_id] = True
            continue

        def priority(intent: MoveIntent) -> tuple[int, str]:
            if intent.is_god:
                return (9999, intent.entity_id)
            phys = store.get_component(intent.entity_id, PhysicsComponent)
            p = phys.collision_priority if phys else 0
            return (p, intent.entity_id)

        blocking.sort(key=lambda intent: (-priority(intent)[0], priority(intent)[1]))
        results[blocking[0].entity_id] = True
        for loser in blocking[1:]:
            results[loser.entity_id] = False

    return results
