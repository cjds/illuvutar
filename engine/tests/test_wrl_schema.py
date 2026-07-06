"""Tests for the WRL schema dataclasses."""
from engine.wrl.schema import (
    WRLFrame,
    WRLTileLayer,
    WRLEntity,
    WRLEffectLayer,
    WRLUILayer,
    WRLLight,
)


def test_frame_has_required_fields():
    frame = WRLFrame(tick=1, world_id="test", timestamp_ms=100)
    assert frame.tick == 1
    assert frame.world_id == "test"
    assert frame.kind == "full"


def test_tile_layer_defaults():
    layer = WRLTileLayer(width=64, height=64, rows=[])
    assert layer.width == 64
    assert layer.rows == []


def test_entity_defaults():
    e = WRLEntity(id="e1", kind="humanoid", x=5, y=10, sprite="human_idle", health=1.0)
    assert e.label == ""
    assert e.carrying == "none"
    assert e.footprint is None


def test_light_fields():
    light = WRLLight(
        kind="point", x=10, y=10, radius_tiles=3.0, color="#fff", intensity=0.9, source="e1"
    )
    assert light.kind == "point"


def test_frame_kind_default():
    f = WRLFrame(tick=0, world_id="x", timestamp_ms=0)
    assert f.kind == "full"
