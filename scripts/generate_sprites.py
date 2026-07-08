#!/usr/bin/env python3
"""Generate 32x32 pixel-art sprites for the 'verdant' palette."""
# scripts/generate_sprites.py
from pathlib import Path
from PIL import Image, ImageDraw

OUT = Path(__file__).parent.parent / "palettes" / "verdant"
OUT.mkdir(parents=True, exist_ok=True)

TILE_SIZE = 32

def solid(color: tuple, noise: bool = False) -> Image.Image:
    """Solid colour tile with optional pixel noise."""
    img = Image.new("RGBA", (TILE_SIZE, TILE_SIZE), color)
    if noise:
        import random; rng = random.Random(sum(color))
        px = img.load()
        for y in range(TILE_SIZE):
            for x in range(TILE_SIZE):
                r, g, b, a = color
                d = rng.randint(-12, 12)
                px[x, y] = (max(0, min(255, r+d)), max(0, min(255, g+d)), max(0, min(255, b+d)), a)
    return img

def save(name: str, img: Image.Image) -> None:
    img.save(OUT / f"{name}.png")

# Ground tiles
save("grass_plain",   solid((76, 153, 0, 255),   noise=True))
save("grass_flowers", solid((102, 179, 51, 255),  noise=True))
save("dirt_path",     solid((139, 115, 85, 255),  noise=True))
save("water_deep",    solid((0, 105, 148, 255),   noise=True))
save("water_shallow", solid((64, 164, 223, 255),  noise=True))
save("forest_floor",  solid((34, 85, 34, 255),    noise=True))
save("stone_floor",   solid((120, 120, 120, 255), noise=True))
save("stone_wall",    solid((80, 80, 80, 255),    noise=True))
save("sand_shore",    solid((210, 180, 140, 255), noise=True))
save("mountain_peak", solid((180, 180, 195, 255), noise=True))
save("void_tile",     solid((10, 10, 10, 255)))

# Forest canopy — dark green with lighter top circle
def forest_canopy() -> Image.Image:
    img = solid((34, 85, 34, 255))
    d = ImageDraw.Draw(img)
    d.ellipse([6, 2, 26, 22], fill=(60, 130, 40, 255))
    d.ellipse([10, 5, 22, 18], fill=(80, 160, 50, 255))
    return img
save("forest_canopy", forest_canopy())

# Entity sprites
def humanoid(r: int, g: int, b: int) -> Image.Image:
    img = Image.new("RGBA", (TILE_SIZE, TILE_SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([12, 2, 20, 10], fill=(255, 220, 185, 255))   # head
    d.rectangle([11, 10, 21, 22], fill=(r, g, b, 255))       # body
    d.rectangle([8, 10, 12, 22], fill=(r, g, b, 255))        # left arm
    d.rectangle([20, 10, 24, 22], fill=(r, g, b, 255))       # right arm
    d.rectangle([11, 22, 15, 30], fill=(80, 60, 40, 255))    # left leg
    d.rectangle([17, 22, 21, 30], fill=(80, 60, 40, 255))    # right leg
    return img

save("human_idle",    humanoid(100, 140, 200))
save("scholar_idle",  humanoid(180, 100, 200))
save("guardian_idle", humanoid(200, 80,  80))

# Tree object
def tree_obj() -> Image.Image:
    img = Image.new("RGBA", (TILE_SIZE, TILE_SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle([14, 20, 18, 30], fill=(101, 67, 33, 255))  # trunk
    d.polygon([(16, 2), (5, 16), (27, 16)], fill=(34, 120, 34, 255))  # canopy
    d.polygon([(16, 8), (7, 20), (25, 20)], fill=(50, 150, 50, 255))
    return img
save("tree_obj", tree_obj())

# Rock object
def rock_obj() -> Image.Image:
    img = Image.new("RGBA", (TILE_SIZE, TILE_SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([5, 12, 27, 28], fill=(130, 130, 130, 255))
    d.ellipse([8, 10, 24, 22], fill=(160, 160, 165, 255))
    return img
save("rock_obj", rock_obj())

# Ruins object
def ruins_obj() -> Image.Image:
    img = Image.new("RGBA", (TILE_SIZE, TILE_SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle([4, 18, 12, 30], fill=(100, 90, 80, 255))
    d.rectangle([20, 14, 28, 30], fill=(100, 90, 80, 255))
    d.rectangle([4, 8, 12, 14], fill=(80, 70, 60, 255))
    return img
save("ruins_obj", ruins_obj())

print(f"Generated {len(list(OUT.glob('*.png')))} sprites in {OUT}")
