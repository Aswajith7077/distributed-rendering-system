import os
import time
from multiprocessing import Queue, Process

from operators.frame_split import split
from operators.stitch import stitch
import worker as worker_module
from managers.base_manager import BaseManager


class Scheduler(BaseManager):

    def __init__(self,workflow_path: str = "workflow.json"):
        super().__init__(workflow_path)
        self.task_queue = Queue()
        self.result_queue = Queue()
        self.SENTINEL = None



    def _dynamic_worker(
        self,
        img_w: int,
        img_h: int,
        tiles_dir: str,
        renderer_cfg: dict | None = None,
    ) -> None:
        """
        Worker process function for pull-based scheduling.

        Loop:
            1. Pull a tile descriptor from task_queue (blocks if empty)
            2. Render the tile
            3. Push result to result_queue
            4. Repeat until SENTINEL received

        The renderer is instantiated ONCE per worker process and reused
        for all tiles — avoids repeated Blender startup overhead.
        """
        # Instantiate renderer once for this process
        if renderer_cfg:
            from renderers import get_renderer

            renderer = get_renderer(renderer_cfg)
        else:
            renderer = None

        while True:
            tile = self.task_queue.get()
            if tile is self.SENTINEL:
                self.task_queue.put(self.SENTINEL)
                break
            if renderer is not None:
                result = worker_module.render_tile_with_backend(
                    tile, img_w, img_h, tiles_dir, renderer
                )
            else:
                result = worker_module.render_tile(tile, img_w, img_h, tiles_dir)
            self.result_queue.put(result)


    # ---------------------------------------------------------------------------
    # Dynamic scheduler — coordinator-side orchestration
    # ---------------------------------------------------------------------------


    def run_render_dynamic(
        self,
        tiles: list[dict],
        img_w: int,
        img_h: int,
        n_workers: int,
        tiles_dir: str,
        renderer_cfg: dict | None = None,
        verbose: bool = False,
    ) -> tuple[list[dict], float]:
        """
        Dispatches tiles using a shared multiprocessing.Queue.

        Args:
            tiles:      List of tile descriptor dicts from frame_split.
            img_w/h:    Full image dimensions.
            n_workers:  Number of parallel worker processes.
            tiles_dir:  Directory for tile PNG output.
            verbose:    Print per-tile completion messages.

        Returns:
            (tile_results, render_time_s)
        """
        # Populate task queue
        for tile in tiles:
            self.task_queue.put(tile)
        self.task_queue.put(self.SENTINEL)  # single sentinel — workers re-enqueue it

        processes = []
        for _ in range(n_workers):
            p = Process(
                target=self._dynamic_worker,
                args=(img_w, img_h, tiles_dir, renderer_cfg),
                daemon=True,
            )
            p.start()
            processes.append(p)

        t_start = time.perf_counter()

        # Collect results
        tile_results = []
        for _ in range(len(tiles)):
            result = self.result_queue.get()
            tile_results.append(result)
            if verbose:
                print(
                    f"    [dynamic] tile {result['id']:04d} done  ({result['duration_s']:.3f}s)"
                )

        # Wait for all workers to exit cleanly
        for p in processes:
            p.join()

        render_time = time.perf_counter() - t_start
        return tile_results, render_time


# ---------------------------------------------------------------------------
# Full pipeline (mirrors coordinator.run_render interface)
# ---------------------------------------------------------------------------

    def run_render(
        self,
        workers_override: int | None = None,
        rows_override: int | None = None,
        cols_override: int | None = None,
        verbose: bool = True,
    ) -> dict:
        """
        Drop-in replacement for coordinator.run_render() using dynamic scheduling.
        Reads the same workflow.json and accepts the same overrides.
        """

        img_w = self.workflow["image"]["width"]
        img_h = self.workflow["image"]["height"]
        rows = rows_override or self.workflow["tiles"]["rows"]
        cols = cols_override or self.workflow["tiles"]["cols"]
        n_workers = workers_override or self.workflow["workers"]
        output_path = self.workflow["output"]
        renderer_cfg = self.workflow.get("renderer")

        tiles_dir = os.path.join(os.path.dirname(output_path), "tiles")
        self._clean_tiles_dir(tiles_dir)

        if verbose:
            w = 60
            print("\n" + "=" * w)
            print("  Dynamic Scheduler — Distributed Tile Renderer")
            print("=" * w)
            renderer_type = (renderer_cfg or {}).get("type", "synthetic")
            print(f"  Image      : {img_w} x {img_h} px")
            print(f"  Tile grid  : {rows} x {cols}  ->  {rows * cols} tiles")
            print(f"  Workers    : {n_workers}  (pull-based dynamic queue)")
            print(f"  Renderer   : {renderer_type}")

        tiles = split(img_w, img_h, rows, cols)

        if verbose:
            print(f"\n[Step 1] frame_split  -> {len(tiles)} tile descriptors generated")
            print("[Step 2] render       -> dispatching via shared Queue ...")

        tile_results, render_time = self.run_render_dynamic(
            tiles=tiles,
            img_w=img_w,
            img_h=img_h,
            n_workers=n_workers,
            tiles_dir=tiles_dir,
            renderer_cfg=renderer_cfg,
            verbose=verbose,
        )

        if verbose:
            print(f"[Step 3] stitch       -> assembling {len(tile_results)} tiles ...")

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        stitch(tile_results, img_w, img_h, output_path)

        if verbose:
            print(f"\nDone!  Output: {output_path}")
            print(f"Render time  : {render_time:.2f}s  (workers: {n_workers})")

        return {
            "workers": n_workers,
            "tiles": len(tiles),
            "render_time_s": render_time,
            "output": output_path,
            "scheduler": "dynamic",
        }
