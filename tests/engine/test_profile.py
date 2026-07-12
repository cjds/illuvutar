from fastapi.testclient import TestClient
from illuvutar.engine.entities.store import EntityStore
from illuvutar.engine.entities.components import (
    Position, Label, AIComponent, Tags, PhysicsComponent, Mind, Profile
)
from illuvutar.engine.physics.passability import PassabilityMap
from illuvutar.engine.server.app import create_app


def _client():
    store = EntityStore()
    store.create("smith", "humanoid", [
        Position(2, 2), Label("Bram"),
        AIComponent(agent_id="smith", goal="forge iron"),
        Tags(["agent"]), PhysicsComponent(),
        Mind(memory="hot work today", facts="I am proud of my craft"),
        Profile(roles=["Blacksmith"], backstory="Took the forge after the fever winter."),
    ])
    passability = PassabilityMap(tilemap=[["g"] * 4 for _ in range(4)], rules={"g": "open"})
    app = create_app(store=store, passability=passability, palette={0: "g"},
                     tilemap_data=[], world_id="w", width=4, height=4)
    return TestClient(app)


def test_profile_returns_full_shape():
    r = _client().get("/entity/smith/profile")
    assert r.status_code == 200
    body = r.json()
    assert body == {
        "id": "smith", "name": "Bram", "roles": ["Blacksmith"], "job": "Blacksmith",
        "backstory": "Took the forge after the fever winter.",
        "facts": "I am proud of my craft", "goal": "forge iron",
    }


def test_profile_unknown_entity_404():
    assert _client().get("/entity/nobody/profile").status_code == 404
