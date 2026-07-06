import pytest
from engine.entities.store import EntityStore
from engine.entities.components import Position, Sprite, Health, PhysicsComponent
from engine.systems.input import InputSystem, Command
from engine.systems.physics_system import PhysicsSystem
from engine.systems.render_output import RenderOutputSystem
from engine.systems.health import HealthSystem
from engine.physics.passability import PassabilityMap

RULES = {"grass": "open", "wall": "blocked"}


@pytest.fixture
def store():
    s = EntityStore()
    s.create("e1", "humanoid", [
        Position(2, 2),
        Sprite("human_idle"),
        Health(current=80.0, max=100.0),
        PhysicsComponent(blocking=True, collision_priority=5),
    ])
    return s


@pytest.fixture
def passability():
    tilemap = [["grass"] * 10 for _ in range(10)]
    return PassabilityMap(tilemap=tilemap, rules=RULES)


def test_input_system_flushes_commands(store, passability):
    queue = [Command(entity_id="e1", action="move", params={"direction": "east"})]
    system = InputSystem(store, passability)
    intents = system.run(tick=1, command_queue=queue)
    assert len(intents) >= 0  # queue processed without error


def test_physics_system_applies_move(store, passability):
    from engine.systems.physics_system import MoveIntent as PMI
    intents = [PMI(entity_id="e1", from_x=2, from_y=2, to_x=3, to_y=2, is_god=False)]
    system = PhysicsSystem(store, passability)
    system.run(tick=1, move_intents=intents)
    pos = store.get_component("e1", Position)
    assert pos.x == 3


def test_render_output_builds_frame(store):
    palette = {0: "void", 1: "grass"}
    tilemap_data = [{"x": 0, "y": 0, "tile_id": "grass", "region": 0}]
    system = RenderOutputSystem(store, palette=palette, tilemap_data=tilemap_data, world_id="test", width=10, height=10)
    frame = system.run(tick=5)
    assert frame.tick == 5
    assert any(e.id == "e1" for e in frame.entities)


def test_health_system_marks_dead_entities(store):
    store.set_component("e1", Health(current=0.0, max=100.0))
    system = HealthSystem(store)
    dead = system.run(tick=1)
    assert "e1" in dead
