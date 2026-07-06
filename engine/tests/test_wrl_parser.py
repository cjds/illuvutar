from engine.wrl.schema import WRLFrame
from engine.wrl.serializer import serialize
from engine.wrl.parser import parse
from engine.wrl.schema import WRLTileLayer, WRLEntity, WRLLight


def _roundtrip(frame: WRLFrame) -> WRLFrame:
    return parse(serialize(frame))


def test_parse_roundtrip_tick():
    f = WRLFrame(tick=42, world_id="rp-world", timestamp_ms=4200)
    assert _roundtrip(f).tick == 42


def test_parse_roundtrip_world_id():
    f = WRLFrame(tick=1, world_id="my-world", timestamp_ms=100)
    assert _roundtrip(f).world_id == "my-world"


def test_parse_roundtrip_palette():
    f = WRLFrame(tick=1, world_id="x", timestamp_ms=100, palette={1: "grass", 2: "water"})
    rt = _roundtrip(f)
    assert rt.palette[1] == "grass"


def test_parse_roundtrip_entity():
    f = WRLFrame(tick=1, world_id="x", timestamp_ms=100)
    f.entities = [WRLEntity(id="e99", kind="animal", x=3, y=7, sprite="deer_idle")]
    rt = _roundtrip(f)
    assert rt.entities[0].id == "e99"
    assert rt.entities[0].x == 3


def test_parse_roundtrip_tiles():
    f = WRLFrame(tick=1, world_id="x", timestamp_ms=100)
    f.tiles = WRLTileLayer(width=4, height=2, rows=["0-3:1", "0-3:2"])
    rt = _roundtrip(f)
    assert rt.tiles.width == 4
    assert rt.tiles.rows[0] == "0-3:1"
