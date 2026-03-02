"""
renderers/base.py — Abstract Tile Renderer Interface
=====================================================
Defines the contract that all renderer backends must implement.
"""

import os
import time
from abc import ABC, abstractmethod


class TileRenderer(ABC):
    """
    Base class for tile renderer backends.

    Every renderer must implement `render_tile()` which takes a tile
    descriptor and produces a PNG image file for that tile region.
    """

    @abstractmethod
    def render_tile(
        self,
        tile: dict,
        img_width: int,
        img_height: int,
        tiles_dir: str,
        **kwargs,
    ) -> dict:
        """
        Render a single tile and save it as a PNG.

        Args:
            tile:       Dict with keys: id, x, y, width, height
            img_width:  Full image width in pixels
            img_height: Full image height in pixels
            tiles_dir:  Directory to write tile PNG files into

        Returns:
            Dict with keys: id, x, y, path, duration_s
        """

    def _make_result(self, tile: dict, path: str, t_start: float) -> dict:
        """Helper to build a standard result dict."""
        return {
            "id": tile["id"],
            "x": tile["x"],
            "y": tile["y"],
            "path": path,
            "duration_s": time.perf_counter() - t_start,
        }

    @staticmethod
    def _tile_path(tile: dict, tiles_dir: str) -> str:
        """Standard tile output path."""
        os.makedirs(tiles_dir, exist_ok=True)
        return os.path.join(tiles_dir, f"tile_{tile['id']:04d}.png")
