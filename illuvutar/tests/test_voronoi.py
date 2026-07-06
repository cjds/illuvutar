"""Tests for Voronoi region layout."""
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
