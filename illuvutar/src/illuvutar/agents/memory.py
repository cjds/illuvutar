"""Persistent conversation memory for the God agent."""
import json
from pathlib import Path


class GodMemory:
    def __init__(self, path: Path | str):
        self.path = Path(path)

    def load(self) -> list[dict]:
        if not self.path.exists():
            return []
        try:
            return json.loads(self.path.read_text())
        except Exception:
            return []

    def save(self, messages: list[dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(messages, indent=2, ensure_ascii=False))
