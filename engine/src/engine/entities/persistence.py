"""Persist evolved entity state (goal, memory, facts) to world_dir/.entities/<id>.json."""
import json
import os
import tempfile
from pathlib import Path

from engine.entities.components import Mind


def _entities_dir(world_dir) -> Path:
    return Path(world_dir) / ".entities"


def load_entity_state(world_dir, entity_id: str) -> dict | None:
    path = _entities_dir(world_dir) / f"{entity_id}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def save_entity_state(world_dir, entity_id: str, goal: str, mind: Mind) -> None:
    d = _entities_dir(world_dir)
    payload = {"goal": goal, "memory": mind.memory, "facts": mind.facts}
    try:
        d.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(d), suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            os.replace(tmp, d / f"{entity_id}.json")
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
    except Exception:
        pass  # best-effort: never crash the tick loop
