"""World state file writer and reader for persistent storage."""
import json
from pathlib import Path
import yaml

YAML_FILES = {"constitution", "regions", "factions", "history", "palette", "agents", "meta"}
JSON_FILES = {"tilemap"}
ALL_FILES = YAML_FILES | JSON_FILES


class WorldStateWriter:
    def __init__(self, world_dir: Path | str):
        self.world_dir = Path(world_dir)
        self.world_dir.mkdir(parents=True, exist_ok=True)

    def write(self, name: str, content: dict | list) -> None:
        if name in JSON_FILES:
            path = self.world_dir / f"{name}.json"
            path.write_text(json.dumps(content, indent=2))
        else:
            path = self.world_dir / f"{name}.yaml"
            path.write_text(yaml.dump(content, allow_unicode=True))

    def read(self, name: str) -> dict | list | None:
        yaml_path = self.world_dir / f"{name}.yaml"
        json_path = self.world_dir / f"{name}.json"
        if yaml_path.exists():
            return yaml.safe_load(yaml_path.read_text())
        if json_path.exists():
            return json.loads(json_path.read_text())
        return None

    def status(self) -> dict[str, bool]:
        result = {}
        for name in sorted(ALL_FILES):
            result[name] = (
                (self.world_dir / f"{name}.yaml").exists()
                or (self.world_dir / f"{name}.json").exists()
            )
        return result
