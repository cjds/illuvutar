from typing import Type, TypeVar
from engine.entities.components import Position

T = TypeVar("T")


class EntityStore:
    def __init__(self):
        self._components: dict[str, dict[type, object]] = {}
        self._kinds: dict[str, str] = {}
        self._position_index: dict[tuple[int, int], set[str]] = {}

    def create(self, entity_id: str, kind: str, components: list) -> None:
        self._components[entity_id] = {}
        self._kinds[entity_id] = kind
        for component in components:
            self._components[entity_id][type(component)] = component
            if isinstance(component, Position):
                self._position_index.setdefault((component.x, component.y), set()).add(entity_id)

    def remove(self, entity_id: str) -> None:
        if entity_id not in self._components:
            return
        pos = self.get_component(entity_id, Position)
        if pos:
            cell = self._position_index.get((pos.x, pos.y), set())
            cell.discard(entity_id)
        del self._components[entity_id]
        del self._kinds[entity_id]

    def get_component(self, entity_id: str, component_type: Type[T]) -> T | None:
        return self._components.get(entity_id, {}).get(component_type)

    def set_component(self, entity_id: str, component) -> None:
        if entity_id not in self._components:
            return
        old_pos = self._components[entity_id].get(Position)
        if isinstance(component, Position) and old_pos:
            self._position_index.get((old_pos.x, old_pos.y), set()).discard(entity_id)
        self._components[entity_id][type(component)] = component
        if isinstance(component, Position):
            self._position_index.setdefault((component.x, component.y), set()).add(entity_id)

    def entities_at(self, x: int, y: int) -> list[str]:
        return list(self._position_index.get((x, y), set()))

    def all_ids(self) -> list[str]:
        return list(self._components.keys())

    def kind(self, entity_id: str) -> str | None:
        return self._kinds.get(entity_id)
