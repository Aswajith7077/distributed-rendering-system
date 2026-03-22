"""
benchmark.py — Performance Evaluation Script
=============================================
Parallel & Distributed Computing — Semester Project
-----------------------------------------------------

Runs the tile-rendering pipeline across increasing worker counts,
measures wall-clock time, and produces:

  1. A CSV results file  →  output/benchmark_results.csv
  2. Three matplotlib plots saved to output/plots/:
       - speedup.png      : Empirical vs. Ideal vs. Amdahl speedup curves
       - efficiency.png   : Parallel efficiency vs. worker count
       - time.png         : Render time vs. worker count

Metrics reported:
  - Speedup      S(p) = T(1) / T(p)
  - Efficiency   E(p) = S(p) / p
  - Overhead     O(p) = p * T(p) - T(1)

Amdahl's Law overlay:
  S_amdahl(p) = 1 / (f_s + (1 - f_s) / p)
  where f_s  = estimated serial fraction (fit from data)

Usage:
    python benchmark.py [--resolution {hd|4k|custom}]
                        [--workers 1 2 4 8]
                        [--rows R] [--cols C]
                        [--serial-fraction F]
                        [--repeats N]
"""

import argparse
import csv
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

from coordinator import run_render

# ---------------------------------------------------------------------------
# Default experiment configuration
# ---------------------------------------------------------------------------

PRESETS = {
    "hd": {"image_w": 960, "image_h": 540},
    "fhd": {"image_w": 1920, "image_h": 1080},
    "4k": {"image_w": 3840, "image_h": 2160},
}

DEFAULT_WORKERS = [1, 2, 4, 8, 16]
DEFAULT_ROWS = 4
DEFAULT_COLS = 4
DEFAULT_SERIAL_F = 0.05  # assumed serial fraction for Amdahl overlay
DEFAULT_REPEATS = 1  # increase to 3+ for statistical averaging


# ---------------------------------------------------------------------------
# Amdahl's Law
# ---------------------------------------------------------------------------


def amdahl_speedup(p: int, serial_fraction: float) -> float:
    """
    Theoretical upper-bound speedup for p processors given a serial fraction.
        S(p) = 1 / (f_s + (1 - f_s) / p)
    """
    if p == 0:
        return 0.0
    return 1.0 / (serial_fraction + (1.0 - serial_fraction) / p)


# ---------------------------------------------------------------------------
# Experiment runner
# ---------------------------------------------------------------------------


def run_experiments(
    worker_counts: list[int],
    image_w: int,
    image_h: int,
    rows: int,
    cols: int,
    repeats: int,
    serial_fraction: float,
) -> list[dict]:
    """
    Executes the rendering pipeline for each worker count (repeated `repeats` times).
    Returns a list of result dicts sorted by worker count.
    """
    print("\n" + "=" * 65)
    print("  DISTRIBUTED RENDERING — BENCHMARK")
    print("=" * 65)
    print(f"  Resolution   : {image_w} × {image_h} px")
    print(f"  Tile grid    : {rows} × {cols}  →  {rows * cols} tiles")
    print(f"  Worker sweep : {worker_counts}")
    print(f"  Repeats      : {repeats} per configuration")
    print(f"  Serial frac  : {serial_fraction:.2f}  (Amdahl overlay)")
    print("=" * 65 + "\n")

    results = []

    for n_workers in worker_counts:
        times = []
        for rep in range(repeats):
            tag = f"[workers={n_workers:2d}  rep={rep + 1}/{repeats}]"
            print(f"  {tag}  running ...", end="", flush=True)
            t0 = time.perf_counter()
            run_render(
                workers_override=n_workers,
                rows_override=rows,
                cols_override=cols,
                verbose=False,
            )
            elapsed = time.perf_counter() - t0
            times.append(elapsed)
            print(f"  {elapsed:.2f}s")

        mean_t = statistics.mean(times)
        results.append(
            {
                "workers": n_workers,
                "time_mean": mean_t,
                "time_min": min(times),
                "time_max": max(times),
                "tiles": rows * cols,
            }
        )

    # Compute derived metrics relative to baseline (1 worker)
    baseline = results[0]["time_mean"]
    for r in results:
        p = r["workers"]
        s = baseline / r["time_mean"]
        r["speedup"] = s
        r["efficiency"] = s / p * 100.0
        r["overhead_s"] = p * r["time_mean"] - baseline
        r["amdahl"] = amdahl_speedup(p, serial_fraction)

    return results


# ---------------------------------------------------------------------------
# Results table
# ---------------------------------------------------------------------------


def print_results_table(results: list[dict]) -> None:
    print("\n" + "=" * 75)
    print("  RESULTS TABLE")
    print("=" * 75)
    hdr = f"  {'Workers':>8}  {'Time (s)':>10}  {'Speedup':>10}  {'Efficiency':>12}  {'Overhead (s)':>14}"
    print(hdr)
    print("  " + "-" * 61)
    for r in results:
        print(
            f"  {r['workers']:>8}  {r['time_mean']:>10.2f}  "
            f"{r['speedup']:>10.2f}x  {r['efficiency']:>10.1f}%  "
            f"{r['overhead_s']:>14.2f}"
        )
    print("=" * 75)


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------


def save_csv(results: list[dict], path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fieldnames = [
        "workers",
        "time_mean",
        "time_min",
        "time_max",
        "speedup",
        "efficiency",
        "overhead_s",
        "amdahl",
        "tiles",
    ]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow({k: r[k] for k in fieldnames})
    print(f"\n  [CSV] Results saved → {path}")


# ---------------------------------------------------------------------------
# Matplotlib plots
# ---------------------------------------------------------------------------


def save_plots(results: list[dict], plots_dir: str) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")  # headless — no display needed
        import matplotlib.pyplot as plt
        import matplotlib.ticker as ticker
    except ImportError:
        print(
            "\n  [WARN] matplotlib not installed — skipping plots.\n"
            "         Run:  pip install matplotlib"
        )
        return

    os.makedirs(plots_dir, exist_ok=True)
    workers = [r["workers"] for r in results]
    speedups = [r["speedup"] for r in results]
    effs = [r["efficiency"] for r in results]
    times = [r["time_mean"] for r in results]
    amdahls = [r["amdahl"] for r in results]

    STYLE = {
        "empirical": dict(
            color="#4C72B0",
            marker="o",
            linewidth=2.2,
            markersize=7,
            label="Empirical speedup",
        ),
        "ideal": dict(
            color="#55A868",
            marker="",
            linewidth=1.6,
            linestyle="--",
            label="Ideal (linear)",
        ),
        "amdahl": dict(
            color="#C44E52",
            marker="",
            linewidth=1.6,
            linestyle=":",
            label="Amdahl's Law",
        ),
        "eff": dict(
            color="#DD8452",
            marker="s",
            linewidth=2.2,
            markersize=7,
            label="Parallel efficiency",
        ),
        "time": dict(
            color="#4C72B0",
            marker="o",
            linewidth=2.2,
            markersize=7,
            label="Render time",
        ),
    }

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.alpha": 0.35,
        }
    )

    # --- Plot 1: Speedup ---
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(workers, speedups, **STYLE["empirical"])
    ax.plot(workers, workers, **STYLE["ideal"])
    ax.plot(workers, amdahls, **STYLE["amdahl"])
    ax.set_xlabel("Number of workers (p)")
    ax.set_ylabel("Speedup  S(p) = T(1) / T(p)")
    ax.set_title(
        "Speedup vs. Worker Count\n(Distributed Tile Rendering)",
        fontsize=13,
        fontweight="bold",
    )
    ax.xaxis.set_major_locator(ticker.FixedLocator(workers))
    ax.legend(framealpha=0.8)
    fig.tight_layout()
    p1 = os.path.join(plots_dir, "speedup.png")
    fig.savefig(p1, dpi=150)
    plt.close(fig)
    print(f"  [PLT] Speedup plot   → {p1}")

    # --- Plot 2: Efficiency ---
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(workers, effs, **STYLE["eff"])
    ax.axhline(
        100, color="#55A868", linestyle="--", linewidth=1.4, label="Ideal (100%)"
    )
    ax.set_xlabel("Number of workers (p)")
    ax.set_ylabel("Parallel efficiency  E(p) = S(p) / p  [%]")
    ax.set_title(
        "Parallel Efficiency vs. Worker Count\n(Distributed Tile Rendering)",
        fontsize=13,
        fontweight="bold",
    )
    ax.set_ylim(0, 115)
    ax.xaxis.set_major_locator(ticker.FixedLocator(workers))
    ax.legend(framealpha=0.8)
    fig.tight_layout()
    p2 = os.path.join(plots_dir, "efficiency.png")
    fig.savefig(p2, dpi=150)
    plt.close(fig)
    print(f"  [PLT] Efficiency plot → {p2}")

    # --- Plot 3: Wall-clock time ---
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(workers, times, **STYLE["time"])
    ax.fill_between(workers, times, alpha=0.12, color="#4C72B0")
    ax.set_xlabel("Number of workers (p)")
    ax.set_ylabel("Render time  T(p)  [seconds]")
    ax.set_title(
        "Render Time vs. Worker Count\n(Distributed Tile Rendering)",
        fontsize=13,
        fontweight="bold",
    )
    ax.xaxis.set_major_locator(ticker.FixedLocator(workers))
    ax.legend(framealpha=0.8)
    fig.tight_layout()
    p3 = os.path.join(plots_dir, "time.png")
    fig.savefig(p3, dpi=150)
    plt.close(fig)
    print(f"  [PLT] Time plot      → {p3}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args():
    parser = argparse.ArgumentParser(
        description="Benchmark: distributed tile rendering scalability analysis"
    )
    parser.add_argument(
        "--resolution",
        choices=["hd", "fhd", "4k"],
        default="hd",
        help="Image size preset (hd=960×540, fhd=1920×1080, 4k=3840×2160). Default: hd",
    )
    parser.add_argument(
        "--workers",
        type=int,
        nargs="+",
        default=DEFAULT_WORKERS,
        metavar="N",
        help="Worker counts to test. Default: 1 2 4 8 16",
    )
    parser.add_argument("--rows", type=int, default=DEFAULT_ROWS, help="Tile grid rows")
    parser.add_argument("--cols", type=int, default=DEFAULT_COLS, help="Tile grid cols")
    parser.add_argument(
        "--serial-fraction",
        type=float,
        default=DEFAULT_SERIAL_F,
        help=f"Assumed serial fraction for Amdahl overlay [0–1]. Default: {DEFAULT_SERIAL_F}",
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=DEFAULT_REPEATS,
        help=f"Repetitions per worker count (results averaged). Default: {DEFAULT_REPEATS}",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    preset = PRESETS[args.resolution]

    results = run_experiments(
        worker_counts=sorted(set(args.workers)),
        image_w=preset["image_w"],
        image_h=preset["image_h"],
        rows=args.rows,
        cols=args.cols,
        repeats=args.repeats,
        serial_fraction=args.serial_fraction,
    )

    print_results_table(results)
    save_csv(results, "output/benchmark_results.csv")
    save_plots(results, "output/plots")

    print("\n  Done. Check output/plots/ for speedup, efficiency, and time graphs.")
    print("")


if __name__ == "__main__":
    main()
