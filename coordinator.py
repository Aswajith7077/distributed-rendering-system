"""
Coordinator (Master Node)
--------------------------
Mimics the BigEarth platform's Planner + Executor.

Execution pipeline:
  1. Read workflow.json  (Workflow Parser)
  2. frame_split operator  → list of tile descriptors
  3. for-each (parallel)   → spawn N worker processes, one per tile
  4. stitch operator       → assemble tiles into final image

Usage:
    python coordinator.py [--workers N] [--rows R] [--cols C]
"""

import json
import os
import time
import argparse
import shutil
from multiprocessing import Pool

from operators.frame_split import split
from operators.stitch import stitch
import worker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_workflow(path: str = "workflow.json") -> dict:
    with open(path, "r") as f:
        return json.load(f)


def print_banner(title: str) -> None:
    w = 60
    print("\n" + "=" * w)
    print(f"  {title}")
    print("=" * w)


def print_pipeline(wf: dict) -> None:
    print("\n📋 Workflow Pipeline:")
    for i, op in enumerate(wf["pipeline"], 1):
        parallel_tag = "  ← parallel (for-each)" if op.get("parallel") else ""
        print(f"   Step {i}: [{op['operator']}]{parallel_tag}")


# ---------------------------------------------------------------------------
# Main render function
# ---------------------------------------------------------------------------


def run_render(
    workflow_path: str = "workflow.json",
    workers_override: int | None = None,
    rows_override: int | None = None,
    cols_override: int | None = None,
    verbose: bool = True,
) -> dict:
    """
    Executes the full rendering pipeline and returns a result dict.
    """
    wf = load_workflow(workflow_path)

    img_w = wf["image"]["width"]
    img_h = wf["image"]["height"]
    rows = rows_override or wf["tiles"]["rows"]
    cols = cols_override or wf["tiles"]["cols"]
    n_workers = workers_override or wf["workers"]
    output_path = wf["output"]

    tiles_dir = os.path.join(os.path.dirname(output_path), "tiles")

    # Clean up old tile files
    if os.path.exists(tiles_dir):
        shutil.rmtree(tiles_dir)

    if verbose:
        print_banner("Distributed Rendering Coordinator")
        print_pipeline(wf)
        print(f"\n🖼️  Image      : {img_w} × {img_h} px")
        print(f"🔲 Tile grid  : {rows} rows × {cols} cols  →  {rows * cols} tiles")
        print(f"⚙️  Workers    : {n_workers}")

    # ------------------------------------------------------------------
    # STEP 1 — Frame Split Operator
    # ------------------------------------------------------------------
    if verbose:
        print("\n[Step 1] frame_split → computing tile descriptors ...")
    tiles = split(img_w, img_h, rows, cols)

    # ------------------------------------------------------------------
    # STEP 2 — Parallel Render (for-each)
    # ------------------------------------------------------------------
    if verbose:
        print(
            f"[Step 2] render     → dispatching {len(tiles)} tile tasks "
            f"across {n_workers} worker(s) ..."
        )

    args = [(t, img_w, img_h, tiles_dir) for t in tiles]

    t_render_start = time.perf_counter()

    if n_workers == 1:
        # Single-worker baseline — no Pool overhead
        tile_results = [worker.run(a) for a in args]
    else:
        with Pool(processes=n_workers) as pool:
            tile_results = pool.map(worker.run, args)

    t_render_end = time.perf_counter()
    render_time = t_render_end - t_render_start

    # ------------------------------------------------------------------
    # STEP 3 — Stitch Operator
    # ------------------------------------------------------------------
    if verbose:
        print(f"[Step 3] stitch     → assembling {len(tile_results)} tiles ...")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    stitch(tile_results, img_w, img_h, output_path)

    if verbose:
        print(f"\n✅ Done!  Output: {output_path}")
        print(
            f"   Render time : {render_time:.2f}s  "
            f"(tiles: {len(tiles)}, workers: {n_workers})"
        )

    return {
        "workers": n_workers,
        "tiles": len(tiles),
        "render_time_s": render_time,
        "output": output_path,
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="BigEarth-style distributed tile renderer"
    )
    parser.add_argument(
        "--workers", type=int, default=None, help="Number of parallel worker processes"
    )
    parser.add_argument("--rows", type=int, default=None, help="Tile grid rows")
    parser.add_argument("--cols", type=int, default=None, help="Tile grid columns")
    parser.add_argument(
        "--workflow", type=str, default="workflow.json", help="Path to workflow JSON"
    )
    args = parser.parse_args()

    result = run_render(
        workflow_path=args.workflow,
        workers_override=args.workers,
        rows_override=args.rows,
        cols_override=args.cols,
        verbose=True,
    )
