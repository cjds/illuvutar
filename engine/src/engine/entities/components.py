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


def _truncate_words(text: str, limit: int) -> str:
    return " ".join((text or "").split()[:max(0, limit)])


@dataclass
class Mind:
    memory: str = ""                 # episodic — "what happened"
    facts: str = ""                  # self-beliefs — "who I am"
    memory_word_limit: int = 60
    facts_word_limit: int = 30

    def set_memory(self, text: str) -> bool:
        new = _truncate_words(text, self.memory_word_limit)
        if new == self.memory:
            return False
        self.memory = new
        return True

    def set_facts(self, text: str) -> bool:
        new = _truncate_words(text, self.facts_word_limit)
        if new == self.facts:
            return False
        self.facts = new
        return True
