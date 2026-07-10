"""Voronoi region layout using KDTree nearest-neighbor assignment."""
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
