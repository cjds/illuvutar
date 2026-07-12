from unittest.mock import MagicMock
from illuvutar.god.generation.populace import generate_populace

_ROLES = [
    {"id": "ash-scavenger", "title": "Ash-scavenger", "locale": "The Dunes", "blurb": "sifts the drifts"},
    {"id": "water-priest", "title": "Water-priest", "locale": "The Cistern", "blurb": "rations the water"},
]

def _tilemap():
    cells = []
    for y in range(6):
        for x in range(6):
            reg = 0 if y < 3 else 1          # region 0 = top, region 1 = bottom
            tid = "sand" if y < 3 else "stone"
            cells.append({"x": x, "y": y, "tile_id": tid, "region": reg})
    return cells

_REGIONS = [{"name": "The Dunes", "biome": "desert"}, {"name": "The Cistern", "biome": "water"}]
_WALKABLE = {"sand", "stone"}


def _client(entries):
    """A client whose .complete returns a JSON array of `entries` per call."""
    import json
    c = MagicMock()
    c.complete.return_value = json.dumps(entries)
    return c


def _entry(name="Vela", extra=None):
    return {"name": name, "extra_roles": extra or [], "backstory": "A short life.",
            "goal": "endure", "facts": "I am."}


def test_generates_exactly_count_with_roles():
    c = _client([_entry(name=f"P{i}") for i in range(12)])
    people = generate_populace(_ROLES, _tilemap(), _REGIONS, _WALKABLE, c, count=5)
    assert len(people) == 5
    for p in people:
        assert p["name"] and p["backstory"] and p["facts"]
        assert isinstance(p["roles"], list) and 1 <= len(p["roles"]) <= 3
        assert p["roles"][0] in {"ash-scavenger", "water-priest"}
    assert len({p["id"] for p in people}) == 5          # unique ids


def test_multiple_roles_preserved():
    c = _client([_entry(name="Vela", extra=["water-priest"])])   # primary ash-scavenger + extra
    people = generate_populace(_ROLES, _tilemap(), _REGIONS, _WALKABLE, c, count=1)
    assert set(people[0]["roles"]) == {"ash-scavenger", "water-priest"}


def test_placement_matches_role_locale():
    # ash-scavenger's locale "The Dunes" = region 0 = rows y<3
    c = _client([_entry()])
    people = generate_populace(_ROLES[:1], _tilemap(), _REGIONS, _WALKABLE, c, count=1)
    assert people[0]["y"] < 3


def test_llm_failure_falls_back_and_returns_all():
    c = MagicMock(); c.complete.side_effect = RuntimeError("down")
    people = generate_populace(_ROLES, _tilemap(), _REGIONS, _WALKABLE, c, count=6)
    assert len(people) == 6
    for p in people:
        assert p["name"] and p["backstory"] and p["roles"]


def test_string_count_and_over_range_handled():
    c = _client([_entry() for _ in range(12)])
    people = generate_populace(_ROLES, _tilemap(), _REGIONS, _WALKABLE, c, count="4")
    assert len(people) == 4


def test_malformed_roles_never_raise():
    from unittest.mock import MagicMock
    c = MagicMock(); c.complete.return_value = "not json"
    bad = [{"title": "No Id"}, 5, {"id": "ok", "title": "Ok", "locale": "", "blurb": "b"}]
    people = generate_populace(bad, _tilemap(), _REGIONS, _WALKABLE, c, count=4)
    assert len(people) == 4
    assert all(p["roles"] and p["name"] for p in people)
