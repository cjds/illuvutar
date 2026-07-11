from fastapi.testclient import TestClient
from studio.app import create_studio_app


def test_shell_served(fake_session):
    c = TestClient(create_studio_app(fake_session))
    r = c.get("/")
    assert r.status_code == 200 and "Forge" in r.text


def test_forge_status(fake_session):
    c = TestClient(create_studio_app(fake_session))
    r = c.get("/forge/status")
    assert r.status_code == 200
    assert r.json() == {"constitution": True, "tilemap": False}


def test_forge_message_triggers_turn(fake_session, monkeypatch):
    import asyncio
    async def ok(text): return True
    fake_session.run_turn = ok
    c = TestClient(create_studio_app(fake_session))
    assert c.post("/forge/message", json={"text": "build"}).status_code == 200
    assert c.post("/forge/message", json={"text": ""}).status_code == 400
