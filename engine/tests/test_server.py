import pytest
import asyncio
from fastapi.testclient import TestClient
from engine.entities.store import EntityStore
from engine.physics.passability import PassabilityMap
from engine.server.app import create_app


@pytest.fixture
def client():
    store = EntityStore()
    passability = PassabilityMap(tilemap=[["grass"] * 4 for _ in range(4)], rules={"grass": "open"})
    app = create_app(store=store, passability=passability, palette={0: "void", 1: "grass"},
                     tilemap_data=[], world_id="test", width=4, height=4)
    return TestClient(app)


def test_root_returns_html(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_post_command_accepted(client):
    toml_cmd = '''[command]
tick_submitted = 0
agent_id = "god"
action = "set_time"
'''
    response = client.post("/command", content=toml_cmd, headers={"Content-Type": "text/plain"})
    assert response.status_code == 200


def test_frames_endpoint_exists(client):
    # We can't easily test SSE in TestClient, but we verify the route exists
    with client.stream("GET", "/frames", timeout=5) as r:
        assert r.status_code == 200
        assert "text/event-stream" in r.headers["content-type"]
