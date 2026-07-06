from dataclasses import dataclass
from engine.entities.store import EntityStore
from engine.physics.passability import PassabilityMap
from engine.physics.collision import MoveIntent

DIRECTION_DELTA = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}


@dataclass
class Command:
    entity_id: str
    action: str
    params: dict


class InputSystem:
    def __init__(self, store: EntityStore, passability: PassabilityMap):
        self._store = store
        self._passability = passability

    def run(self, tick: int, command_queue: list[Command]) -> list[MoveIntent]:
        from engine.entities.components import Position
        move_intents = []
        for cmd in command_queue:
            if cmd.action == "move":
                direction = cmd.params.get("direction", "south")
                dx, dy = DIRECTION_DELTA.get(direction, (0, 0))
                pos = self._store.get_component(cmd.entity_id, Position)
                if pos:
                    move_intents.append(MoveIntent(
                        entity_id=cmd.entity_id,
                        from_x=pos.x, from_y=pos.y,
                        to_x=pos.x + dx, to_y=pos.y + dy,
                        is_god=(cmd.entity_id == "god"),
                    ))
        return move_intents
