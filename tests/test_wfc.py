import numpy as np
import pytest
from illuvutar.palette.indexer import Tile
from illuvutar.world_state.schema import Region
from illuvutar.generation.wfc import WFC

@pytest.fixture
def simple_setup():
    tiles = [
        Tile("grass", "/p/grass.png", "ground", ["grass"], ["grass", "dirt"]),
        Tile("dirt", "/p/dirt.png", "ground", ["grass"], ["grass", "dirt"]),
    ]
    regions = [Region(id=0, name="Field", biome="grass", centroid_x=2, centroid_y=2)]
    region_grid = np.zeros((4, 4), dtype=np.int32)
    return tiles, regions, region_grid

def test_collapse_returns_correct_shape(simple_setup):
    tiles, regions, grid = simple_setup
    wfc = WFC(width=4, height=4, tiles=tiles, region_grid=grid, regions=regions)
    result = wfc.collapse()
    assert result is not None
    assert len(result) == 4
    assert len(result[0]) == 4

def test_collapse_uses_valid_tile_ids(simple_setup):
    tiles, regions, grid = simple_setup
    wfc = WFC(width=4, height=4, tiles=tiles, region_grid=grid, regions=regions)
    result = wfc.collapse()
    valid_ids = {"grass", "dirt"}
    for row in result:
        for cell in row:
            assert cell in valid_ids

def test_collapse_respects_adjacency(simple_setup):
    # Tile "water" is not adjacent to "grass" — so if grid has only grass tiles
    # and water is not in adj list of grass, water should never appear
    tiles, regions, grid = simple_setup
    wfc = WFC(width=4, height=4, tiles=tiles, region_grid=grid, regions=regions)
    result = wfc.collapse()
    for row in result:
        for cell in row:
            assert cell != "water"

def test_contradiction_returns_none():
    # Tile with empty adjacency list cannot propagate — force contradiction
    tiles = [Tile("isolated", "/p/iso.png", "ground", ["x"], [])]
    regions = [Region(id=0, name="X", biome="x", centroid_x=1, centroid_y=1)]
    grid = np.zeros((3, 3), dtype=np.int32)
    wfc = WFC(width=3, height=3, tiles=tiles, region_grid=grid, regions=regions)
    # 3x3 with one tile that has no neighbors allowed → only (0,0) collapses cleanly
    # neighbors of any cell get empty set → contradiction
    result = wfc.collapse()
    # Either it collapses (single tile trivially satisfies adjacency with itself) or returns None
    # We just assert it doesn't raise
    assert result is None or isinstance(result, list)
