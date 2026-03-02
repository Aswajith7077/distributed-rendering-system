"""
manage.py — Unified CLI Entry Point
====================================
Parallel & Distributed Computing — Semester Project

Runs the distributed tile rendering pipeline using either:
  - coordinator : static scheduling via Pool.map
  - scheduler   : dynamic scheduling via pull-based work queue

Usage:
    python manage.py coordinator [--workers N] [--rows R] [--cols C]
    python manage.py scheduler   [--workers N] [--rows R] [--cols C]
"""

import argparse
import multiprocessing as mp

from managers.coordinator import Coordinator
from managers.scheduler import Scheduler


MODES = {
    "coordinator": Coordinator,
    "scheduler": Scheduler,
}


def main():
    parser = argparse.ArgumentParser(
        description="Distributed tile renderer — choose scheduling strategy"
    )
    parser.add_argument(
        "mode",
        choices=MODES.keys(),
        help="Scheduling strategy: 'coordinator' (static Pool.map) or 'scheduler' (dynamic Queue)",
    )
    parser.add_argument(
        "--workers", type=int, default=None, help="Number of parallel worker processes"
    )
    parser.add_argument("--rows", type=int, default=None, help="Tile grid rows")
    parser.add_argument("--cols", type=int, default=None, help="Tile grid columns")
    parser.add_argument(
        "--workflow", type=str, default="workflow.json", help="Path to workflow JSON"
    )
    parser.add_argument(
        "--verbose", action="store_true", default=True, help="Print progress output"
    )
    args = parser.parse_args()

    # Required on Windows for multiprocessing
    mp.freeze_support()

    # Instantiate the chosen manager and run
    manager_cls = MODES[args.mode]
    manager = manager_cls(args.workflow)

    manager.run_render(
        workers_override=args.workers,
        rows_override=args.rows,
        cols_override=args.cols,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    main()
