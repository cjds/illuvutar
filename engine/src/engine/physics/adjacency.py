from engine.entities.store import EntityStore
from engine.entities.components import Position


def get_adjacent_entities(entity_id: str, store: EntityStore, radius: int = 1) -> list[str]:
    pos = store.get_component(entity_id, Position)
    if pos is None:
        return []
    result = []
    for other_id in store.all_ids():
        if other_id == entity_id:
            continue
        other_pos = store.get_component(other_id, Position)
        if other_pos is None:
            continue
        if abs(other_pos.x - pos.x) <= radius and abs(other_pos.y - pos.y) <= radius:
            result.append(other_id)
    return result
