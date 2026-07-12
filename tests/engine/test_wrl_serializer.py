from illuvutar.engine.wrl.schema import WRLFrame, WRLTileLayer, WRLEntity, WRLEffectLayer, WRLLight
from illuvutar.engine.wrl.serializer import serialize


def _minimal_frame():
    return WRLFrame(tick=1, world_id="test-world", timestamp_ms=100)


def test_serialize_contains_frame_header():
    out = serialize(_minimal_frame())
    assert "[frame]" in out
    assert "tick = 1" in out
    assert 'world_id = "test-world"' in out


def test_serialize_includes_tile_layer():
    frame = _minimal_frame()
    frame.tiles = WRLTileLayer(width=4, height=2, rows=["0-3:1", "0-3:1"])
    out = serialize(frame)
    assert "[[layer.tiles]]" in out
    assert "width = 4" in out


def test_serialize_includes_entity():
    frame = _minimal_frame()
    frame.entities = [WRLEntity(id="e1", kind="humanoid", x=5, y=3, sprite="human_idle")]
    out = serialize(frame)
    assert '[[layer.entities.entity]]' in out
    assert 'id = "e1"' in out


def test_serialize_includes_palette():
    frame = _minimal_frame()
    frame.palette = {0: "void", 1: "grass_plain"}
    out = serialize(frame)
    assert "[palette]" in out
    assert '0 = "void"' in out


def test_serialize_includes_ambient_light():
    frame = _minimal_frame()
    frame.effects.lights = [WRLLight(kind="ambient", color="#aaa", intensity=0.5)]
    out = serialize(frame)
    assert "[[layer.effects.light]]" in out
    assert 'kind = "ambient"' in out
