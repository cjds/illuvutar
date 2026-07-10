"""Tests for world state writer and reader."""
import yaml
import json
from pathlib import Path
from illuvutar.world_state.writer import WorldStateWriter
from illuvutar.world_state.schema import Constitution


def test_write_creates_yaml_file(tmp_path):
    writer = WorldStateWriter(tmp_path)
    c = Constitution("TestWorld", "palette_v1", 32, 32, "test", [])
    writer.write("constitution", c.to_dict())
    assert (tmp_path / "constitution.yaml").exists()


def test_read_round_trips(tmp_path):
    writer = WorldStateWriter(tmp_path)
    c = Constitution("TestWorld", "palette_v1", 32, 32, "dark", ["rule1"])
    writer.write("constitution", c.to_dict())
    loaded = writer.read("constitution")
    assert loaded["world_name"] == "TestWorld"


def test_write_tilemap_as_json(tmp_path):
    writer = WorldStateWriter(tmp_path)
    tilemap = [{"x": 0, "y": 0, "tile_id": "grass_plain", "region": 0}]
    writer.write("tilemap", tilemap)
    assert (tmp_path / "tilemap.json").exists()


def test_status_tracks_completion(tmp_path):
    writer = WorldStateWriter(tmp_path)
    status = writer.status()
    assert status["constitution"] is False
    writer.write("constitution", {"world_name": "X", "palette_used": "p", "width": 32, "height": 32, "tone": "t", "rules": []})
    assert writer.status()["constitution"] is True
