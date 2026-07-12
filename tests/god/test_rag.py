import pytest
from illuvutar.god.palette.indexer import Tile
from illuvutar.god.palette.rag import PaletteRAG

@pytest.fixture
def sample_tiles():
    return [
        Tile("grass_plain", "/p/grass_plain.png", "ground", ["grass", "walkable"], ["grass_plain"]),
        Tile("water_shallow", "/p/water_shallow.png", "ground", ["water", "walkable"], ["water_deep"]),
        Tile("water_deep", "/p/water_deep.png", "ground", ["water", "impassable"], ["water_shallow"]),
        Tile("wall_stone", "/p/wall_stone.png", "object", ["wall", "impassable"], ["wall_stone"]),
    ]

def test_query_returns_water_tiles(sample_tiles, tmp_path):
    rag = PaletteRAG.build(sample_tiles, persist_dir=str(tmp_path))
    results = rag.query("shallow water edge for rivers", n=2)
    ids = [t.id for t in results]
    assert "water_shallow" in ids

def test_query_returns_at_most_n(sample_tiles, tmp_path):
    rag = PaletteRAG.build(sample_tiles, persist_dir=str(tmp_path))
    results = rag.query("any tile", n=2)
    assert len(results) <= 2

def test_query_returns_tiles_not_strings(sample_tiles, tmp_path):
    rag = PaletteRAG.build(sample_tiles, persist_dir=str(tmp_path))
    results = rag.query("grass", n=1)
    assert isinstance(results[0], Tile)
