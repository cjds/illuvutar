import pytest
from illuvutar.engine.entities.components import Position, Sprite, Health, Tags, PhysicsComponent
from illuvutar.engine.entities.store import EntityStore

@pytest.fixture
def store():
    return EntityStore()

def test_create_and_get(store):
    store.create("e1", "humanoid", [Position(x=5, y=10), Sprite(sprite_name="human_idle")])
    pos = store.get_component("e1", Position)
    assert pos.x == 5

def test_entities_at(store):
    store.create("e1", "humanoid", [Position(x=3, y=4)])
    store.create("e2", "animal", [Position(x=3, y=4)])
    store.create("e3", "object", [Position(x=1, y=1)])
    at = store.entities_at(3, 4)
    assert set(at) == {"e1", "e2"}

def test_remove(store):
    store.create("e1", "humanoid", [Position(x=0, y=0)])
    store.remove("e1")
    assert store.get_component("e1", Position) is None

def test_all_ids(store):
    store.create("a", "humanoid", [])
    store.create("b", "animal", [])
    assert set(store.all_ids()) == {"a", "b"}

def test_missing_component_returns_none(store):
    store.create("e1", "object", [Position(x=0, y=0)])
    assert store.get_component("e1", Health) is None

def test_update_component(store):
    store.create("e1", "humanoid", [Position(x=0, y=0)])
    store.set_component("e1", Position(x=99, y=99))
    assert store.get_component("e1", Position).x == 99
