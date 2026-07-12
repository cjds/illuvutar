"""Persist evolved entity state (goal, memory, facts) to world_dir/.entities/<id>.json."""
import json
import logging
import os
import tempfile
from pathlib import Path

from illuvutar.engine.entities.components import Mind

logger = logging.getLogger(__name__)


def _entities_dir(world_dir) -> Path:
    return Path(world_dir) / ".entities"


def _is_safe_id(entity_id: str) -> bool:
    return bool(entity_id) and "/" not in entity_id and "\\" not in entity_id and ".." not in entity_id


def load_entity_state(world_dir, entity_id: str) -> dict | None:
    if not _is_safe_id(entity_id):
        return None
    path = _entities_dir(world_dir) / f"{entity_id}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except Exception as e:
        logger.warning("Could not read entity state for %s: %s", entity_id, e)
        return None
    return data if isinstance(data, dict) else None


def save_entity_state(world_dir, entity_id: str, goal: str, mind: Mind) -> None:
    if not _is_safe_id(entity_id):
        return
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
    except Exception as e:
        logger.warning("Could not persist entity state for %s: %s", entity_id, e)
        pass  # best-effort: never crash the tick loop
