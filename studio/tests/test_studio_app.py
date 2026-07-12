import pytest
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


def test_sim_start_needs_tilemap(tmp_path, fake_session):
    c = TestClient(create_studio_app(fake_session, world_dir=tmp_path))
    r = c.post("/sim/start")
    assert r.status_code == 200 and r.json()["ready"] is False
    assert "tilemap" in r.json()["missing"]


@pytest.mark.asyncio
async def test_sim_start_is_idempotent(tmp_path, monkeypatch):
    from unittest.mock import MagicMock, AsyncMock
    import studio.sim as sim_mod
    # required world files present so missing() is empty
    (tmp_path / "constitution.yaml").write_text("world_name: t")
    (tmp_path / "palette.yaml").write_text("tiles: []")
    (tmp_path / "tilemap.json").write_text("[]")

    calls = []
    def fake_create_app(**kw):
        app = MagicMock()
        app.state.tick_loop.start = AsyncMock()
        calls.append(app)
        return app
    monkeypatch.setattr(sim_mod, "load_world", lambda wd: MagicMock())
    monkeypatch.setattr(sim_mod, "create_app", fake_create_app)

    holder = sim_mod.SimHolder(tmp_path)
    assert holder.start() is True
    assert holder.start() is True          # second Play
    assert len(calls) == 1                 # built once, no second (leaked) loop


@pytest.mark.asyncio
async def test_sim_reload_rebuilds_and_stops_old(tmp_path, monkeypatch):
    from unittest.mock import MagicMock, AsyncMock
    import studio.sim as sim_mod
    (tmp_path / "constitution.yaml").write_text("world_name: t")
    (tmp_path / "palette.yaml").write_text("tiles: []")
    (tmp_path / "tilemap.json").write_text("[]")
    built = []
    def fake_create_app(**kw):
        app = MagicMock(); app.state.tick_loop.start = AsyncMock(); built.append(app); return app
    monkeypatch.setattr(sim_mod, "load_world", lambda wd: MagicMock())
    monkeypatch.setattr(sim_mod, "create_app", fake_create_app)
    holder = sim_mod.SimHolder(tmp_path)
    assert holder.start() is True
    first = built[0]
    assert holder.reload() is True
    assert len(built) == 2                       # rebuilt
    first.state.tick_loop.stop.assert_called_once()   # old loop stopped


def test_sim_reload_needs_tilemap(tmp_path, fake_session):
    from studio.app import create_studio_app
    c = TestClient(create_studio_app(fake_session, world_dir=tmp_path))
    r = c.post("/sim/reload")
    assert r.status_code == 200 and r.json()["ready"] is False
