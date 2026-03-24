"""
Worker Node
-----------
Each worker receives a tile descriptor and independently renders its tile.

Supports two modes:
  1. Legacy mode:  render_tile() uses the built-in synthetic renderer
  2. Backend mode: render_tile_with_backend() uses the pluggable renderer API

The legacy interface is kept for backward compatibility with existing code
that calls worker.run() directly.
"""

import os
import time
import math
from PIL import Image
import redis
import json
import socket


# ---------------------------------------------------------------------------
# Synthetic renderer — simulates costly per-pixel computation (LEGACY)
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
    Renders a single tile using the built-in synthetic renderer.
    (Legacy interface — kept for backward compat with run_demo.py/benchmark.py)
    """
    t_start = time.perf_counter()

    tile_img = Image.new("RGB", (tile["width"], tile["height"]))
    pixels = tile_img.load()

    for py in range(tile["height"]):
        for px in range(tile["width"]):
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
# Backend-aware renderer
# ---------------------------------------------------------------------------


def render_tile_with_backend(
    tile: dict,
    img_width: int,
    img_height: int,
    tiles_dir: str,
    renderer,
) -> dict:
    """
    Renders a tile using the pluggable renderer backend.

    Args:
        tile:       Tile descriptor dict
        img_width:  Full image width
        img_height: Full image height
        tiles_dir:  Output directory for tile PNGs
        renderer:   A TileRenderer instance (from renderers package)

    Returns:
        Dict with: id, x, y, path, duration_s
    """
    return renderer.render_tile(tile, img_width, img_height, tiles_dir)


# ---------------------------------------------------------------------------
# Entry points used by coordinator / scheduler via multiprocessing
# ---------------------------------------------------------------------------


def run(args: tuple) -> dict:
    """
    Unpacks args tuple and calls the appropriate renderer.

    Supports two arg formats:
        (tile, img_w, img_h, tiles_dir)               → legacy synthetic
        (tile, img_w, img_h, tiles_dir, renderer_cfg)  → pluggable backend
    """
    if len(args) == 5:
        tile, img_width, img_height, tiles_dir, renderer_cfg = args
        from renderers import get_renderer

        renderer = get_renderer(renderer_cfg)
        return render_tile_with_backend(
            tile, img_width, img_height, tiles_dir, renderer
        )
    else:
        tile, img_width, img_height, tiles_dir = args
        return render_tile(tile, img_width, img_height, tiles_dir)


# ---------------------------------------------------------------------------
# Distributed Worker Loop (Redis-based)
# ---------------------------------------------------------------------------



# def start_worker(redis_host="localhost", redis_port=6379):
#     """
#     Distributed worker loop:
#     - Pulls tasks from Redis queue
#     - Executes using existing run()
#     - Reports completion
#     """
#     r = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)

#     worker_id = socket.gethostname()
#     print(f"[Worker {worker_id}] Started. Waiting for tasks...")

#     while True:
#         task_data = r.brpop("render_queue")  # blocking pop

#         if not task_data:
#             continue

#         _, payload = task_data

#         try:
#             task = json.loads(payload)

#             args = task["args"]
#             job_id = task["job_id"]

#             print(f"[Worker {worker_id}] Processing tile {args[0]['id']}")

#             result = run(tuple(args))  # 🔥 reuse your existing logic

#             # mark completion
#             r.rpush(f"job:{job_id}:results", json.dumps(result))
#             r.incr(f"job:{job_id}:done")

#             print(f"[Worker {worker_id}] Done tile {args[0]['id']}")

#         except Exception as e:
#             print(f"[Worker {worker_id}] Error: {e}")


# if __name__ == "__main__":
#     start_worker()