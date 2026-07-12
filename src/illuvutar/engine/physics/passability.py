from illuvutar.engine.entities.store import EntityStore
from illuvutar.engine.entities.components import Tags


class PassabilityMap:
    def __init__(self, tilemap: list[list[str]], rules: dict[str, str]):
        self._tilemap = tilemap
        self._rules = rules

    def passability_class(self, tile_id: str) -> str:
        return self._rules.get(tile_id, "open")

    def can_enter(self, entity_id: str, x: int, y: int, store: EntityStore) -> bool:
        if entity_id == "god":
            return True
        if y < 0 or y >= len(self._tilemap) or x < 0 or x >= len(self._tilemap[0]):
            return False
        tile = self._tilemap[y][x]
        pc = self.passability_class(tile)
        if pc == "blocked":
            return False
        if pc == "conditional":
            tags = store.get_component(entity_id, Tags)
            return tags is not None and tags.has("can_open_doors")
        return True
