"""World Render Language (WRL) schema dataclasses."""
from dataclasses import dataclass, field


@dataclass
class WRLTileLayer:
    """Represents a tile layer with RLE-encoded row data."""

    width: int
    height: int
    rows: list[str]  # RLE-encoded rows


@dataclass
class WRLEntity:
    """Represents an entity in the world."""

    id: str
    kind: str  # humanoid | animal | object | structure | item_drop | effect_anchor
    x: int
    y: int
    sprite: str
    health: float = 1.0
    label: str = ""
    facing: str = "south"
    state: str = "idle"
    carrying: str = "none"
    footprint: list[list[int]] | None = None  # for multi-tile structures


@dataclass
class WRLLight:
    """Represents a light source in the world."""

    kind: str  # ambient | point
    color: str
    intensity: float
    x: float = 0.0
    y: float = 0.0
    radius_tiles: float = 0.0
    source: str = ""


@dataclass
class WRLParticle:
    """Represents particle effects like weather."""

    kind: str  # weather_rain | weather_snow | etc.
    intensity: float
    direction_deg: float = 270.0
    wind_px_per_tick: float = 0.0


@dataclass
class WRLOverlay:
    """Represents screen overlays like vignettes or color grades."""

    kind: str  # vignette | color_grade
    strength: float = 0.0


@dataclass
class WRLEffectLayer:
    """Represents effects layer containing lights, particles, and overlays."""

    lights: list[WRLLight] = field(default_factory=list)
    particles: list[WRLParticle] = field(default_factory=list)
    overlays: list[WRLOverlay] = field(default_factory=list)


@dataclass
class WRLTooltip:
    """Represents a tooltip UI element."""

    entity_id: str
    text: str
    style: str = "speech_bubble"


@dataclass
class WRLHud:
    """Represents a HUD (heads-up display) element."""

    kind: str  # minimap | clock | inventory
    visible: bool = True
    data: dict = field(default_factory=dict)


@dataclass
class WRLUILayer:
    """Represents the UI layer containing tooltips and HUD elements."""

    tooltips: list[WRLTooltip] = field(default_factory=list)
    huds: list[WRLHud] = field(default_factory=list)


@dataclass
class WRLFrame:
    """Represents a complete frame of the simulation in WRL format."""

    tick: int
    world_id: str
    timestamp_ms: int
    kind: str = "full"  # full | delta
    base_tick: int | None = None
    palette: dict[int, str] = field(default_factory=dict)  # index → sprite name
    tiles: WRLTileLayer | None = None
    entities: list[WRLEntity] = field(default_factory=list)
    effects: WRLEffectLayer = field(default_factory=WRLEffectLayer)
    ui: WRLUILayer = field(default_factory=WRLUILayer)
    for_agent: str | None = None
    visibility_radius: int | None = None
