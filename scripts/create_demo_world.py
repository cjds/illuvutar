#!/usr/bin/env python3
"""Create a minimal demo world for testing the simulation engine.

Usage: python3 scripts/create_demo_world.py [--out demo_world]
Produces a world/ directory loadable by `illuvutar-engine`.
"""
import argparse
import json
import shutil
import yaml
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
PALETTE_DIR = REPO_ROOT / "palettes" / "verdant"

WIDTH = 24
HEIGHT = 20

def make_tilemap() -> list[dict]:
    """24×20 map: grass border, forest patches, a lake, a path."""
    cells = []
    for y in range(HEIGHT):
        for x in range(WIDTH):
            # Water lake in bottom-right
            if 14 <= x <= 20 and 12 <= y <= 17:
                tid = "water_deep" if (15 <= x <= 19 and 13 <= y <= 16) else "water_shallow"
            # Forest patch top-left
            elif x <= 6 and y <= 8:
                tid = "forest_canopy" if (1 <= x <= 5 and 1 <= y <= 7) else "forest_floor"
            # Stone ruin cluster
            elif 10 <= x <= 13 and 5 <= y <= 9:
                tid = "stone_wall" if (x in (10, 13) or y in (5, 9)) else "stone_floor"
            # Dirt path through middle
            elif x == 8 or y == 10:
                tid = "dirt_path"
            # Sand shore near lake
            elif 13 <= x <= 21 and 11 <= y <= 18:
                tid = "sand_shore"
            else:
                import random
                rng = random.Random(x * 100 + y)
                tid = "grass_flowers" if rng.random() < 0.15 else "grass_plain"
            cells.append({"x": x, "y": y, "tile_id": tid, "region": _region(x, y)})
    return cells

def _region(x: int, y: int) -> int:
    if x <= 7 and y <= 9: return 0   # The Verdant Wood
    if x >= 13 and y >= 11: return 1  # The Mirror Lake
    if 9 <= x <= 14 and 4 <= y <= 10: return 2  # The Ruined Keep
    return 3  # The Open Plains

def make_agents() -> list[dict]:
    return [
        {"id": "wanderer",  "kind": "humanoid",  "x": 10, "y": 10,
         "name": "Elara the Wanderer",
         "behavior": "explore and discover, drawn to ruins and ancient places"},
        {"id": "scholar",   "kind": "scholar",   "x": 11, "y": 7,
         "name": "Doran the Scholar",
         "behavior": "study the ruins, record observations, seek lost knowledge"},
        {"id": "guardian",  "kind": "guardian",  "x": 8,  "y": 10,
         "name": "Kael the Guardian",
         "behavior": "protect the path, watch for strangers, guard the crossing"},
    ]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="demo_world")
    args = parser.parse_args()
    out = REPO_ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)

    # Copy palette for loader
    palette_tiles = []
    palette_meta = yaml.safe_load((PALETTE_DIR / "palette_meta.yaml").read_text())
    for tile in palette_meta["tiles"]:
        palette_tiles.append(tile)

    (out / "palette.yaml").write_text(yaml.dump({
        "palette_used": str(PALETTE_DIR),
        "tiles": palette_tiles,
    }))

    (out / "constitution.yaml").write_text(yaml.dump({
        "world_name": "Verdant Crossroads",
        "palette_used": str(PALETTE_DIR),
        "width": WIDTH,
        "height": HEIGHT,
        "tone": "A quiet world of forest, ruin, and still water. Three travelers meet.",
        "rules": [
            "No entity may enter water without the 'swimmer' tag.",
            "Ruins are old — their stories are incomplete.",
        ],
    }))

    regions = [
        {"id": 0, "name": "The Verdant Wood",  "biome": "forest",  "centroid_x": 3.5, "centroid_y": 4.5, "atmosphere": "dark canopy, birdsong"},
        {"id": 1, "name": "The Mirror Lake",   "biome": "water",   "centroid_x": 17,  "centroid_y": 14,  "atmosphere": "still water, reflections"},
        {"id": 2, "name": "The Ruined Keep",   "biome": "ruins",   "centroid_x": 11,  "centroid_y": 7,   "atmosphere": "crumbling stone, echoes"},
        {"id": 3, "name": "The Open Plains",   "biome": "grassland","centroid_x": 12,  "centroid_y": 14,  "atmosphere": "wide sky, warm wind"},
    ]
    (out / "regions.yaml").write_text(yaml.dump({"regions": regions}))

    tilemap = make_tilemap()
    (out / "tilemap.json").write_text(json.dumps(tilemap, indent=2))

    agents = make_agents()
    (out / "agents.yaml").write_text(yaml.dump(agents))

    (out / "factions.yaml").write_text(yaml.dump([
        {"id": "wanderers", "name": "The Wayfarers", "region_ids": [3],
         "disposition": "neutral", "description": "Travellers with no fixed home."},
    ]))
    (out / "history.yaml").write_text(yaml.dump([
        {"era": "ancient", "event": "A keep was built here, then fell silent.", "region_id": 2},
        {"era": "recent",  "event": "Three strangers arrived at the crossroads on the same day.", "region_id": 3},
    ]))
    (out / "meta.yaml").write_text(yaml.dump({
        "generation_log": [{"agent": "demo_script", "action": "created", "detail": "demo world"}]
    }))

    print(f"Demo world written to {out}/")
    print(f"  {WIDTH}×{HEIGHT} tiles, {len(agents)} entities, {len(regions)} regions")
    print(f"\nTo run the engine:")
    print(f"  cd engine && uv run python3 -m engine ../{args.out} --port 8080")
    print(f"  Then open http://localhost:8080 in your browser")

if __name__ == "__main__":
    main()
