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


from engine.entities.components import Mind, AIComponent
from engine.entities.persistence import save_entity_state


def _add_agent(world_dir, agent):
    import yaml
    (world_dir / "agents.yaml").write_text(yaml.dump([agent]))


def test_entity_gets_mind_with_default_limits(world_dir):
    data = load_world(world_dir)
    mind = data.store.get_component("e1", Mind)
    assert mind is not None
    assert mind.memory_word_limit == 60
    assert mind.facts_word_limit == 30


def test_facts_seed_string(world_dir):
    _add_agent(world_dir, {"id": "e1", "kind": "humanoid", "x": 1, "y": 1,
                           "name": "Alice", "behavior": "wander",
                           "facts": "I am cautious"})
    data = load_world(world_dir)
    assert data.store.get_component("e1", Mind).facts == "I am cautious"


def test_facts_seed_list_joined(world_dir):
    _add_agent(world_dir, {"id": "e1", "kind": "humanoid", "x": 1, "y": 1,
                           "name": "Alice", "behavior": "wander",
                           "facts": ["I am cautious", "I distrust strangers"]})
    data = load_world(world_dir)
    facts = data.store.get_component("e1", Mind).facts
    assert "cautious" in facts and "distrust" in facts


def test_persisted_state_overlays_seed(world_dir):
    _add_agent(world_dir, {"id": "e1", "kind": "humanoid", "x": 1, "y": 1,
                           "name": "Alice", "behavior": "wander",
                           "facts": "seed fact"})
    save_entity_state(world_dir, "e1", "evolved goal",
                      Mind(memory="I recall the storm", facts="evolved fact"))
    data = load_world(world_dir)
    mind = data.store.get_component("e1", Mind)
    ai = data.store.get_component("e1", AIComponent)
    assert mind.memory == "I recall the storm"
    assert mind.facts == "evolved fact"
    assert ai.goal == "evolved goal"


def test_cli_limit_overrides_constitution_and_truncates_overlay(world_dir):
    import yaml
    const = yaml.safe_load((world_dir / "constitution.yaml").read_text())
    const["memory_word_limit"] = 40
    (world_dir / "constitution.yaml").write_text(yaml.dump(const))
    save_entity_state(world_dir, "e1", "wander",
                      Mind(memory="alpha beta gamma delta", facts=""))
    data = load_world(world_dir, memory_word_limit=2)  # CLI wins over constitution's 40
    mind = data.store.get_component("e1", Mind)
    assert mind.memory_word_limit == 2
    assert mind.memory == "alpha beta"  # overlay re-truncated to CLI limit


def test_constitution_limit_used_when_no_cli(world_dir):
    import yaml
    const = yaml.safe_load((world_dir / "constitution.yaml").read_text())
    const["facts_word_limit"] = 7
    (world_dir / "constitution.yaml").write_text(yaml.dump(const))
    data = load_world(world_dir)
    assert data.store.get_component("e1", Mind).facts_word_limit == 7


from engine.entities.components import Profile


def test_entity_gets_empty_profile_by_default(world_dir):
    data = load_world(world_dir)
    prof = data.store.get_component("e1", Profile)
    assert prof is not None
    assert prof.job == "" and prof.backstory == ""


def test_profile_loaded_from_agents_yaml(world_dir):
    import yaml
    (world_dir / "agents.yaml").write_text(yaml.dump([
        {"id": "e1", "kind": "humanoid", "x": 1, "y": 1, "name": "Bram",
         "behavior": "forge", "job": "Blacksmith",
         "backstory": "Took the forge after the fever winter."},
    ]))
    data = load_world(world_dir)
    prof = data.store.get_component("e1", Profile)
    assert prof.job == "Blacksmith"
    assert "fever winter" in prof.backstory
