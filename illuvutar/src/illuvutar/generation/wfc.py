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

        # Build biome -> eligible tile IDs map
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
