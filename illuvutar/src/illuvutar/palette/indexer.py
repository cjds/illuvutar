from dataclasses import dataclass, field
from pathlib import Path
import yaml


@dataclass
class Tile:
    id: str
    sprite_path: str
    layer: str
    tags: list[str] = field(default_factory=list)
    adjacent: list[str] = field(default_factory=list)


def index_palette(palette_dir: Path | str) -> list[Tile]:
    palette_dir = Path(palette_dir)
    meta_file = palette_dir / "palette_meta.yaml"
    if not meta_file.exists():
        raise FileNotFoundError(f"No palette_meta.yaml found in {palette_dir}")

    with open(meta_file) as f:
        meta = yaml.safe_load(f)

    tiles = []
    for entry in meta.get("tiles", []):
        png = palette_dir / f"{entry['id']}.png"
        if not png.exists():
            raise FileNotFoundError(f"Sprite not found: {png}")
        tiles.append(Tile(
            id=entry["id"],
            sprite_path=str(png),
            layer=entry.get("layer", "ground"),
            tags=entry.get("tags", []),
            adjacent=entry.get("adjacent", []),
        ))

    return tiles
