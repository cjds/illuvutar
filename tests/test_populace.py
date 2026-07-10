import json
from unittest.mock import patch, MagicMock
from illuvutar.generation.jobs import JOBS
from illuvutar.generation.populace import generate_populace

# 6x6 map: region 0 grassland everywhere except a forest strip (region 1) and water (region 2)
def _tilemap():
    cells = []
    for y in range(6):
        for x in range(6):
            if y == 0:
                tid, reg = "forest_floor", 1
            elif y == 5:
                tid, reg = "water_shallow", 2
            else:
                tid, reg = "grass_plain", 0
            cells.append({"x": x, "y": y, "tile_id": tid, "region": reg})
    return cells

_REGIONS = [
    {"id": 0, "name": "Plains", "biome": "grassland"},
    {"id": 1, "name": "Wood", "biome": "forest"},
    {"id": 2, "name": "Lake", "biome": "water"},
]
_WALKABLE = {"grass_plain", "forest_floor"}  # water excluded


def _mock_ok(name="Bram", story="A short life story.", goal="work", facts="I am proud."):
    m = MagicMock()
    m.message.content = json.dumps({"name": name, "backstory": story, "goal": goal, "facts": facts})
    return m


def test_generates_one_valid_npc_per_job():
    jobs = JOBS[:5]
    with patch("illuvutar.generation.populace.ollama") as mo:
        mo.chat.return_value = _mock_ok()
        people = generate_populace(jobs, _tilemap(), _REGIONS, _WALKABLE, model="m")
    assert len(people) == len(jobs)
    for p in people:
        assert p["name"] and p["backstory"] and p["job"] and p["behavior"] and p["facts"]
    ids = [p["id"] for p in people]
    assert len(set(ids)) == len(ids)
    positions = [(p["x"], p["y"]) for p in people]
    assert len(set(positions)) == len(positions)


def test_positions_are_walkable_and_never_on_water():
    with patch("illuvutar.generation.populace.ollama") as mo:
        mo.chat.return_value = _mock_ok()
        people = generate_populace(JOBS, _tilemap(), _REGIONS, _WALKABLE, model="m")
    tile_at = {(c["x"], c["y"]): c["tile_id"] for c in _tilemap()}
    for p in people:
        assert tile_at[(p["x"], p["y"])] in _WALKABLE


def test_llm_failure_falls_back_and_still_returns_all():
    with patch("illuvutar.generation.populace.ollama") as mo:
        mo.chat.side_effect = RuntimeError("ollama down")
        people = generate_populace(JOBS[:8], _tilemap(), _REGIONS, _WALKABLE, model="m")
    assert len(people) == 8
    for p in people:                       # fallback still fills every field
        assert p["name"] and p["backstory"] and p["facts"]


def test_backstory_truncated_to_word_limit():
    long_story = " ".join(["word"] * 200)
    with patch("illuvutar.generation.populace.ollama") as mo:
        mo.chat.return_value = _mock_ok(story=long_story)
        people = generate_populace(JOBS[:1], _tilemap(), _REGIONS, _WALKABLE, model="m", backstory_word_limit=12)
    assert len(people[0]["backstory"].split()) == 12


def test_biome_placement_uses_positional_index_not_declared_id():
    # Region list order = positional index used by the tilemap (per _tilemap(): index 0
    # is grassland/y1-4, index 1 is the forest strip/y==0, index 2 is water/y==5), but
    # declared ids are scrambled / missing. Forest is at positional index 1.
    regions = [
        {"id": 7, "name": "Plains", "biome": "grassland"},  # index 0 -> tilemap region 0 (grass_plain, y 1-4)
        {"id": 99, "name": "Wood", "biome": "forest"},      # index 1 -> tilemap region 1 (forest strip, y==0)
        {"name": "Lake", "biome": "water"},                 # index 2, no id key -> tilemap region 2 (water, y==5)
    ]
    # Place 6 grassland jobs first so that, under the buggy declared-id matching (where
    # NO declared id ever equals an actual tilemap region 0/1/2), every job falls back to
    # "any walkable cell" in iteration order — which exhausts the forest strip (y==0, the
    # first 6 walkable cells) before the forest job is ever placed. Under the fix, the
    # grassland jobs correctly claim only region-0 (y 1-4) cells, leaving the forest strip
    # untouched for the forest job.
    from illuvutar.generation.jobs import Job
    forest_job = Job("hunter", "Hunter", "The Wood", "forest", "tracks game")
    jobs = JOBS[:6] + [forest_job]
    with patch("illuvutar.generation.populace.ollama") as mo:
        mo.chat.return_value = _mock_ok()
        people = generate_populace(jobs, _tilemap(), regions, _WALKABLE, model="m")
    assert len(people) == 7
    assert people[-1]["y"] == 0  # placed in the forest strip (positional region 1), not a fallback cell


def test_malformed_regions_do_not_raise():
    bad_regions = [{"name": "no id or biome"}, {"id": "notanint", "biome": "grassland"}, 42]
    with patch("illuvutar.generation.populace.ollama") as mo:
        mo.chat.return_value = _mock_ok()
        people = generate_populace(JOBS[:3], _tilemap(), bad_regions, _WALKABLE, model="m")
    assert len(people) == 3  # never raised; still placed on walkable cells
