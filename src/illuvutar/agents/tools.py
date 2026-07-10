"""AgentTools: tool implementations for the God Agent."""
import json
import os
from pathlib import Path

import yaml

from illuvutar.palette.indexer import Tile
from illuvutar.palette.rag import PaletteRAG
from illuvutar.world_state.writer import WorldStateWriter
from illuvutar.world_state.schema import Region
from illuvutar.generation.voronoi import regions_to_grid
from illuvutar.generation.wfc import WFC


class AgentTools:
    def __init__(
        self,
        writer: WorldStateWriter,
        rag: PaletteRAG,
        tiles: list[Tile],
        palette_dir: Path,
    ):
        self.writer = writer
        self.rag = rag
        self.tiles = tiles
        self.palette_dir = palette_dir
        self._specialist_results: list[str] = []

    def read_file(self, name: str) -> str:
        world_dir = str(self.writer.world_dir.resolve())
        palette_dir = str(self.palette_dir.resolve())
        full = os.path.realpath(os.path.join(world_dir, name))
        if not (full.startswith(world_dir) or full.startswith(palette_dir)):
            return f"error: path '{name}' is outside world directory"
        content = self.writer.read(name)
        if content is None:
            return f"File '{name}' does not exist yet."
        return yaml.dump(content) if isinstance(content, dict) else json.dumps(content)

    def write_world_state(self, name: str, content_json: str) -> str:
        if not name or '/' in name or '\\' in name or '..' in name:
            return f"error: invalid name '{name}'"
        try:
            content = json.loads(content_json)
        except json.JSONDecodeError:
            try:
                content = yaml.safe_load(content_json)
            except Exception as e:
                return f"Error parsing content: {e}"
        self.writer.write(name, content)
        return f"Written {name} successfully."

    def query_palette(self, description: str) -> str:
        results = self.rag.query(description, n=8)
        if not results:
            return "No matching tiles found."
        lines = [
            f"- {t.id} (layer={t.layer}, tags={t.tags}, adjacent={t.adjacent})"
            for t in results
        ]
        return "\n".join(lines)

    def run_wfc(self, width: int, height: int) -> str:
        regions_data = self.writer.read("regions")
        if not regions_data:
            return "Error: regions.yaml must exist before running WFC."
        regions = [
            Region(
                id=i,
                name=r["name"],
                biome=r["biome"],
                centroid_x=r["centroid_x"],
                centroid_y=r["centroid_y"],
                atmosphere=r.get("atmosphere", ""),
            )
            for i, r in enumerate(regions_data["regions"])
        ]
        grid = regions_to_grid(regions, width, height)
        wfc = WFC(width=width, height=height, tiles=self.tiles, region_grid=grid, regions=regions)
        tilemap = wfc.collapse()
        if tilemap is None:
            return "WFC contradiction — try loosening adjacency rules in palette_meta.yaml."
        cells = [
            {"x": x, "y": y, "tile_id": tilemap[y][x], "region": int(grid[y, x])}
            for y in range(height)
            for x in range(width)
        ]
        self.writer.write("tilemap", cells)
        return f"Tilemap written: {width}x{height} = {len(cells)} tiles."

    def spawn_specialist(self, mandate_json: str) -> str:
        try:
            mandate = json.loads(mandate_json)
        except Exception:
            return "Error: mandate must be valid JSON."
        mandate_path = (
            self.writer.world_dir / "specialists" / f"{mandate['role']}-mandate.yaml"
        )
        mandate_path.parent.mkdir(exist_ok=True)
        mandate_path.write_text(yaml.dump(mandate))
        return f"Specialist mandate written for role '{mandate['role']}'."

    @staticmethod
    def definitions() -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read a world-state file by name (e.g. 'constitution', 'regions'). Returns its content as text.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "File name without extension"}
                        },
                        "required": ["name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "write_world_state",
                    "description": "Write a world-state file. Content must be a JSON string representing the file's data.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "content_json": {
                                "type": "string",
                                "description": "JSON-encoded content to write",
                            },
                        },
                        "required": ["name", "content_json"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "query_palette",
                    "description": "Query the tile palette for tiles matching a natural language description.",
                    "parameters": {
                        "type": "object",
                        "properties": {"description": {"type": "string"}},
                        "required": ["description"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "run_wfc",
                    "description": "Run Wave Function Collapse to generate tilemap.json. Requires regions.yaml to exist first.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "width": {"type": "integer"},
                            "height": {"type": "integer"},
                        },
                        "required": ["width", "height"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "spawn_specialist",
                    "description": "Spawn a specialist agent by writing a mandate file. The mandate must include 'role', 'task', 'constraints', and 'output_file'.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "mandate_json": {
                                "type": "string",
                                "description": "JSON string describing the specialist mandate",
                            }
                        },
                        "required": ["mandate_json"],
                    },
                },
            },
        ]
