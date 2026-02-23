# Distributed Rendering System
### A college project implementation of the BigEarth paper

> *"Distributed, Workflow-Driven Rendering of 3D Object Scenes on a Big Data Processing Platform"*

---

## What This Project Does

This project implements a simplified version of the **BigEarth distributed rendering pipeline** described in the paper. It demonstrates two core concepts from the paper:

1. **Sort-last data parallelism** — the image is split into tiles; each worker renders its tile independently
2. **Workflow-driven execution** — the pipeline is described in `workflow.json` and executed by a coordinator, mirroring the Operator → Planner → Executor model

---

## How It Maps to the Paper

| Paper Concept | This Project |
|---|---|
| BigEarth platform | `coordinator.py` (Planner + Executor) |
| Worker VMs | Python processes via `multiprocessing.Pool` |
| Blender Cycles renderer | Synthetic per-pixel procedural renderer (`worker.py`) |
| Frame Split operator | `operators/frame_split.py` |
| Image Stitch operator | `operators/stitch.py` |
| Workflow graph (JSON) | `workflow.json` |
| For-Each parallel node | `Pool.map()` in coordinator |

---

## Project Structure

```
package/
│
├── workflow.json           ← Workflow definition (operators, image size, tile grid)
├── coordinator.py          ← Master node: reads workflow, splits, dispatches, stitches
├── worker.py               ← Worker node: renders a single tile
├── run_demo.py             ← Scaling experiment (1 → 16 workers, prints speedup table)
├── requirements.txt
│
├── operators/
│   ├── frame_split.py      ← Divides image into N×M tile grid
│   └── stitch.py           ← Assembles tiles into final image
│
└── output/                 ← Generated at runtime
    ├── final.png           ← Final stitched image
    └── tiles/
        └── tile_XXXX.png   ← Individual tile outputs
```

---

## Setup

```bash
pip install -r requirements.txt
```

---

## Usage

### Single render (uses workflow.json config)
```bash
python coordinator.py
```

### Override workers / tile grid from the command line
```bash
python coordinator.py --workers 8 --rows 4 --cols 4
```

### Full scaling experiment (replicates paper's experiment)
```bash
python run_demo.py
```

---

## Example Output

```
  Workers  |  Time (s)  |  Speedup  |  Efficiency
  ------------------------------------------------
        1  |     42.15  |    1.00x  |      100.0%
        2  |     22.10  |    1.91x  |       95.4%
        4  |     12.08  |    3.49x  |       87.2%
        8  |      7.73  |    5.45x  |       68.2%
       16  |      5.92  |    7.12x  |       44.5%
```

Non-linear scaling matches the paper's findings — overhead from task dispatching and I/O limits perfect (linear) speedup.

---

## Key Concepts Demonstrated

| Concept | Where |
|---|---|
| Data parallelism | Each tile rendered by an independent worker |
| Workflow abstraction | `workflow.json` describes pipeline without code changes |
| Operator modularity | `frame_split` and `stitch` are plug-and-play modules |
| Scalability | `--workers N` to test any parallelism level |
| Sort-last rendering | Tiles assembled post-render by stitch operator |
