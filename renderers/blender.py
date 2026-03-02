"""
renderers/blender.py — Blender Headless Tile Renderer
=====================================================
Renders tiles by calling Blender in headless mode (blender -b) with
border/crop parameters.  Each tile maps to a region of the full frame.

Blender border coordinates are normalised to [0.0, 1.0]:
    border_min_x = tile.x / img_width
    border_max_x = (tile.x + tile.width) / img_width
    border_min_y = 1.0 - (tile.y + tile.height) / img_height   (Blender Y is flipped)
    border_max_y = 1.0 - tile.y / img_height

Requirements:
    - Blender installed (headless mode, no GPU required for EEVEE)
    - A .blend scene file
"""

import os
import subprocess
import sys
import time

from .base import TileRenderer


# Common install paths to try if user doesn't specify one
_DEFAULT_PATHS_WIN = [
    r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 4.1\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 4.0\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 3.6\blender.exe",
]

_DEFAULT_PATHS_UNIX = [
    "/usr/bin/blender",
    "/usr/local/bin/blender",
    "/snap/bin/blender",
]


def find_blender() -> str | None:
    """Auto-detect the Blender executable path."""
    paths = _DEFAULT_PATHS_WIN if sys.platform == "win32" else _DEFAULT_PATHS_UNIX
    for p in paths:
        if os.path.isfile(p):
            return p
    return None


class BlenderRenderer(TileRenderer):
    """
    Renders tiles using Blender's headless CLI.

    Config keys (passed via workflow.json → renderer_config):
        blender_path : str   — path to blender executable (auto-detected if omitted)
        scene_file   : str   — path to .blend file (REQUIRED)
        engine       : str   — render engine: "CYCLES" | "BLENDER_EEVEE_NEXT" (default: CYCLES)
        samples      : int   — render samples (default: 128)
        device       : str   — compute device: "CPU" | "GPU" (default: CPU)
    """

    def __init__(self, config: dict):
        self.scene_file = config.get("scene_file")
        if not self.scene_file:
            raise ValueError(
                "BlenderRenderer requires 'scene_file' in renderer config. "
                "Set it in workflow.json under renderer.scene_file."
            )
        if not os.path.isfile(self.scene_file):
            raise FileNotFoundError(f"Blender scene file not found: {self.scene_file}")

        self.blender_path = config.get("blender_path") or find_blender()
        if not self.blender_path or not os.path.isfile(self.blender_path):
            raise FileNotFoundError(
                "Blender executable not found. Set 'blender_path' in "
                "workflow.json or install Blender to a standard location."
            )

        self.engine = config.get("engine", "CYCLES")
        self.samples = config.get("samples", 128)
        self.device = config.get("device", "CPU")

    def _build_python_expr(
        self, tile: dict, img_width: int, img_height: int, output_path: str
    ) -> str:
        """
        Build the Python expression that Blender will execute to configure
        border rendering and output path.

        Blender's Y-axis is flipped relative to image coordinates:
            image (0,0) = top-left    →   Blender (0,0) = bottom-left
        """
        # Normalise pixel coords to [0, 1]
        min_x = tile["x"] / img_width
        max_x = (tile["x"] + tile["width"]) / img_width
        # Flip Y axis
        min_y = 1.0 - (tile["y"] + tile["height"]) / img_height
        max_y = 1.0 - tile["y"] / img_height

        # Use forward slashes in path for Blender Python compatibility
        out_path_escaped = output_path.replace("\\", "/")

        expr = (
            "import bpy; "
            "s = bpy.context.scene; "
            f"s.render.engine = '{self.engine}'; "
            f"s.render.filepath = '{out_path_escaped}'; "
            f"s.render.resolution_x = {tile['width']}; "
            f"s.render.resolution_y = {tile['height']}; "
            "s.render.resolution_percentage = 100; "
            "s.render.use_border = True; "
            "s.render.use_crop_to_border = True; "
            f"s.render.border_min_x = {min_x:.6f}; "
            f"s.render.border_max_x = {max_x:.6f}; "
            f"s.render.border_min_y = {min_y:.6f}; "
            f"s.render.border_max_y = {max_y:.6f}; "
        )

        if self.engine == "CYCLES":
            expr += (
                f"s.cycles.samples = {self.samples}; "
                f"s.cycles.device = '{self.device}'; "
            )
        elif self.engine == "BLENDER_EEVEE_NEXT":
            expr += f"s.eevee.taa_render_samples = {self.samples}; "

        return expr

    def render_tile(
        self,
        tile: dict,
        img_width: int,
        img_height: int,
        tiles_dir: str,
        **kwargs,
    ) -> dict:
        t_start = time.perf_counter()

        output_path = self._tile_path(tile, tiles_dir)

        # Build Blender CLI command
        python_expr = self._build_python_expr(tile, img_width, img_height, output_path)

        scene_path = os.path.abspath(self.scene_file)

        cmd = [
            self.blender_path,
            "-b",
            scene_path,  # headless / background mode
            "--python-expr",
            python_expr,  # configure border + output
            "-f",
            "1",  # render frame 1
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout per tile
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"Blender render failed for tile {tile['id']}.\n"
                f"STDERR: {result.stderr[-500:]}\n"
                f"CMD: {' '.join(cmd)}"
            )

        # Blender appends frame number to output path: output0001.png
        # We need to find the actual rendered file and rename it
        expected_blender_output = output_path + "0001.png"
        if os.path.isfile(expected_blender_output):
            # Rename to our standard tile path
            if os.path.isfile(output_path):
                os.remove(output_path)
            os.rename(expected_blender_output, output_path)
        elif not os.path.isfile(output_path):
            # Try common Blender naming patterns
            base, ext = os.path.splitext(output_path)
            for suffix in ["0001.png", "0001.exr", ".png", ""]:
                candidate = base + suffix
                if os.path.isfile(candidate) and candidate != output_path:
                    os.rename(candidate, output_path)
                    break
            else:
                raise FileNotFoundError(
                    f"Blender did not produce expected output for tile {tile['id']}. "
                    f"Expected: {output_path}\n"
                    f"STDOUT: {result.stdout[-500:]}"
                )

        return self._make_result(tile, output_path, t_start)
