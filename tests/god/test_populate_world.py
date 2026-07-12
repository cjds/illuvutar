import json
from unittest.mock import patch, MagicMock
from pathlib import Path
from illuvutar.god.world_state.writer import WorldStateWriter
from illuvutar.god.palette.indexer import Tile
from illuvutar.god.agents.tools import AgentTools


def _tools(tmp_path, entries=None):
    client = MagicMock()
    client.complete.return_value = json.dumps(entries or [
        {"name": "Vela", "extra_roles": [], "backstory": "b", "goal": "g", "facts": "f"}
        for _ in range(12)])
    tiles = [Tile(id="grass_plain", sprite_path="", layer="ground", tags=["walkable"], adjacent=[])]
    tools = AgentTools(writer=WorldStateWriter(tmp_path), rag=MagicMock(), tiles=tiles,
                       palette_dir=Path(tmp_path), client=client)
    return tools, WorldStateWriter(tmp_path)


def _seed(writer):
    writer.write("regions", {"regions": [{"name": "Plains", "biome": "grassland"}]})
    writer.write("tilemap", [{"x": x, "y": 0, "tile_id": "grass_plain", "region": 0} for x in range(20)])
    writer.write("roles", {"roles": [
        {"id": "farmer", "title": "Farmer", "locale": "Plains", "blurb": "works the fields"}]})


def test_requires_tilemap(tmp_path):
    tools, _ = _tools(tmp_path)
    assert "tilemap" in tools.populate_world().lower()


def test_requires_roles(tmp_path):
    tools, writer = _tools(tmp_path)
    writer.write("tilemap", [{"x": 0, "y": 0, "tile_id": "grass_plain", "region": 0}])
    assert "roles" in tools.populate_world().lower()


def test_writes_agents_with_roles_list(tmp_path):
    tools, writer = _tools(tmp_path)
    _seed(writer)
    out = tools.populate_world(count=5)
    agents = writer.read("agents")
    assert len(agents) == 5
    assert all(isinstance(a["roles"], list) and "backstory" in a for a in agents)
    assert "5" in out


def test_string_count_does_not_crash(tmp_path):
    tools, writer = _tools(tmp_path)
    _seed(writer)
    out = tools.populate_world(count="5")
    assert "error" not in out.lower()
    assert len(writer.read("agents")) == 5
