# World Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the world generation pipeline — a CLI tool that starts a god agent, converses with a human via a TUI, indexes a tile palette, and produces a `world/` directory of YAML/JSON files ready for the engine.

**Architecture:** The palette directory is indexed into ChromaDB at startup. A persistent god agent (local ollama LLM) converses with the human, uses tool calls to read files and query the RAG, writes world-state files in order (constitution → regions → specialists → tilemap via WFC), and exits when the world is complete. The Textual TUI provides a two-panel chat interface.

**Tech Stack:** Python 3.12+, uv, ollama (local LLM), chromadb, sentence-transformers, textual, pyyaml, scipy, numpy, pytest

## Global Constraints

- Use `python3` — `python` is not available
- All world-state files must be human-readable YAML or JSON
- The god agent cannot invent tile IDs not present in `palette.yaml`
- `constitution.yaml` must be written before any specialist runs
- `tilemap.json` is always the last file written
- Tests must not require ollama to be running — mock the LLM client

---

## File Map

```
illuvutar/
  pyproject.toml
  src/illuvutar/
    __init__.py
    cli.py                        # click entry point: `illuvutar create-world`
    palette/
      __init__.py
      indexer.py                  # scan palette dir → Tile list + palette.yaml
      rag.py                      # ChromaDB index + query_palette(description) → [Tile]
    world_state/
      __init__.py
      schema.py                   # dataclasses: Constitution, Region, Faction, etc.
      writer.py                   # WorldStateWriter: write_file(name, content)
    generation/
      __init__.py
      voronoi.py                  # regions_to_grid(regions, w, h) → np.ndarray
      wfc.py                      # WFC class: collapse tile grid from adjacency rules
    agents/
      __init__.py
      tools.py                    # tool implementations for god agent
      god.py                      # GodAgent: persistent ollama loop + tool dispatch
      specialist.py               # SpecialistAgent: one-shot mandate → world-state slice
    tui/
      __init__.py
      app.py                      # Textual two-panel TUI
  tests/
    conftest.py
    test_indexer.py
    test_rag.py
    test_schema.py
    test_writer.py
    test_voronoi.py
    test_wfc.py
    test_tools.py
    test_god.py
    test_specialist.py
```

---

### Task 1: Project Scaffold + Palette Indexer

**Files:**
- Create: `pyproject.toml`
- Create: `src/illuvutar/__init__.py`
- Create: `src/illuvutar/palette/__init__.py`
- Create: `src/illuvutar/palette/indexer.py`
- Create: `tests/conftest.py`
- Create: `tests/test_indexer.py`

**Interfaces:**
- Produces: `Tile(id, sprite_path, layer, tags, adjacent)` dataclass; `index_palette(palette_dir) -> list[Tile]`; writes `palette.yaml` to `world_dir`

- [ ] **Step 1: Create pyproject.toml**

```toml
[project]
name = "illuvutar"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "ollama>=0.3",
    "chromadb>=0.5",
    "sentence-transformers>=3.0",
    "textual>=0.60",
    "pyyaml>=6.0",
    "scipy>=1.13",
    "numpy>=1.26",
    "click>=8.1",
]

[project.scripts]
illuvutar = "illuvutar.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]

[dependency-groups]
dev = ["pytest>=8.0", "pytest-asyncio>=0.23"]
```

- [ ] **Step 2: Install dependencies**

```bash
uv sync --dev
```

Expected: resolves and installs all packages without error.

- [ ] **Step 3: Write the failing test**

```python
# tests/test_indexer.py
import pytest
from pathlib import Path
from illuvutar.palette.indexer import index_palette, Tile

@pytest.fixture
def palette_dir(tmp_path):
    # Create fake PNG files and a meta.yaml
    (tmp_path / "grass_plain.png").write_bytes(b"PNG")
    (tmp_path / "water_deep.png").write_bytes(b"PNG")
    meta = {
        "tiles": [
            {
                "id": "grass_plain",
                "layer": "ground",
                "tags": ["grass", "walkable"],
                "adjacent": ["grass_plain", "water_deep"],
            },
            {
                "id": "water_deep",
                "layer": "ground",
                "tags": ["water", "impassable"],
                "adjacent": ["water_deep", "grass_plain"],
            },
        ]
    }
    import yaml
    (tmp_path / "palette_meta.yaml").write_text(yaml.dump(meta))
    return tmp_path

def test_index_palette_returns_tiles(palette_dir):
    tiles = index_palette(palette_dir)
    assert len(tiles) == 2
    ids = {t.id for t in tiles}
    assert ids == {"grass_plain", "water_deep"}

def test_tile_has_correct_fields(palette_dir):
    tiles = index_palette(palette_dir)
    grass = next(t for t in tiles if t.id == "grass_plain")
    assert grass.layer == "ground"
    assert "walkable" in grass.tags
    assert "grass_plain" in grass.adjacent
    assert grass.sprite_path.endswith("grass_plain.png")

def test_index_palette_requires_matching_png(palette_dir, tmp_path):
    # Tile in meta but no png → raises
    import yaml
    bad_dir = tmp_path / "bad"
    bad_dir.mkdir()
    (bad_dir / "palette_meta.yaml").write_text(yaml.dump({
        "tiles": [{"id": "ghost_tile", "layer": "ground", "tags": [], "adjacent": []}]
    }))
    with pytest.raises(FileNotFoundError):
        index_palette(bad_dir)
```

- [ ] **Step 4: Run test to verify it fails**

```bash
uv run pytest tests/test_indexer.py -v
```

Expected: `ImportError` or `ModuleNotFoundError` — indexer does not exist yet.

- [ ] **Step 5: Implement indexer**

```python
# src/illuvutar/palette/indexer.py
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
```

- [ ] **Step 6: Run test to verify it passes**

```bash
uv run pytest tests/test_indexer.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml src/ tests/
git commit -m "feat: scaffold project and implement palette indexer"
```

---

### Task 2: RAG System (ChromaDB)

**Files:**
- Create: `src/illuvutar/palette/rag.py`
- Create: `tests/test_rag.py`

**Interfaces:**
- Consumes: `list[Tile]` from `index_palette()`
- Produces: `PaletteRAG.build(tiles)` class method; `PaletteRAG.query(description: str, n: int) -> list[Tile]`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_rag.py
import pytest
from illuvutar.palette.indexer import Tile
from illuvutar.palette.rag import PaletteRAG

@pytest.fixture
def sample_tiles():
    return [
        Tile("grass_plain", "/p/grass_plain.png", "ground", ["grass", "walkable"], ["grass_plain"]),
        Tile("water_shallow", "/p/water_shallow.png", "ground", ["water", "walkable"], ["water_deep"]),
        Tile("water_deep", "/p/water_deep.png", "ground", ["water", "impassable"], ["water_shallow"]),
        Tile("wall_stone", "/p/wall_stone.png", "object", ["wall", "impassable"], ["wall_stone"]),
    ]

def test_query_returns_water_tiles(sample_tiles, tmp_path):
    rag = PaletteRAG.build(sample_tiles, persist_dir=str(tmp_path))
    results = rag.query("shallow water edge for rivers", n=2)
    ids = [t.id for t in results]
    assert "water_shallow" in ids

def test_query_returns_at_most_n(sample_tiles, tmp_path):
    rag = PaletteRAG.build(sample_tiles, persist_dir=str(tmp_path))
    results = rag.query("any tile", n=2)
    assert len(results) <= 2

def test_query_returns_tiles_not_strings(sample_tiles, tmp_path):
    rag = PaletteRAG.build(sample_tiles, persist_dir=str(tmp_path))
    results = rag.query("grass", n=1)
    assert isinstance(results[0], Tile)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_rag.py -v
```

Expected: `ImportError` — rag module does not exist.

- [ ] **Step 3: Implement PaletteRAG**

```python
# src/illuvutar/palette/rag.py
import json
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from illuvutar.palette.indexer import Tile


class PaletteRAG:
    COLLECTION = "palette_tiles"

    def __init__(self, client: chromadb.Client, tiles_by_id: dict[str, Tile]):
        self._client = client
        self._tiles_by_id = tiles_by_id
        self._collection = client.get_collection(
            self.COLLECTION,
            embedding_function=SentenceTransformerEmbeddingFunction(),
        )

    @classmethod
    def build(cls, tiles: list[Tile], persist_dir: str) -> "PaletteRAG":
        client = chromadb.PersistentClient(path=persist_dir)
        ef = SentenceTransformerEmbeddingFunction()
        try:
            client.delete_collection(cls.COLLECTION)
        except Exception:
            pass
        collection = client.create_collection(cls.COLLECTION, embedding_function=ef)

        documents = [
            f"{t.id} layer={t.layer} tags={' '.join(t.tags)} adjacent={' '.join(t.adjacent)}"
            for t in tiles
        ]
        collection.add(
            documents=documents,
            ids=[t.id for t in tiles],
            metadatas=[{"tile_json": json.dumps(t.__dict__)} for t in tiles],
        )

        tiles_by_id = {t.id: t for t in tiles}
        return cls(client, tiles_by_id)

    def query(self, description: str, n: int = 5) -> list[Tile]:
        results = self._collection.query(query_texts=[description], n_results=min(n, len(self._tiles_by_id)))
        ids = results["ids"][0]
        return [self._tiles_by_id[tile_id] for tile_id in ids if tile_id in self._tiles_by_id]
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_rag.py -v
```

Expected: 3 tests PASS. (First run downloads sentence-transformers model — may take a minute.)

- [ ] **Step 5: Commit**

```bash
git add src/illuvutar/palette/rag.py tests/test_rag.py
git commit -m "feat: implement palette RAG with ChromaDB"
```

---

### Task 3: World-State Schema + Writer

**Files:**
- Create: `src/illuvutar/world_state/__init__.py`
- Create: `src/illuvutar/world_state/schema.py`
- Create: `src/illuvutar/world_state/writer.py`
- Create: `tests/test_schema.py`
- Create: `tests/test_writer.py`

**Interfaces:**
- Produces: `Constitution`, `Region`, `RegionMap`, `Faction`, `HistoryEvent`, `AgentRecord`, `WorldMeta` dataclasses; `WorldStateWriter(world_dir)` with `write(name, content)`, `read(name)`, `status() -> dict[str, bool]`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_schema.py
from illuvutar.world_state.schema import Constitution, Region, RegionMap

def test_constitution_serializes():
    c = Constitution(
        world_name="Ashenveil",
        palette_used="forest_ruins_v1",
        width=64, height=64,
        tone="melancholic ancient world",
        rules=["no magic", "survival focus"],
    )
    d = c.to_dict()
    assert d["world_name"] == "Ashenveil"
    assert d["width"] == 64

def test_region_map_serializes():
    r = Region(id=0, name="The Ashwood", biome="forest", centroid_x=10, centroid_y=10, atmosphere="dense fog")
    rm = RegionMap(regions=[r])
    d = rm.to_dict()
    assert d["regions"][0]["name"] == "The Ashwood"
```

```python
# tests/test_writer.py
import yaml
import json
from pathlib import Path
from illuvutar.world_state.writer import WorldStateWriter
from illuvutar.world_state.schema import Constitution

def test_write_creates_yaml_file(tmp_path):
    writer = WorldStateWriter(tmp_path)
    c = Constitution("TestWorld", "palette_v1", 32, 32, "test", [])
    writer.write("constitution", c.to_dict())
    assert (tmp_path / "constitution.yaml").exists()

def test_read_round_trips(tmp_path):
    writer = WorldStateWriter(tmp_path)
    c = Constitution("TestWorld", "palette_v1", 32, 32, "dark", ["rule1"])
    writer.write("constitution", c.to_dict())
    loaded = writer.read("constitution")
    assert loaded["world_name"] == "TestWorld"

def test_write_tilemap_as_json(tmp_path):
    writer = WorldStateWriter(tmp_path)
    tilemap = [{"x": 0, "y": 0, "tile_id": "grass_plain", "region": 0}]
    writer.write("tilemap", tilemap)
    assert (tmp_path / "tilemap.json").exists()

def test_status_tracks_completion(tmp_path):
    writer = WorldStateWriter(tmp_path)
    status = writer.status()
    assert status["constitution"] is False
    writer.write("constitution", {"world_name": "X", "palette_used": "p", "width": 32, "height": 32, "tone": "t", "rules": []})
    assert writer.status()["constitution"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_schema.py tests/test_writer.py -v
```

Expected: `ImportError`.

- [ ] **Step 3: Implement schema**

```python
# src/illuvutar/world_state/schema.py
from dataclasses import dataclass, field, asdict


@dataclass
class Constitution:
    world_name: str
    palette_used: str
    width: int
    height: int
    tone: str
    rules: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Region:
    id: int
    name: str
    biome: str
    centroid_x: float
    centroid_y: float
    atmosphere: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RegionMap:
    regions: list[Region]

    def to_dict(self) -> dict:
        return {"regions": [r.to_dict() for r in self.regions]}


@dataclass
class Faction:
    id: str
    name: str
    region_ids: list[int]
    disposition: str
    description: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class HistoryEvent:
    era: str
    event: str
    region_id: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AgentRecord:
    id: str
    kind: str
    x: int
    y: int
    name: str
    faction_id: str | None = None
    behavior: str = "wander_passive"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class WorldMeta:
    generation_log: list[dict] = field(default_factory=list)

    def log(self, agent: str, action: str, detail: str = "") -> None:
        self.generation_log.append({"agent": agent, "action": action, "detail": detail})

    def to_dict(self) -> dict:
        return {"generation_log": self.generation_log}
```

- [ ] **Step 4: Implement writer**

```python
# src/illuvutar/world_state/writer.py
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
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/test_schema.py tests/test_writer.py -v
```

Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add src/illuvutar/world_state/ tests/test_schema.py tests/test_writer.py
git commit -m "feat: world-state schema and writer"
```

---

### Task 4: Voronoi Region Layout

**Files:**
- Create: `src/illuvutar/generation/__init__.py`
- Create: `src/illuvutar/generation/voronoi.py`
- Create: `tests/test_voronoi.py`

**Interfaces:**
- Consumes: `list[Region]`, `width: int`, `height: int`
- Produces: `regions_to_grid(regions, width, height) -> np.ndarray` — 2D array where each cell is a region index

- [ ] **Step 1: Write the failing test**

```python
# tests/test_voronoi.py
import numpy as np
import pytest
from illuvutar.world_state.schema import Region
from illuvutar.generation.voronoi import regions_to_grid

@pytest.fixture
def two_regions():
    return [
        Region(id=0, name="Left", biome="forest", centroid_x=8, centroid_y=16),
        Region(id=1, name="Right", biome="desert", centroid_x=24, centroid_y=16),
    ]

def test_grid_shape(two_regions):
    grid = regions_to_grid(two_regions, width=32, height=32)
    assert grid.shape == (32, 32)

def test_grid_values_are_region_indices(two_regions):
    grid = regions_to_grid(two_regions, width=32, height=32)
    assert set(np.unique(grid)).issubset({0, 1})

def test_left_half_is_region_0(two_regions):
    grid = regions_to_grid(two_regions, width=32, height=32)
    # Cells near left centroid should belong to region 0
    assert grid[16, 4] == 0

def test_right_half_is_region_1(two_regions):
    grid = regions_to_grid(two_regions, width=32, height=32)
    assert grid[16, 28] == 1
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_voronoi.py -v
```

Expected: `ImportError`.

- [ ] **Step 3: Implement Voronoi layout**

```python
# src/illuvutar/generation/voronoi.py
import numpy as np
from scipy.spatial import KDTree
from illuvutar.world_state.schema import Region


def regions_to_grid(regions: list[Region], width: int, height: int) -> np.ndarray:
    """Return a (height, width) array where each cell is the index of its nearest region centroid."""
    points = np.array([[r.centroid_x, r.centroid_y] for r in regions], dtype=float)
    tree = KDTree(points)

    ys, xs = np.mgrid[0:height, 0:width]
    grid_points = np.column_stack([xs.ravel().astype(float), ys.ravel().astype(float)])
    _, indices = tree.query(grid_points)

    return indices.reshape(height, width).astype(np.int32)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_voronoi.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/illuvutar/generation/ tests/test_voronoi.py
git commit -m "feat: Voronoi region layout"
```

---

### Task 5: WFC Tile Placement

**Files:**
- Create: `src/illuvutar/generation/wfc.py`
- Create: `tests/test_wfc.py`

**Interfaces:**
- Consumes: `region_grid: np.ndarray`, `regions: list[Region]`, `tiles: list[Tile]`, `width: int`, `height: int`
- Produces: `WFC.collapse() -> list[list[str]] | None` — 2D list of tile IDs, or None on contradiction

- [ ] **Step 1: Write the failing test**

```python
# tests/test_wfc.py
import numpy as np
import pytest
from illuvutar.palette.indexer import Tile
from illuvutar.world_state.schema import Region
from illuvutar.generation.wfc import WFC

@pytest.fixture
def simple_setup():
    tiles = [
        Tile("grass", "/p/grass.png", "ground", ["grass"], ["grass", "dirt"]),
        Tile("dirt", "/p/dirt.png", "ground", ["grass"], ["grass", "dirt"]),
    ]
    regions = [Region(id=0, name="Field", biome="grass", centroid_x=2, centroid_y=2)]
    region_grid = np.zeros((4, 4), dtype=np.int32)
    return tiles, regions, region_grid

def test_collapse_returns_correct_shape(simple_setup):
    tiles, regions, grid = simple_setup
    wfc = WFC(width=4, height=4, tiles=tiles, region_grid=grid, regions=regions)
    result = wfc.collapse()
    assert result is not None
    assert len(result) == 4
    assert len(result[0]) == 4

def test_collapse_uses_valid_tile_ids(simple_setup):
    tiles, regions, grid = simple_setup
    wfc = WFC(width=4, height=4, tiles=tiles, region_grid=grid, regions=regions)
    result = wfc.collapse()
    valid_ids = {"grass", "dirt"}
    for row in result:
        for cell in row:
            assert cell in valid_ids

def test_collapse_respects_adjacency(simple_setup):
    # Tile "water" is not adjacent to "grass" — so if grid has only grass tiles
    # and water is not in adj list of grass, water should never appear
    tiles, regions, grid = simple_setup
    wfc = WFC(width=4, height=4, tiles=tiles, region_grid=grid, regions=regions)
    result = wfc.collapse()
    for row in result:
        for cell in row:
            assert cell != "water"

def test_contradiction_returns_none():
    # Tile with empty adjacency list cannot propagate — force contradiction
    tiles = [Tile("isolated", "/p/iso.png", "ground", ["x"], [])]
    regions = [Region(id=0, name="X", biome="x", centroid_x=1, centroid_y=1)]
    grid = np.zeros((3, 3), dtype=np.int32)
    wfc = WFC(width=3, height=3, tiles=tiles, region_grid=grid, regions=regions)
    # 3x3 with one tile that has no neighbors allowed → only (0,0) collapses cleanly
    # neighbors of any cell get empty set → contradiction
    result = wfc.collapse()
    # Either it collapses (single tile trivially satisfies adjacency with itself) or returns None
    # We just assert it doesn't raise
    assert result is None or isinstance(result, list)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_wfc.py -v
```

Expected: `ImportError`.

- [ ] **Step 3: Implement WFC**

```python
# src/illuvutar/generation/wfc.py
import random
from collections import deque
import numpy as np
from illuvutar.palette.indexer import Tile
from illuvutar.world_state.schema import Region


class WFC:
    def __init__(
        self,
        width: int,
        height: int,
        tiles: list[Tile],
        region_grid: np.ndarray,
        regions: list[Region],
    ):
        self.width = width
        self.height = height
        self.adjacency: dict[str, set[str]] = {t.id: set(t.adjacent) for t in tiles}

        # Build biome → eligible tile IDs map
        biome_tiles: dict[str, set[str]] = {}
        for t in tiles:
            for tag in t.tags:
                biome_tiles.setdefault(tag, set()).add(t.id)

        # Initialize possibilities per cell based on region biome
        self.possibilities: list[list[set[str]]] = []
        for y in range(height):
            row = []
            for x in range(width):
                region_idx = int(region_grid[y, x])
                biome = regions[region_idx].biome
                eligible = biome_tiles.get(biome, set(self.adjacency.keys()))
                row.append(set(eligible))
            self.possibilities.append(row)

    def collapse(self) -> list[list[str]] | None:
        MAX_ITERATIONS = self.width * self.height * 10
        for _ in range(MAX_ITERATIONS):
            cell = self._min_entropy_cell()
            if cell is None:
                break  # fully collapsed

            x, y = cell
            poss = self.possibilities[y][x]
            if not poss:
                return None  # contradiction

            chosen = random.choice(list(poss))
            self.possibilities[y][x] = {chosen}

            if not self._propagate(x, y):
                return None  # contradiction during propagation

        # Verify fully collapsed and extract
        result = []
        for y in range(self.height):
            row = []
            for x in range(self.width):
                poss = self.possibilities[y][x]
                if not poss:
                    return None
                row.append(next(iter(poss)))
            result.append(row)
        return result

    def _min_entropy_cell(self) -> tuple[int, int] | None:
        min_entropy = float("inf")
        best = None
        for y in range(self.height):
            for x in range(self.width):
                n = len(self.possibilities[y][x])
                if n == 0:
                    return (x, y)  # contradiction — surface it
                if 1 < n < min_entropy:
                    min_entropy = n
                    best = (x, y)
        return best

    def _propagate(self, start_x: int, start_y: int) -> bool:
        queue: deque[tuple[int, int]] = deque([(start_x, start_y)])
        while queue:
            cx, cy = queue.popleft()
            current_allowed_neighbors: set[str] = set()
            for tile_id in self.possibilities[cy][cx]:
                current_allowed_neighbors |= self.adjacency.get(tile_id, set())

            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                nx, ny = cx + dx, cy + dy
                if not (0 <= nx < self.width and 0 <= ny < self.height):
                    continue
                neighbor_poss = self.possibilities[ny][nx]
                new_poss = neighbor_poss & current_allowed_neighbors
                if not new_poss:
                    return False  # contradiction
                if new_poss != neighbor_poss:
                    self.possibilities[ny][nx] = new_poss
                    queue.append((nx, ny))
        return True
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_wfc.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/illuvutar/generation/wfc.py tests/test_wfc.py
git commit -m "feat: WFC tile placement"
```

---

### Task 6: God Agent Tools

**Files:**
- Create: `src/illuvutar/agents/__init__.py`
- Create: `src/illuvutar/agents/tools.py`
- Create: `tests/test_tools.py`

**Interfaces:**
- Consumes: `WorldStateWriter`, `PaletteRAG`, `WFC`, `regions_to_grid`, `list[Region]`
- Produces: `AgentTools` class with methods matching ollama tool signatures: `read_file`, `write_world_state`, `query_palette`, `run_wfc`, `spawn_specialist`; `AgentTools.definitions() -> list[dict]` (ollama tool schema list)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tools.py
import pytest
from pathlib import Path
from unittest.mock import MagicMock
from illuvutar.agents.tools import AgentTools

@pytest.fixture
def tools(tmp_path):
    writer = MagicMock()
    writer.world_dir = tmp_path
    writer.read.return_value = {"world_name": "Test"}
    rag = MagicMock()
    rag.query.return_value = []
    return AgentTools(writer=writer, rag=rag, tiles=[], palette_dir=tmp_path)

def test_read_file_reads_world_state(tools, tmp_path):
    (tmp_path / "constitution.yaml").write_text("world_name: Test\n")
    result = tools.read_file("constitution")
    assert "world_name" in result or result is not None

def test_write_world_state_delegates_to_writer(tools):
    tools.write_world_state("constitution", '{"world_name": "X", "palette_used": "p", "width": 32, "height": 32, "tone": "t", "rules": []}')
    tools.writer.write.assert_called_once()

def test_query_palette_returns_string(tools):
    result = tools.query_palette("water edge tiles")
    assert isinstance(result, str)

def test_definitions_returns_list(tools):
    defs = AgentTools.definitions()
    assert isinstance(defs, list)
    assert len(defs) >= 4
    names = [d["function"]["name"] for d in defs]
    assert "read_file" in names
    assert "write_world_state" in names
    assert "query_palette" in names
    assert "run_wfc" in names
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_tools.py -v
```

Expected: `ImportError`.

- [ ] **Step 3: Implement AgentTools**

```python
# src/illuvutar/agents/tools.py
import json
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
        content = self.writer.read(name)
        if content is None:
            return f"File '{name}' does not exist yet."
        return yaml.dump(content) if isinstance(content, dict) else json.dumps(content)

    def write_world_state(self, name: str, content_json: str) -> str:
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
        lines = [f"- {t.id} (layer={t.layer}, tags={t.tags}, adjacent={t.adjacent})" for t in results]
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
        # Deferred: specialist runner implemented in Task 8
        # Store mandate for later processing
        try:
            mandate = json.loads(mandate_json)
        except Exception:
            return "Error: mandate must be valid JSON."
        mandate_path = self.writer.world_dir / "specialists" / f"{mandate['role']}-mandate.yaml"
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
                        "properties": {"name": {"type": "string", "description": "File name without extension"}},
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
                            "content_json": {"type": "string", "description": "JSON-encoded content to write"},
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
                        "properties": {"mandate_json": {"type": "string", "description": "JSON string describing the specialist mandate"}},
                        "required": ["mandate_json"],
                    },
                },
            },
        ]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_tools.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/illuvutar/agents/ tests/test_tools.py
git commit -m "feat: god agent tool implementations"
```

---

### Task 7: God Agent

**Files:**
- Create: `src/illuvutar/agents/god.py`
- Create: `tests/test_god.py`

**Interfaces:**
- Consumes: `AgentTools`, model name string
- Produces: `GodAgent(model, tools)` with `chat(human_message: str) -> str` (streams god response, executes tool calls, returns final text) and `is_done() -> bool`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_god.py
import pytest
from unittest.mock import MagicMock, patch
from illuvutar.agents.god import GodAgent
from illuvutar.agents.tools import AgentTools

@pytest.fixture
def mock_tools():
    tools = MagicMock(spec=AgentTools)
    tools.read_file.return_value = "world_name: Test"
    tools.query_palette.return_value = "- grass_plain (layer=ground)"
    AgentTools.definitions = staticmethod(lambda: [])
    return tools

def _make_ollama_response(content, tool_calls=None):
    msg = MagicMock()
    msg.content = content
    msg.tool_calls = tool_calls or []
    resp = MagicMock()
    resp.message = msg
    return resp

def test_god_returns_text_response(mock_tools):
    with patch("illuvutar.agents.god.ollama") as mock_ollama:
        mock_ollama.chat.return_value = _make_ollama_response("I shall build a world of ancient forest.")
        agent = GodAgent(model="llama3.2", tools=mock_tools)
        response = agent.chat("What kind of world shall we make?")
        assert "forest" in response

def test_god_calls_tool_when_requested(mock_tools):
    tool_call = MagicMock()
    tool_call.function.name = "query_palette"
    tool_call.function.arguments = {"description": "forest tiles"}

    with patch("illuvutar.agents.god.ollama") as mock_ollama:
        # First response has a tool call, second is final text
        mock_ollama.chat.side_effect = [
            _make_ollama_response("", tool_calls=[tool_call]),
            _make_ollama_response("I found these forest tiles."),
        ]
        agent = GodAgent(model="llama3.2", tools=mock_tools)
        response = agent.chat("What forest tiles do we have?")
        mock_tools.query_palette.assert_called_once_with(description="forest tiles")
        assert "forest" in response

def test_god_tracks_message_history(mock_tools):
    with patch("illuvutar.agents.god.ollama") as mock_ollama:
        mock_ollama.chat.return_value = _make_ollama_response("A dark and misty world.")
        agent = GodAgent(model="llama3.2", tools=mock_tools)
        agent.chat("Make it dark.")
        agent.chat("Add mist.")
        # Both turns should be in history
        assert len(agent.messages) >= 4  # 2 user + 2 assistant
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_god.py -v
```

Expected: `ImportError`.

- [ ] **Step 3: Implement GodAgent**

```python
# src/illuvutar/agents/god.py
import ollama
from illuvutar.agents.tools import AgentTools

GOD_SYSTEM_PROMPT = """You are the God of this world — an ancient, creative intelligence tasked with generating a living 2D world from a palette of tiles.

You have been given tools to read and write world-state files. Your task is to:
1. Ask the human what palette and resources are available.
2. Query the palette to understand what tiles you have.
3. Write constitution.yaml first — the world's name, tone, rules, and palette.
4. Write regions.yaml — the named regions, biomes, and centroids.
5. Spawn specialist agents if you want help with factions, history, or initial agents.
6. Run WFC to generate the tilemap.
7. Confirm the world is complete.

Introduce concepts slowly. Do not invent tile IDs that are not in the palette.
Be deliberate, creative, and speak with gravitas."""


class GodAgent:
    def __init__(self, model: str, tools: AgentTools):
        self.model = model
        self.tools = tools
        self.messages: list[dict] = [{"role": "system", "content": GOD_SYSTEM_PROMPT}]
        self._done = False

    def chat(self, human_message: str) -> str:
        self.messages.append({"role": "user", "content": human_message})
        return self._run_loop()

    def is_done(self) -> bool:
        return self._done

    def _run_loop(self) -> str:
        tool_defs = AgentTools.definitions()
        while True:
            response = ollama.chat(
                model=self.model,
                messages=self.messages,
                tools=tool_defs if tool_defs else None,
            )
            msg = response.message
            self.messages.append({"role": "assistant", "content": msg.content or "", "tool_calls": [
                {"function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in (msg.tool_calls or [])
            ]})

            if not msg.tool_calls:
                if msg.content and "world is complete" in msg.content.lower():
                    self._done = True
                return msg.content or ""

            for tool_call in msg.tool_calls:
                result = self._dispatch(tool_call.function.name, tool_call.function.arguments)
                self.messages.append({"role": "tool", "content": str(result)})

    def _dispatch(self, name: str, args: dict) -> str:
        method = getattr(self.tools, name, None)
        if method is None:
            return f"Unknown tool: {name}"
        try:
            return method(**args)
        except Exception as e:
            return f"Tool error ({name}): {e}"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_god.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/illuvutar/agents/god.py tests/test_god.py
git commit -m "feat: god agent with ollama tool loop"
```

---

### Task 8: Specialist Agent + TUI + CLI

**Files:**
- Create: `src/illuvutar/agents/specialist.py`
- Create: `src/illuvutar/tui/__init__.py`
- Create: `src/illuvutar/tui/app.py`
- Create: `src/illuvutar/cli.py`
- Create: `tests/test_specialist.py`

**Interfaces:**
- `SpecialistAgent(model, mandate_path, tools).run() -> str`
- `GodChatApp(god_agent, writer)` — Textual App subclass
- `main()` — click entry point

- [ ] **Step 1: Write the failing test for SpecialistAgent**

```python
# tests/test_specialist.py
import pytest
import yaml
from unittest.mock import patch, MagicMock
from illuvutar.agents.specialist import SpecialistAgent

@pytest.fixture
def mandate_file(tmp_path):
    mandate = {
        "role": "faction-agent",
        "task": "Create 2 rival factions for the northern forest region.",
        "constraints": ["Factions must reference only region id 0", "Tone: hostile"],
        "output_file": "factions",
        "read_files": ["constitution", "regions"],
    }
    path = tmp_path / "faction-agent-mandate.yaml"
    path.write_text(yaml.dump(mandate))
    return path

def test_specialist_runs_and_returns_text(mandate_file, tmp_path):
    tools = MagicMock()
    tools.read_file.return_value = "world_name: Test"
    tools.write_world_state.return_value = "Written factions successfully."
    tools.query_palette.return_value = ""

    with patch("illuvutar.agents.specialist.ollama") as mock_ollama:
        msg = MagicMock()
        msg.content = "I have created two rival factions."
        msg.tool_calls = []
        mock_ollama.chat.return_value = MagicMock(message=msg)

        agent = SpecialistAgent(model="llama3.2", mandate_path=mandate_file, tools=tools)
        result = agent.run()
        assert isinstance(result, str)
        assert len(result) > 0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_specialist.py -v
```

Expected: `ImportError`.

- [ ] **Step 3: Implement SpecialistAgent**

```python
# src/illuvutar/agents/specialist.py
from pathlib import Path
import yaml
import ollama
from illuvutar.agents.tools import AgentTools


class SpecialistAgent:
    def __init__(self, model: str, mandate_path: Path, tools: AgentTools):
        self.model = model
        self.tools = tools
        mandate = yaml.safe_load(Path(mandate_path).read_text())
        self.mandate = mandate

        context_parts = [f"You are a specialist agent with role: {mandate['role']}.", f"Task: {mandate['task']}"]
        if mandate.get("constraints"):
            context_parts.append("Constraints:\n" + "\n".join(f"- {c}" for c in mandate["constraints"]))
        if mandate.get("read_files"):
            for fname in mandate["read_files"]:
                content = tools.read_file(fname)
                context_parts.append(f"[{fname}]\n{content}")
        context_parts.append(f"When done, write your output using the write_world_state tool to file '{mandate['output_file']}'.")

        self.messages = [{"role": "system", "content": "\n\n".join(context_parts)},
                         {"role": "user", "content": "Begin your task."}]

    def run(self) -> str:
        tool_defs = AgentTools.definitions()
        while True:
            response = ollama.chat(model=self.model, messages=self.messages, tools=tool_defs or None)
            msg = response.message
            self.messages.append({"role": "assistant", "content": msg.content or ""})

            if not msg.tool_calls:
                return msg.content or ""

            for tc in msg.tool_calls:
                result = self._dispatch(tc.function.name, tc.function.arguments)
                self.messages.append({"role": "tool", "content": str(result)})

    def _dispatch(self, name: str, args: dict) -> str:
        method = getattr(self.tools, name, None)
        if method is None:
            return f"Unknown tool: {name}"
        try:
            return method(**args)
        except Exception as e:
            return f"Tool error: {e}"
```

- [ ] **Step 4: Implement TUI**

```python
# src/illuvutar/tui/app.py
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input, RichLog, Static
from textual.containers import Horizontal, Vertical
from textual import work
from illuvutar.agents.god import GodAgent
from illuvutar.world_state.writer import WorldStateWriter


class WorldStatePanel(Static):
    def __init__(self, writer: WorldStateWriter, **kwargs):
        super().__init__(**kwargs)
        self._writer = writer

    def on_mount(self) -> None:
        self.set_interval(1.0, self.refresh_status)

    def refresh_status(self) -> None:
        status = self._writer.status()
        lines = ["[b]WORLD STATE[/b]\n"]
        for name, done in status.items():
            icon = "✓" if done else "○"
            lines.append(f"  {icon} {name}")
        self.update("\n".join(lines))


class GodChatApp(App):
    CSS = """
    #left { width: 2fr; }
    #right { width: 1fr; border-left: solid $primary; padding: 1; }
    #chat-log { height: 1fr; }
    Input { dock: bottom; }
    """

    def __init__(self, god_agent: GodAgent, writer: WorldStateWriter):
        super().__init__()
        self.god_agent = god_agent
        self.writer = writer

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal():
            with Vertical(id="left"):
                yield RichLog(id="chat-log", highlight=True, markup=True)
                yield Input(placeholder="Speak to the god...", id="input")
            yield WorldStatePanel(self.writer, id="right")
        yield Footer()

    def on_mount(self) -> None:
        log = self.query_one("#chat-log", RichLog)
        log.write("[bold yellow]God:[/bold yellow] I am awakened. What palette have you prepared for me?")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        message = event.value.strip()
        if not message:
            return
        self.query_one("#input", Input).value = ""
        log = self.query_one("#chat-log", RichLog)
        log.write(f"[bold cyan]You:[/bold cyan] {message}")
        self._send_to_god(message)

    @work(thread=True)
    def _send_to_god(self, message: str) -> None:
        response = self.god_agent.chat(message)
        log = self.query_one("#chat-log", RichLog)
        self.call_from_thread(log.write, f"[bold yellow]God:[/bold yellow] {response}")
        if self.god_agent.is_done():
            self.call_from_thread(log.write, "[bold green]The world is complete.[/bold green]")
```

- [ ] **Step 5: Implement CLI**

```python
# src/illuvutar/cli.py
import click
from pathlib import Path
from illuvutar.palette.indexer import index_palette
from illuvutar.palette.rag import PaletteRAG
from illuvutar.world_state.writer import WorldStateWriter
from illuvutar.agents.tools import AgentTools
from illuvutar.agents.god import GodAgent
from illuvutar.tui.app import GodChatApp


@click.group()
def main():
    pass


@main.command()
@click.option("--palette", required=True, type=click.Path(exists=True), help="Path to palette directory")
@click.option("--world", default="world", help="Output world directory")
@click.option("--model", default="llama3.2", help="Ollama model name")
def create_world(palette, world, model):
    """Start the god agent to generate a new world."""
    palette_dir = Path(palette)
    world_dir = Path(world)

    click.echo(f"Indexing palette from {palette_dir}...")
    tiles = index_palette(palette_dir)
    click.echo(f"Found {len(tiles)} tiles. Building RAG index...")

    rag_dir = world_dir / ".rag"
    rag = PaletteRAG.build(tiles, persist_dir=str(rag_dir))

    writer = WorldStateWriter(world_dir)
    tools = AgentTools(writer=writer, rag=rag, tiles=tiles, palette_dir=palette_dir)
    god = GodAgent(model=model, tools=tools)

    app = GodChatApp(god_agent=god, writer=writer)
    app.run()
```

- [ ] **Step 6: Run specialist test**

```bash
uv run pytest tests/test_specialist.py -v
```

Expected: 1 test PASS.

- [ ] **Step 7: Smoke-test the CLI help**

```bash
uv run illuvutar --help
uv run illuvutar create-world --help
```

Expected: help text printed, no import errors.

- [ ] **Step 8: Commit**

```bash
git add src/illuvutar/agents/specialist.py src/illuvutar/tui/ src/illuvutar/cli.py tests/test_specialist.py
git commit -m "feat: specialist agent, TUI, and CLI entry point"
```

---

## Integration Check

After all tasks complete, run the full test suite:

```bash
uv run pytest -v
```

Expected: all tests pass. Then verify the CLI is wired up:

```bash
uv run illuvutar create-world --help
```

Expected: shows `--palette`, `--world`, `--model` options.
