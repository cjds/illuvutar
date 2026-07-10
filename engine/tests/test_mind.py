from engine.entities.components import Mind


def test_set_memory_under_limit_kept_verbatim():
    m = Mind(memory_word_limit=5)
    changed = m.set_memory("the ruins feel alive")
    assert changed is True
    assert m.memory == "the ruins feel alive"


def test_set_memory_truncates_to_word_limit():
    m = Mind(memory_word_limit=3)
    m.set_memory("one two three four five")
    assert m.memory == "one two three"


def test_set_memory_normalizes_whitespace():
    m = Mind(memory_word_limit=10)
    m.set_memory("  spaced   out \n words ")
    assert m.memory == "spaced out words"


def test_set_memory_empty_clears():
    m = Mind(memory="something", memory_word_limit=5)
    changed = m.set_memory("   ")
    assert m.memory == ""
    assert changed is True


def test_set_memory_no_change_returns_false():
    m = Mind(memory_word_limit=5)
    m.set_memory("stable text")
    assert m.set_memory("stable text") is False


def test_set_facts_truncates_to_its_own_limit():
    m = Mind(facts_word_limit=2)
    m.set_facts("I distrust every stranger")
    assert m.facts == "I distrust"
