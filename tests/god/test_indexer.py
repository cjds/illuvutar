import pytest
from pathlib import Path
from illuvutar.god.palette.indexer import index_palette, Tile


@pytest.fixture
def palette_dir(tmp_path):
    # Create fake PNG files and a meta.yaml
    (tmp_path / "grass_plain.png").write_bytes(b"PNG")
    (tmp_path / "water_deep.png").write_bytes(b"PNG")
    meta = {
        "tiles": [
            {
                "id": "grass_plain",
                "layer": "ground",
                "tags": ["grass", "walkable"],
                "adjacent": ["grass_plain", "water_deep"],
            },
            {
                "id": "water_deep",
                "layer": "ground",
                "tags": ["water", "impassable"],
                "adjacent": ["water_deep", "grass_plain"],
            },
        ]
    }
    import yaml
    (tmp_path / "palette_meta.yaml").write_text(yaml.dump(meta))
    return tmp_path


def test_index_palette_returns_tiles(palette_dir):
    tiles = index_palette(palette_dir)
    assert len(tiles) == 2
    ids = {t.id for t in tiles}
    assert ids == {"grass_plain", "water_deep"}


def test_tile_has_correct_fields(palette_dir):
    tiles = index_palette(palette_dir)
    grass = next(t for t in tiles if t.id == "grass_plain")
    assert grass.layer == "ground"
    assert "walkable" in grass.tags
    assert "grass_plain" in grass.adjacent
    assert grass.sprite_path.endswith("grass_plain.png")


def test_index_palette_requires_matching_png(palette_dir, tmp_path):
    # Tile in meta but no png → raises
    import yaml
    bad_dir = tmp_path / "bad"
    bad_dir.mkdir()
    (bad_dir / "palette_meta.yaml").write_text(yaml.dump({
        "tiles": [{"id": "ghost_tile", "layer": "ground", "tags": [], "adjacent": []}]
    }))
    with pytest.raises(FileNotFoundError):
        index_palette(bad_dir)
