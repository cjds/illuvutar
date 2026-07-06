"""World state dataclasses for serialization and storage."""
from dataclasses import dataclass, field, asdict


@dataclass
class Constitution:
    world_name: str
    palette_used: str
    width: int
    height: int
    tone: str
    rules: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Region:
    id: int
    name: str
    biome: str
    centroid_x: float
    centroid_y: float
    atmosphere: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RegionMap:
    regions: list[Region]

    def to_dict(self) -> dict:
        return {"regions": [r.to_dict() for r in self.regions]}


@dataclass
class Faction:
    id: str
    name: str
    region_ids: list[int]
    disposition: str
    description: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class HistoryEvent:
    era: str
    event: str
    region_id: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AgentRecord:
    id: str
    kind: str
    x: int
    y: int
    name: str
    faction_id: str | None = None
    behavior: str = "wander_passive"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class WorldMeta:
    generation_log: list[dict] = field(default_factory=list)

    def log(self, agent: str, action: str, detail: str = "") -> None:
        self.generation_log.append({"agent": agent, "action": action, "detail": detail})

    def to_dict(self) -> dict:
        return {"generation_log": self.generation_log}
