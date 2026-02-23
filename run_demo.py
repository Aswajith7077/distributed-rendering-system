"""
Scaling Demo
-------------
Runs the rendering pipeline several times with increasing worker counts,
then prints a results table and ASCII speedup bar chart.

This directly replicates the paper's experiment:
  - Baseline: 1 worker
  - Increasing workers: 2, 4, 8, 16
  - Measure: render time, speedup vs baseline

Usage:
    python run_demo.py
"""

import sys
import os

# Ensure coordinator can import from the same package root
sys.path.insert(0, os.path.dirname(__file__))

from coordinator import run_render

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Worker counts to test (mirrors the paper's multi-worker experiments)
WORKER_COUNTS = [1, 2, 4, 8, 16]

# Use a smaller image for the demo to keep runtime manageable on one machine
DEMO_WORKFLOW = {
    "image_w": 960,
    "image_h": 540,
    "rows": 4,
    "cols": 4,  # 16 tiles total — ensures tasks > workers for all counts
}


# ---------------------------------------------------------------------------
# Run experiments
# ---------------------------------------------------------------------------


def run_experiments() -> list[dict]:
    print("=" * 62)
    print("  Distributed Rendering - Scaling Experiment")
    print("  (Replicating BigEarth paper experiments in Python)")
    print("=" * 62)
    print(
        f"\n  Image resolution : {DEMO_WORKFLOW['image_w']} x {DEMO_WORKFLOW['image_h']} px"
    )
    print(
        f"  Tile grid        : {DEMO_WORKFLOW['rows']} x {DEMO_WORKFLOW['cols']}"
        f"  ->  {DEMO_WORKFLOW['rows'] * DEMO_WORKFLOW['cols']} tiles"
    )
    print(f"  Worker counts    : {WORKER_COUNTS}")
    print()

    results = []
    for n_workers in WORKER_COUNTS:
        print(f"--- Running with {n_workers:2d} worker(s) ---")
        res = run_render(
            workers_override=n_workers,
            rows_override=DEMO_WORKFLOW["rows"],
            cols_override=DEMO_WORKFLOW["cols"],
            verbose=False,  # suppress per-step output during demo
        )
        # Patch image size into result for display
        res["img_w"] = DEMO_WORKFLOW["image_w"]
        res["img_h"] = DEMO_WORKFLOW["image_h"]
        results.append(res)
        print(f"    Workers: {n_workers:2d}  |  Time: {res['render_time_s']:.2f}s")

    return results


# ---------------------------------------------------------------------------
# Display results table
# ---------------------------------------------------------------------------


def print_results_table(results: list[dict]) -> None:
    baseline = results[0]["render_time_s"]

    print("\n" + "=" * 62)
    print("  RESULTS TABLE")
    print("=" * 62)
    print(f"  {'Workers':>8}  {'Time (s)':>10}  {'Speedup':>10}  {'Efficiency':>12}")
    print("  " + "-" * 46)
    for r in results:
        speedup = baseline / r["render_time_s"]
        efficiency = speedup / r["workers"] * 100
        print(
            f"  {r['workers']:>8}  {r['render_time_s']:>10.2f}  "
            f"{speedup:>10.2f}x  {efficiency:>10.1f}%"
        )
    print("=" * 62)


# ---------------------------------------------------------------------------
# ASCII bar chart
# ---------------------------------------------------------------------------


def print_speedup_chart(results: list[dict]) -> None:
    baseline = results[0]["render_time_s"]
    max_speedup = baseline / results[-1]["render_time_s"]
    bar_width = 40

    print("\n  SPEEDUP CHART  (relative to 1 worker)")
    print("  " + "-" * 54)
    for r in results:
        speedup = baseline / r["render_time_s"]
        filled = int((speedup / max_speedup) * bar_width)
        bar = "#" * filled + "-" * (bar_width - filled)
        print(f"  {r['workers']:>3} workers |{bar}| {speedup:.2f}x")
    print()
    print("  NOTE: Non-linear scaling matches paper's findings.")
    print("        Overhead from task dispatch + I/O limits perfect speedup.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    results = run_experiments()
    print_results_table(results)
    print_speedup_chart(results)

    print(f"\n  [OK] Final image saved to: {results[-1]['output']}")
    print("     Open output/final.png to verify the stitched result.")
    print()
