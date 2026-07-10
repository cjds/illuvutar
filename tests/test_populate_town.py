import json
from unittest.mock import patch, MagicMock
from pathlib import Path
from illuvutar.world_state.writer import WorldStateWriter
from illuvutar.palette.indexer import Tile
from illuvutar.agents.tools import AgentTools


def _tools(tmp_path):
    writer = WorldStateWriter(tmp_path)
    tiles = [
        Tile(id="grass_plain", sprite_path="", layer="ground", tags=["walkable"], adjacent=[]),
        Tile(id="water_shallow", sprite_path="", layer="ground", tags=["wading"], adjacent=[]),
    ]
    return AgentTools(writer=writer, rag=MagicMock(), tiles=tiles,
                      palette_dir=Path(tmp_path), model="m"), writer


def test_populate_town_requires_tilemap(tmp_path):
    tools, _ = _tools(tmp_path)
    out = tools.populate_town()
    assert "tilemap" in out.lower() or "wfc" in out.lower()


def test_populate_town_writes_agents_with_job_and_backstory(tmp_path):
    tools, writer = _tools(tmp_path)
    writer.write("regions", {"regions": [{"id": 0, "name": "Plains", "biome": "grassland"}]})
    writer.write("tilemap", [{"x": x, "y": 0, "tile_id": "grass_plain", "region": 0} for x in range(20)])
    with patch("illuvutar.generation.populace.ollama") as mo:
        m = MagicMock(); m.message.content = json.dumps(
            {"name": "Bram", "backstory": "A life of iron.", "goal": "forge", "facts": "I forge."})
        mo.chat.return_value = m
        out = tools.populate_town(count=5)
    agents = writer.read("agents")
    assert len(agents) == 5
    assert all("job" in a and "backstory" in a for a in agents)
    assert "5" in out
