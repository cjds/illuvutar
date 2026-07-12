import pytest
from fastapi.testclient import TestClient
from illuvutar.engine.entities.store import EntityStore
from illuvutar.engine.physics.passability import PassabilityMap
from illuvutar.engine.server.app import create_app


def _make_app(**kwargs):
    store = EntityStore()
    passability = PassabilityMap(tilemap=[["grass"] * 4 for _ in range(4)], rules={"grass": "open"})
    return create_app(store=store, passability=passability, palette={0: "void", 1: "grass"},
                      tilemap_data=[], world_id="test", width=4, height=4, **kwargs)


@pytest.fixture
def client():
    with TestClient(_make_app()) as c:
        yield c


def test_create_app_exposes_tick_loop():
    app = _make_app()
    assert hasattr(app.state, "tick_loop")


def test_root_returns_html(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_root_injects_empty_base_standalone(client):
    r = client.get("/")
    assert r.status_code == 200
    assert 'window.__BASE__ = ""' in r.text


def test_post_command_accepted(client):
    toml_cmd = '''[command]
tick_submitted = 0
agent_id = "god"
action = "set_time"
'''
    response = client.post("/command", content=toml_cmd, headers={"Content-Type": "text/plain"})
    assert response.status_code == 200


def test_entity_say_injects_whisper(client):
    """POST /entity/<id>/say returns 200 and accepts text."""
    response = client.post(
        "/entity/wanderer/say",
        json={"text": "Hello, wanderer. What do you seek?"},
    )
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_thoughts_endpoint_returns_list(client):
    """GET /thoughts returns a JSON list."""
    response = client.get("/thoughts")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_frames_endpoint_exists():
    # max_frames=1 makes the stream finite so TestClient can complete the request
    with TestClient(_make_app(max_frames=1)) as c:
        with c.stream("GET", "/frames") as r:
            assert r.status_code == 200
            assert "text/event-stream" in r.headers["content-type"]
            lines = list(r.iter_lines())
            assert any(line.startswith("data:") for line in lines)


def test_pause_resume_status(client):
    assert client.post("/pause").json() == {"paused": True}
    assert client.get("/status").json()["paused"] is True
    assert client.post("/resume").json() == {"paused": False}
    assert client.get("/status").json()["paused"] is False
