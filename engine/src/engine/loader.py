"""Load a world-state directory into engine-ready data structures."""
from dataclasses import dataclass
from pathlib import Path
import json
import yaml

from engine.entities.store import EntityStore
from engine.entities.components import (
    Position, Sprite, Health, PhysicsComponent, Label, Tags, AIComponent
)
from engine.physics.passability import PassabilityMap


# Tags in palette that map to passability classes
_TAG_TO_CLASS = {
    "walkable": "open",
    "slow": "slow",
    "wading": "slow",
    "blocked": "blocked",
    "impassable": "blocked",
    "structure": "blocked",
    "high": "blocked",
    "void": "blocked",
}


@dataclass
class WorldData:
    store: EntityStore
    passability: PassabilityMap
    palette: dict[int, str]       # index → tile_id, for WRL rendering
    tilemap_data: list[dict]      # [{x, y, tile_id, region}, ...]
    world_id: str
    width: int
    height: int
    sprite_dir: Path | None = None


def load_world(world_dir: Path | str) -> WorldData:
    """Load a world-state directory into engine inputs."""
    world_dir = Path(world_dir)

    # --- Constitution ---
    constitution = yaml.safe_load((world_dir / "constitution.yaml").read_text())
    world_id = constitution.get("world_name", "world")
    width = int(constitution.get("width", 32))
    height = int(constitution.get("height", 32))
    palette_used = constitution.get("palette_used", "")

    # --- Palette ---
    palette_yaml = yaml.safe_load((world_dir / "palette.yaml").read_text()) or {}
    tile_list = palette_yaml.get("tiles", [])

    # Build palette dict: index → tile_id (for WRL)
    palette: dict[int, str] = {}
    passability_rules: dict[str, str] = {}

    for idx, tile in enumerate(tile_list):
        tile_id = tile["id"]
        palette[idx] = tile_id
        # Derive passability from tags (first match wins)
        tags = tile.get("tags", [])
        p_class = "open"
        for tag in tags:
            if tag in _TAG_TO_CLASS:
                p_class = _TAG_TO_CLASS[tag]
                break
        passability_rules[tile_id] = p_class

    # --- Tilemap ---
    tilemap_path = world_dir / "tilemap.json"
    tilemap_data: list[dict] = []
    if tilemap_path.exists():
        tilemap_data = json.loads(tilemap_path.read_text())

    # Build tilemap 2D list for PassabilityMap
    grid: list[list[str]] = [["void_tile"] * width for _ in range(height)]
    default_tile = list(palette.values())[0] if palette else "void_tile"
    for cell in tilemap_data:
        x, y = cell.get("x", 0), cell.get("y", 0)
        if 0 <= x < width and 0 <= y < height:
            grid[y][x] = cell.get("tile_id", default_tile)

    passability = PassabilityMap(tilemap=grid, rules=passability_rules)

    # --- Entities (agents.yaml) ---
    store = EntityStore()
    agents_path = world_dir / "agents.yaml"
    if agents_path.exists():
        agents_raw = yaml.safe_load(agents_path.read_text()) or []
        # agents.yaml can be a list or a dict with 'agents' key
        if isinstance(agents_raw, dict):
            agents_raw = agents_raw.get("agents", [])
        for agent in (agents_raw or []):
            eid = agent.get("id", f"e_{len(store.all_ids())}")
            kind = agent.get("kind", "humanoid")
            x = int(agent.get("x", 0))
            y = int(agent.get("y", 0))
            name = agent.get("name", eid)
            behavior = agent.get("behavior", "wander_passive")
            sprite_name = _sprite_for_kind(kind)
            store.create(eid, kind, [
                Position(x, y),
                Sprite(sprite_name),
                Health(100.0, 100.0),
                PhysicsComponent(blocking=True),
                Label(name),
                Tags(["agent", kind]),
                AIComponent(agent_id=eid, goal=behavior),
            ])

    # --- Sprite dir ---
    sprite_dir: Path | None = None
    if palette_used:
        candidate = Path(palette_used)
        if not candidate.is_absolute():
            # Try relative to CWD, then relative to world_dir parent chain
            for base in [Path.cwd(), world_dir.parent, world_dir.parent.parent]:
                resolved = base / candidate
                if resolved.is_dir():
                    candidate = resolved
                    break
        if candidate.is_dir():
            sprite_dir = candidate

    return WorldData(
        store=store,
        passability=passability,
        palette=palette,
        tilemap_data=tilemap_data,
        world_id=world_id,
        width=width,
        height=height,
        sprite_dir=sprite_dir,
    )


def _sprite_for_kind(kind: str) -> str:
    return {
        "humanoid": "human_idle",
        "scholar": "scholar_idle",
        "guardian": "guardian_idle",
        "tree": "tree_obj",
        "rock": "rock_obj",
        "ruins": "ruins_obj",
    }.get(kind, "human_idle")
