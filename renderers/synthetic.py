"""
renderers/synthetic.py — Synthetic (Procedural) Tile Renderer
=============================================================
The original per-pixel gradient+sine renderer extracted into the
pluggable renderer interface.  No external dependencies beyond Pillow.
"""

import math
import time

from PIL import Image

from .base import TileRenderer


class SyntheticRenderer(TileRenderer):
    """
    Produces a deterministic gradient + sine-wave interference pattern.
    Useful for benchmarking and demos without needing Blender installed.
    """

    # ------------------------------------------------------------------ #
    # Per-pixel computation
    # ------------------------------------------------------------------ #

    @staticmethod
    def _compute_pixel(x: int, y: int, img_w: int, img_h: int) -> tuple[int, int, int]:
        nx = x / img_w
        ny = y / img_h

        r = int(nx * 200 + 55)
        g = int((1 - ny) * 120 + 30)
        b = int((1 - nx) * 220 + 35)

        wave = math.sin(nx * math.pi * 8) * math.cos(ny * math.pi * 6)
        offset = int(wave * 30)

        r = max(0, min(255, r + offset))
        g = max(0, min(255, g - offset))
        b = max(0, min(255, b + offset // 2))

        return (r, g, b)

    # ------------------------------------------------------------------ #
    # Interface implementation
    # ------------------------------------------------------------------ #

    def render_tile(
        self,
        tile: dict,
        img_width: int,
        img_height: int,
        tiles_dir: str,
        **kwargs,
    ) -> dict:
        t_start = time.perf_counter()

        tile_img = Image.new("RGB", (tile["width"], tile["height"]))
        pixels = tile_img.load()

        for py in range(tile["height"]):
            for px in range(tile["width"]):
                gx = tile["x"] + px
                gy = tile["y"] + py
                pixels[px, py] = self._compute_pixel(gx, gy, img_width, img_height)

        path = self._tile_path(tile, tiles_dir)
        tile_img.save(path)

        return self._make_result(tile, path, t_start)
