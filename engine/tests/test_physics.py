import pytest
from engine.entities.store import EntityStore
from engine.entities.components import Position, PhysicsComponent, Tags
from engine.physics.passability import PassabilityMap
from engine.physics.collision import MoveIntent, resolve_conflicts
from engine.physics.adjacency import get_adjacent_entities

PASS_RULES = {"grass": "open", "wall_stone": "blocked", "water_shallow": "slow", "door": "conditional"}

@pytest.fixture
def simple_map():
    tilemap = [["grass"] * 10 for _ in range(10)]
    tilemap[3][3] = "wall_stone"
    return PassabilityMap(tilemap=tilemap, rules=PASS_RULES)

@pytest.fixture
def store():
    s = EntityStore()
    s.create("p1", "humanoid", [Position(0, 0), PhysicsComponent(blocking=True, collision_priority=10)])
    s.create("p2", "animal", [Position(5, 5), PhysicsComponent(blocking=True, collision_priority=1)])
    return s

def test_open_tile_passable(simple_map, store):
    assert simple_map.can_enter("p1", 2, 2, store) is True

def test_blocked_tile_impassable(simple_map, store):
    assert simple_map.can_enter("p1", 3, 3, store) is False

def test_god_bypasses_blocking(simple_map, store):
    assert simple_map.can_enter("god", 3, 3, store) is True

def test_resolve_single_move_succeeds(simple_map, store):
    intents = [MoveIntent("p1", 0, 0, 1, 0, is_god=False)]
    results = resolve_conflicts(intents, store, simple_map)
    assert results["p1"] is True

def test_resolve_conflict_higher_priority_wins(simple_map, store):
    intents = [
        MoveIntent("p1", 0, 0, 2, 2, is_god=False),
        MoveIntent("p2", 5, 5, 2, 2, is_god=False),
    ]
    results = resolve_conflicts(intents, store, simple_map)
    assert results["p1"] is True   # p1 has priority 10
    assert results["p2"] is False  # p2 has priority 1

def test_adjacent_entities(store):
    store.create("near", "object", [Position(1, 0)])
    store.create("far", "object", [Position(9, 9)])
    adj = get_adjacent_entities("p1", store, radius=1)
    assert "near" in adj
    assert "far" not in adj
    assert "p1" not in adj
