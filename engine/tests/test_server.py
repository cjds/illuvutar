import pytest
from fastapi.testclient import TestClient
from engine.entities.store import EntityStore
from engine.physics.passability import PassabilityMap
from engine.server.app import create_app


def _make_app(**kwargs):
    store = EntityStore()
    passability = PassabilityMap(tilemap=[["grass"] * 4 for _ in range(4)], rules={"grass": "open"})
    return create_app(store=store, passability=passability, palette={0: "void", 1: "grass"},
                      tilemap_data=[], world_id="test", width=4, height=4, **kwargs)


@pytest.fixture
def client():
    with TestClient(_make_app()) as c:
        yield c


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


def test_frames_endpoint_exists():
    # max_frames=1 makes the stream finite so TestClient can complete the request
    with TestClient(_make_app(max_frames=1)) as c:
        with c.stream("GET", "/frames") as r:
            assert r.status_code == 200
            assert "text/event-stream" in r.headers["content-type"]
            lines = list(r.iter_lines())
            assert any(line.startswith("data:") for line in lines)
