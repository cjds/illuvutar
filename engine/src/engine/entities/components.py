from dataclasses import dataclass, field


@dataclass
class Position:
    x: int
    y: int
    layer: int = 0


@dataclass
class Sprite:
    sprite_name: str
    facing: str = "south"
    animation_state: str = "idle"
    frame: int = 0


@dataclass
class Health:
    current: float
    max: float = 100.0

    @property
    def normalized(self) -> float:
        return self.current / self.max if self.max > 0 else 0.0


@dataclass
class ItemStack:
    item_id: str
    quantity: int = 1


@dataclass
class Inventory:
    slots: list[ItemStack] = field(default_factory=list)
    capacity: int = 10
    carrying: str = "none"  # display label for WRL


@dataclass
class AIComponent:
    agent_id: str
    goal: str = "idle"
    memory_ref: str = ""


@dataclass
class PhysicsComponent:
    blocking: bool = True
    passable_by: list[str] = field(default_factory=list)
    collision_priority: int = 1  # higher = wins conflicts


@dataclass
class Label:
    name: str
    visible: bool = True


@dataclass
class Tags:
    values: list[str] = field(default_factory=list)

    def has(self, tag: str) -> bool:
        return tag in self.values
