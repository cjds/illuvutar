import json
import pytest
from pathlib import Path
from illuvutar.agents.memory import GodMemory


def test_load_returns_empty_when_no_file(tmp_path):
    mem = GodMemory(tmp_path / "mem.json")
    assert mem.load() == []


def test_save_and_load_roundtrip(tmp_path):
    path = tmp_path / "mem.json"
    mem = GodMemory(path)
    messages = [
        {"role": "system", "content": "You are god."},
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "I am awakened."},
    ]
    mem.save(messages)
    assert path.exists()
    loaded = mem.load()
    assert loaded == messages


def test_save_overwrites_previous(tmp_path):
    path = tmp_path / "mem.json"
    mem = GodMemory(path)
    mem.save([{"role": "user", "content": "first"}])
    mem.save([{"role": "user", "content": "second"}])
    loaded = mem.load()
    assert len(loaded) == 1
    assert loaded[0]["content"] == "second"
