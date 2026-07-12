from illuvutar.engine.entities.store import EntityStore
from illuvutar.engine.entities.components import Position, Sprite, Health, Inventory, Label
from illuvutar.engine.wrl.schema import WRLFrame, WRLTileLayer, WRLEntity
from illuvutar.engine.wrl.serializer import serialize


def _encode_rle_rows(tilemap_data: list[dict], width: int, height: int, tile_to_idx: dict[str, int]) -> list[str]:
    grid = [[0] * width for _ in range(height)]
    for cell in tilemap_data:
        x, y = cell["x"], cell["y"]
        if 0 <= y < height and 0 <= x < width:
            grid[y][x] = tile_to_idx.get(cell["tile_id"], 0)

    rows = []
    for row in grid:
        if not row:
            rows.append(f"0-{width-1}:0")
            continue
        parts = []
        start = 0
        for i in range(1, len(row) + 1):
            if i == len(row) or row[i] != row[start]:
                if i - start == 1:
                    parts.append(f"{start}:{row[start]}")
                else:
                    parts.append(f"{start}-{i-1}:{row[start]}")
                start = i
        rows.append(",".join(parts))
    return rows


class RenderOutputSystem:
    def __init__(self, store: EntityStore, palette: dict[int, str], tilemap_data: list[dict], world_id: str, width: int, height: int):
        self._store = store
        self._palette = palette
        self._tilemap_data = tilemap_data
        self._world_id = world_id
        self._width = width
        self._height = height
        self._tile_to_idx = {v: k for k, v in palette.items()}

    def run(self, tick: int) -> WRLFrame:
        frame = WRLFrame(tick=tick, world_id=self._world_id, timestamp_ms=tick * 100, palette=self._palette)
        rows = _encode_rle_rows(self._tilemap_data, self._width, self._height, self._tile_to_idx)
        frame.tiles = WRLTileLayer(width=self._width, height=self._height, rows=rows)

        for entity_id in self._store.all_ids():
            pos = self._store.get_component(entity_id, Position)
            sprite = self._store.get_component(entity_id, Sprite)
            if pos is None or sprite is None:
                continue
            health_comp = self._store.get_component(entity_id, Health)
            inv = self._store.get_component(entity_id, Inventory)
            label_comp = self._store.get_component(entity_id, Label)
            frame.entities.append(WRLEntity(
                id=entity_id,
                kind=self._store.kind(entity_id) or "object",
                x=pos.x, y=pos.y,
                sprite=sprite.sprite_name,
                facing=sprite.facing,
                state=sprite.animation_state,
                health=health_comp.normalized if health_comp else 1.0,
                carrying=inv.carrying if inv else "none",
                label=label_comp.name if label_comp else "",
            ))

        return frame
