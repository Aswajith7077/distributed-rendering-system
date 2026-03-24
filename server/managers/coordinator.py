import os
import time
from multiprocessing import Pool

from operators.frame_split import split
from operators.stitch import stitch
import worker
from managers.base_manager import BaseManager


class Coordinator(BaseManager):
    def __init__(self, workflow_path: str = "workflow.json"):
        super().__init__(workflow_path)


    def __print_banner(self, title: str) -> None:
        w = 60
        print("\n" + "=" * w)
        print(f"  {title}")
        print("=" * w)


    def __print_pipeline(self) -> None:
        print("\n📋 Workflow Pipeline:")
        for i, op in enumerate(self.workflow["pipeline"], 1):
            parallel_tag = "  ← parallel (for-each)" if op.get("parallel") else ""
            print(f"   Step {i}: [{op['operator']}]{parallel_tag}")


    def _parallel_render(self, tiles, img_w, img_h, tiles_dir, renderer_cfg, n_workers, verbose, on_tile_complete=None):
        if verbose:
            print(
                f"[Step 2] render     → dispatching {len(tiles)} tile tasks "
                f"across {n_workers} worker(s) ..."
            )

        if renderer_cfg:
            args = [(t, img_w, img_h, tiles_dir, renderer_cfg) for t in tiles]
        else:
            args = [(t, img_w, img_h, tiles_dir) for t in tiles]

        t_render_start = time.perf_counter()
        
        tile_results = []

        if n_workers == 1:
            # Single-worker baseline — no Pool overhead
            for a in args:
                res = worker.run(a)
                if on_tile_complete:
                    on_tile_complete(res['duration_s'])
                tile_results.append(res)
        else:
            with Pool(processes=n_workers) as pool:
                for res in pool.imap_unordered(worker.run, args):
                    if on_tile_complete:
                        on_tile_complete(res['duration_s'])
                    tile_results.append(res)

        t_render_end = time.perf_counter()
        render_time = t_render_end - t_render_start

        return tile_results, render_time


    def run_render(
        self,
        workers_override: int | None = None,
        rows_override: int | None = None,
        cols_override: int | None = None,
        verbose: bool = True,
        on_job_start=None,
        on_tile_complete=None,
    ) -> dict:
        """
        Executes the full rendering pipeline and returns a result dict.
        """
        wf = self.workflow

        img_w = wf["image"]["width"]
        img_h = wf["image"]["height"]
        rows = rows_override or wf["tiles"]["rows"]
        cols = cols_override or wf["tiles"]["cols"]
        n_workers = workers_override or wf["workers"]
        output_path = wf["output"]
        renderer_cfg = wf.get("renderer")

        tiles_dir = os.path.join(os.path.dirname(output_path), "tiles")
        self._clean_tiles_dir(tiles_dir)

        if verbose:
            self.__print_banner("Distributed Rendering Coordinator")
            self.__print_pipeline()
            renderer_type = (renderer_cfg or {}).get("type", "synthetic")
            print(f"\n🖼️  Image      : {img_w} × {img_h} px")
            print(f"🔲 Tile grid  : {rows} rows × {cols} cols  →  {rows * cols} tiles")
            print(f"⚙️  Workers    : {n_workers}")
            print(f"🎨 Renderer   : {renderer_type}")

        # ------------------------------------------------------------------
        # STEP 1 — Frame Split Operator
        # ------------------------------------------------------------------
        if verbose:
            print("\n[Step 1] frame_split → computing tile descriptors ...")
        tiles = split(img_w, img_h, rows, cols)
        
        if on_job_start:
            on_job_start(len(tiles))

        # ------------------------------------------------------------------
        # STEP 2 — Parallel Render (for-each)
        # ------------------------------------------------------------------
        tile_results, render_time = self._parallel_render(tiles, img_w, img_h, tiles_dir, renderer_cfg, n_workers, verbose, on_tile_complete=on_tile_complete)

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

