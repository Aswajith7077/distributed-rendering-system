"""
Worker Node
-----------
Mimics a "worker VM" from the BigEarth paper.
Each worker receives a tile descriptor and independently renders its tile.

The renderer simulates a computationally expensive per-pixel operation
(procedural gradient + noise pattern) without requiring Blender or a GPU.
This demonstrates that each tile is independently renderable — the core
principle of data parallelism in sort-last distributed rendering.
"""

import os
import time
import math
from PIL import Image


# ---------------------------------------------------------------------------
# Synthetic renderer — simulates costly per-pixel computation
# ---------------------------------------------------------------------------


def _compute_pixel(x: int, y: int, img_w: int, img_h: int) -> tuple[int, int, int]:
    """
    Produces a deterministic RGB value for pixel (x, y) in an image of
    size (img_w × img_h).  The pattern is a smooth gradient overlaid with
    a sine-based interference pattern — visually interesting and cheap to
    verify (same pixel always gives same colour regardless of which worker
    computed it).
    """
    # Normalise coords to [0, 1]
    nx = x / img_w
    ny = y / img_h

    # Primary gradient (top-left: deep blue → bottom-right: warm orange)
    r = int(nx * 200 + 55)
    g = int((1 - ny) * 120 + 30)
    b = int((1 - nx) * 220 + 35)

    # Sine-wave interference overlay (gives a "wave" pattern)
    wave = math.sin(nx * math.pi * 8) * math.cos(ny * math.pi * 6)
    offset = int(wave * 30)

    r = max(0, min(255, r + offset))
    g = max(0, min(255, g - offset))
    b = max(0, min(255, b + offset // 2))

    return (r, g, b)


def render_tile(tile: dict, img_width: int, img_height: int, tiles_dir: str) -> dict:
    """
    Renders a single tile and saves it as a PNG.

    Args:
        tile:       Dict with keys: id, x, y, width, height
        img_width:  Full image width (for normalised coordinate calculation)
        img_height: Full image height
        tiles_dir:  Directory to write tile PNG files into

    Returns:
        Dict with: id, x, y, path, duration_s
    """
    t_start = time.perf_counter()

    tile_img = Image.new("RGB", (tile["width"], tile["height"]))
    pixels = tile_img.load()

    for py in range(tile["height"]):
        for px in range(tile["width"]):
            # Global pixel coordinates
            gx = tile["x"] + px
            gy = tile["y"] + py
            pixels[px, py] = _compute_pixel(gx, gy, img_width, img_height)

    os.makedirs(tiles_dir, exist_ok=True)
    path = os.path.join(tiles_dir, f"tile_{tile['id']:04d}.png")
    tile_img.save(path)

    duration = time.perf_counter() - t_start
    return {
        "id": tile["id"],
        "x": tile["x"],
        "y": tile["y"],
        "path": path,
        "duration_s": duration,
    }


# ---------------------------------------------------------------------------
# Entry point used by coordinator via multiprocessing
# ---------------------------------------------------------------------------


def run(args: tuple) -> dict:
    """Unpacks args tuple and calls render_tile. Used as Pool worker target."""
    tile, img_width, img_height, tiles_dir = args
    return render_tile(tile, img_width, img_height, tiles_dir)
