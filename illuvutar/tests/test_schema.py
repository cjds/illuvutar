"""Tests for world state schema dataclasses."""
from illuvutar.world_state.schema import Constitution, Region, RegionMap


def test_constitution_serializes():
    c = Constitution(
        world_name="Ashenveil",
        palette_used="forest_ruins_v1",
        width=64, height=64,
        tone="melancholic ancient world",
        rules=["no magic", "survival focus"],
    )
    d = c.to_dict()
    assert d["world_name"] == "Ashenveil"
    assert d["width"] == 64


def test_region_map_serializes():
    r = Region(id=0, name="The Ashwood", biome="forest", centroid_x=10, centroid_y=10, atmosphere="dense fog")
    rm = RegionMap(regions=[r])
    d = rm.to_dict()
    assert d["regions"][0]["name"] == "The Ashwood"
