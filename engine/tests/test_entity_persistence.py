from engine.entities.components import Mind
from engine.entities.persistence import load_entity_state, save_entity_state


def test_save_then_load_round_trip(tmp_path):
    mind = Mind(memory="met a stranger", facts="I guard the ruins")
    save_entity_state(tmp_path, "guardian", "guard the ruins", mind)
    state = load_entity_state(tmp_path, "guardian")
    assert state == {
        "goal": "guard the ruins",
        "memory": "met a stranger",
        "facts": "I guard the ruins",
    }


def test_load_missing_returns_none(tmp_path):
    assert load_entity_state(tmp_path, "nobody") is None


def test_load_corrupt_returns_none(tmp_path):
    d = tmp_path / ".entities"
    d.mkdir()
    (d / "broken.json").write_text("{ not valid json")
    assert load_entity_state(tmp_path, "broken") is None


def test_load_non_dict_returns_none(tmp_path):
    d = tmp_path / ".entities"
    d.mkdir()
    (d / "list.json").write_text("[1, 2, 3]")
    assert load_entity_state(tmp_path, "list") is None


def test_save_leaves_no_tmp_files(tmp_path):
    save_entity_state(tmp_path, "guardian", "g", Mind(memory="m", facts="f"))
    tmp_leftovers = list((tmp_path / ".entities").glob("*.tmp"))
    assert tmp_leftovers == []
