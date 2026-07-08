import pytest
import json
import yaml
from pathlib import Path
from engine.loader import load_world, WorldData

@pytest.fixture
def world_dir(tmp_path):
    """Minimal world-state directory for testing."""
    # constitution.yaml
    (tmp_path / "constitution.yaml").write_text(yaml.dump({
        "world_name": "test_world",
        "palette_used": str(tmp_path / "palette"),
        "width": 4, "height": 4,
        "tone": "test", "rules": [],
    }))
    # palette.yaml — same format as worldstatewriter writes it
    (tmp_path / "palette.yaml").write_text(yaml.dump({
        "tiles": [
            {"id": "grass", "layer": "ground", "tags": ["walkable"], "adjacent": ["grass"]},
            {"id": "wall",  "layer": "ground", "tags": ["blocked"], "adjacent": ["wall"]},
        ]
    }))
    # tilemap.json
    cells = [{"x": x, "y": y, "tile_id": "grass", "region": 0}
             for y in range(4) for x in range(4)]
    (tmp_path / "tilemap.json").write_text(json.dumps(cells))
    # agents.yaml
    (tmp_path / "agents.yaml").write_text(yaml.dump([
        {"id": "e1", "kind": "humanoid", "x": 1, "y": 1,
         "name": "Alice", "behavior": "wander_passive"},
    ]))
    return tmp_path

def test_load_world_returns_world_data(world_dir):
    data = load_world(world_dir)
    assert isinstance(data, WorldData)
    assert data.world_id == "test_world"
    assert data.width == 4
    assert data.height == 4

def test_load_world_builds_palette(world_dir):
    data = load_world(world_dir)
    # palette is dict[int, str] — index→tile_id
    assert isinstance(data.palette, dict)
    assert 0 in data.palette or 1 in data.palette
    tile_ids = set(data.palette.values())
    assert "grass" in tile_ids

def test_load_world_builds_passability(world_dir):
    from engine.physics.passability import PassabilityMap
    data = load_world(world_dir)
    assert isinstance(data.passability, PassabilityMap)
    # grass is walkable → open
    assert data.passability.can_enter("player", 0, 0, data.store)

def test_load_world_populates_entities(world_dir):
    data = load_world(world_dir)
    ids = list(data.store.all_ids())
    assert "e1" in ids

def test_load_world_tilemap_data(world_dir):
    data = load_world(world_dir)
    assert len(data.tilemap_data) == 16  # 4x4
    assert data.tilemap_data[0]["tile_id"] == "grass"
