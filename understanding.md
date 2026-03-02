# Understanding the Distributed Rendering System

> A complete walkthrough of how every component works, how data flows between them, and what happens at each step.

---

## Table of Contents

1. [Big Picture — What Happens When You Run It](#1-big-picture)
2. [workflow.json — The Blueprint](#2-workflowjson)
3. [frame_split.py — Tile Decomposition](#3-frame_splitpy)
4. [worker.py — The Compute Unit](#4-workerpy)
5. [coordinator.py — Static Scheduler](#5-coordinatorpy)
6. [scheduler.py — Dynamic Work Queue](#6-schedulerpy)
7. [stitch.py — Image Aggregation](#7-stitchpy)
8. [renderers/ — Pluggable Rendering Backends](#8-renderers)
9. [benchmark.py — Performance Evaluation](#9-benchmarkpy)
10. [Complete Data Flow — End to End](#10-complete-data-flow)

---

## 1. Big Picture

When you run `python coordinator.py`, this is what happens in sequence:

```
 YOU run coordinator.py
      │
      ▼
 ┌─────────────────────────────────────────────┐
 │  1. Read workflow.json                       │
 │     → image size, tile grid, worker count    │
 │     → which renderer to use                  │
 └─────────────────────┬───────────────────────┘
                       │
                       ▼
 ┌─────────────────────────────────────────────┐
 │  2. frame_split(1920, 1080, 4, 4)           │
 │     → returns 16 tile descriptors           │
 │     → each says "render pixels x..x, y..y"  │
 └─────────────────────┬───────────────────────┘
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
 ┌──────────┐  ┌──────────┐  ┌──────────┐
 │ Worker 1 │  │ Worker 2 │  │ Worker N │   ← each renders its tile
 │ tile_0   │  │ tile_1   │  │ tile_15  │      independently
 └────┬─────┘  └────┬─────┘  └────┬─────┘
      │              │              │
      ▼              ▼              ▼
   tile_0000.png  tile_0001.png  tile_0015.png
          │              │              │
          └──────────────┼──────────────┘
                         ▼
 ┌─────────────────────────────────────────────┐
 │  3. stitch(tile_results, 1920, 1080)        │
 │     → paste all tile PNGs onto one canvas   │
 │     → save output/final.png                 │
 └─────────────────────────────────────────────┘
```

That's the entire system. Everything else is just details of *how each step works*.

---

## 2. workflow.json

**Purpose:** The single config file that describes the entire pipeline.

```json
{
  "pipeline": [
    {"operator": "frame_split"},
    {"operator": "render", "parallel": true},
    {"operator": "stitch"}
  ],
  "image": {
    "width": 1920,
    "height": 1080
  },
  "tiles": {
    "rows": 4,
    "cols": 4
  },
  "workers": 4,
  "output": "output/final.png",
  "renderer": {
    "type": "synthetic"
  }
}
```

### What each field does:

| Field | What it controls |
|---|---|
| `pipeline` | The DAG — which operators run and in what order |
| `pipeline[].parallel` | If `true`, this step runs across multiple workers |
| `image.width/height` | Full output image dimensions in pixels |
| `tiles.rows/cols` | How many rows × columns to split the image into |
| `workers` | Number of parallel processes to use |
| `output` | Where to save the final stitched image |
| `renderer.type` | Which rendering backend: `"synthetic"` or `"blender"` |

### For Blender rendering, the renderer section looks like:

```json
"renderer": {
  "type": "blender",
  "blender_path": "C:\\Program Files\\Blender Foundation\\Blender 5.0\\blender.exe",
  "scene_file": "scene.blend",
  "engine": "CYCLES",
  "samples": 128,
  "device": "CPU"
}
```

---

## 3. frame_split.py

**File:** `operators/frame_split.py`
**Purpose:** Decomposes the full image into a grid of tile descriptors.

### How it works:

```
Input:  img_width=1920, img_height=1080, rows=2, cols=2

Step 1: Calculate tile dimensions
        tile_w = 1920 / 2 = 960 px
        tile_h = 1080 / 2 = 540 px

Step 2: Generate grid of tile descriptors

        ┌──────────────────┬──────────────────┐
        │  Tile 0          │  Tile 1          │
        │  x=0, y=0        │  x=960, y=0      │
        │  960 × 540 px    │  960 × 540 px    │
        ├──────────────────┼──────────────────┤
        │  Tile 2          │  Tile 3          │
        │  x=0, y=540      │  x=960, y=540    │
        │  960 × 540 px    │  960 × 540 px    │
        └──────────────────┴──────────────────┘
```

### Output: a list of dicts

```python
[
    {"id": 0, "x": 0,   "y": 0,   "width": 960, "height": 540},
    {"id": 1, "x": 960, "y": 0,   "width": 960, "height": 540},
    {"id": 2, "x": 0,   "y": 540, "width": 960, "height": 540},
    {"id": 3, "x": 960, "y": 540, "width": 960, "height": 540},
]
```

### Edge handling:
The last row/column absorbs remainder pixels when dimensions don't divide evenly.

---

## 4. worker.py

**File:** `worker.py`
**Purpose:** The actual compute unit. Receives ONE tile, renders it, saves it as PNG.

### Two modes:

#### Mode 1: Legacy (no renderer config)

```python
# Called as: worker.run((tile, img_w, img_h, tiles_dir))
# Uses the built-in synthetic renderer directly
```

The synthetic renderer computes each pixel with a gradient + sine wave formula:
```
For each pixel (px, py) in the tile:
    gx = tile.x + px          ← global x coordinate
    gy = tile.y + py          ← global y coordinate
    color = gradient(gx, gy) + sine_wave_pattern(gx, gy)
    save pixel
```

This is deliberately CPU-intensive (nested loops, trig functions) to simulate real rendering workload.

#### Mode 2: Backend (with renderer config)

```python
# Called as: worker.run((tile, img_w, img_h, tiles_dir, renderer_cfg))
# Creates renderer from config, delegates to it
```

The `run()` function detects which mode by checking the length of the args tuple:
- **4 args** → legacy synthetic
- **5 args** → pluggable backend (creates renderer from config)

### Output:

```python
{
    "id": 0,
    "x": 0,
    "y": 0,
    "path": "output/tiles/tile_0000.png",
    "duration_s": 0.95
}
```

---

## 5. coordinator.py — Static Scheduler

**File:** `coordinator.py`
**Purpose:** Orchestrates the full pipeline using static task assignment.

### How static scheduling works:

```python
# Step 1: Generate all tile descriptors
tiles = split(1920, 1080, 4, 4)    # → 16 tiles

# Step 2: Build arg tuples for each tile
args = [(tile_0, 1920, 1080, "output/tiles"),
        (tile_1, 1920, 1080, "output/tiles"),
        ...
        (tile_15, 1920, 1080, "output/tiles")]

# Step 3: Dispatch ALL tasks using Pool.map
with Pool(processes=4) as pool:
    results = pool.map(worker.run, args)
```

### What `Pool.map` does internally:

```
Pool creates 4 worker processes.
It PRE-ASSIGNS tiles to workers before any rendering starts:

  Worker 0 gets: [tile_0, tile_4, tile_8,  tile_12]
  Worker 1 gets: [tile_1, tile_5, tile_9,  tile_13]
  Worker 2 gets: [tile_2, tile_6, tile_10, tile_14]
  Worker 3 gets: [tile_3, tile_7, tile_11, tile_15]

Each worker processes its assigned tiles sequentially.
Pool.map waits for ALL workers to finish.
```

### The problem with static scheduling:

```
If tile_3 is complex (takes 5 seconds) but tile_0 is simple (takes 1 second):

  Worker 0: [tile_0(1s), tile_4(1s), tile_8(1s), tile_12(1s)]  → done at 4s  ← IDLE
  Worker 1: [tile_1(1s), tile_5(1s), tile_9(1s), tile_13(1s)]  → done at 4s  ← IDLE
  Worker 2: [tile_2(1s), tile_6(1s), tile_10(1s), tile_14(1s)] → done at 4s  ← IDLE
  Worker 3: [tile_3(5s), tile_7(1s), tile_11(1s), tile_15(1s)] → done at 8s  ← STRAGGLER

Total time: 8s (bottlenecked by Worker 3)
Workers 0-2 sat idle for 4 seconds!
```

This is the **straggler problem** — it motivates the dynamic scheduler.

---

## 6. scheduler.py — Dynamic Work Queue

**File:** `scheduler.py`
**Purpose:** Same pipeline, but workers PULL tasks from a shared queue instead of having tasks pre-assigned.

### How dynamic scheduling works:

```python
# Step 1: Put all tiles into a shared Queue
task_queue = Queue()
for tile in tiles:
    task_queue.put(tile)
task_queue.put(SENTINEL)   # poison pill

# Step 2: Spawn worker processes
# Each worker runs _dynamic_worker() which loops:
while True:
    tile = task_queue.get()        # BLOCKS until a tile is available
    if tile is SENTINEL:
        task_queue.put(SENTINEL)   # re-enqueue for next worker
        break
    result = render(tile)
    result_queue.put(result)
```

### Visualised:

```
 Queue: [tile_0, tile_1, tile_2, ..., tile_15, SENTINEL]

 Time 0:  Worker 0 pulls tile_0    Worker 1 pulls tile_1
 Time 1:  Worker 0 pulls tile_2    Worker 1 pulls tile_3  (tile_3 is slow...)
 Time 2:  Worker 0 pulls tile_4    Worker 1 still on tile_3...
 Time 3:  Worker 0 pulls tile_5    Worker 1 still on tile_3...
 Time 5:  Worker 0 pulls tile_7    Worker 1 pulls tile_6  (tile_3 done!)
 ...
```

### Why this is better:

- **No idle workers**: when a worker finishes a tile, it immediately pulls the next one
- **Automatic load balancing**: fast workers naturally do more tiles
- **No straggler problem**: the slow tile_3 doesn't block worker 0 from doing more work

### SENTINEL (poison pill) pattern:

```
Queue state when work is done: [..., SENTINEL]

Worker 2 pulls SENTINEL → puts SENTINEL back → exits
Worker 0 pulls SENTINEL → puts SENTINEL back → exits
Worker 1 pulls SENTINEL → puts SENTINEL back → exits

Result: all workers exit cleanly, one by one.
```

This is a standard distributed systems shutdown pattern.

---

## 7. stitch.py

**File:** `operators/stitch.py`
**Purpose:** Assembles rendered tile PNGs into one final image.

### How it works:

```python
# Create blank canvas
canvas = Image.new("RGB", (1920, 1080), color=(0, 0, 0))

# For each rendered tile result:
for tile in tile_results:
    tile_img = Image.open(tile["path"])         # load tile_0000.png
    canvas.paste(tile_img, (tile["x"], tile["y"]))  # paste at correct position

# Save final image
canvas.save("output/final.png")
```

### Visualised:

```
 canvas (1920 × 1080, initially black)
 ┌──────────────────┬──────────────────┐
 │  paste tile_0    │  paste tile_1    │
 │  at (0, 0)       │  at (960, 0)     │
 ├──────────────────┼──────────────────┤
 │  paste tile_2    │  paste tile_3    │
 │  at (0, 540)     │  at (960, 540)   │
 └──────────────────┴──────────────────┘
 → save as output/final.png
```

---

## 8. renderers/ — Pluggable Rendering Backends

**Directory:** `renderers/`
**Purpose:** Swap between synthetic (fake) rendering and real Blender rendering without changing any other code.

### Architecture:

```
renderers/
├── __init__.py      ← Factory: get_renderer(config) → TileRenderer
├── base.py          ← Abstract interface: TileRenderer (ABC)
├── synthetic.py     ← SyntheticRenderer (gradient + sine waves)
└── blender.py       ← BlenderRenderer (calls blender CLI)
```

### How the factory works:

```python
from renderers import get_renderer

# Config comes from workflow.json's "renderer" section
renderer = get_renderer({"type": "synthetic"})
# → returns SyntheticRenderer()

renderer = get_renderer({"type": "blender", "scene_file": "scene.blend", ...})
# → returns BlenderRenderer(config)
```

### TileRenderer interface (base.py):

Every renderer must implement one method:

```python
def render_tile(self, tile, img_width, img_height, tiles_dir, **kwargs) -> dict:
    # Input:  tile descriptor {"id", "x", "y", "width", "height"}
    # Output: result dict     {"id", "x", "y", "path", "duration_s"}
```

### SyntheticRenderer (synthetic.py):

Identical logic to the original `worker.py` — gradient + sine wave per pixel. No external dependencies.

### BlenderRenderer (blender.py):

Calls Blender's headless CLI. Here's what happens per tile:

```
Step 1: Convert pixel coordinates → normalised coordinates [0.0–1.0]

        tile = {x: 960, y: 0, width: 960, height: 540}
        image = 1920 × 1080

        border_min_x = 960 / 1920   = 0.5
        border_max_x = 1920 / 1920  = 1.0
        border_min_y = 1 - 540/1080 = 0.5    ← Y is FLIPPED in Blender
        border_max_y = 1 - 0/1080   = 1.0

Step 2: Build a Python expression string for Blender:

        "import bpy;
         s = bpy.context.scene;
         s.render.use_border = True;
         s.render.use_crop_to_border = True;
         s.render.border_min_x = 0.5;
         s.render.border_max_x = 1.0;
         s.render.border_min_y = 0.5;
         s.render.border_max_y = 1.0;
         s.cycles.samples = 128;"

Step 3: Call Blender as a subprocess:

        blender.exe -b scene.blend --python-expr "..." -f 1

        -b           = headless mode (no GUI)
        --python-expr = run Python code to set border region
        -f 1         = render frame 1

Step 4: Blender renders ONLY the border region and saves it as PNG

Step 5: Rename output file to our standard tile_XXXX.png format
```

### Why this design matters:

The coordinator and scheduler **don't know or care** which renderer is being used. They just pass `renderer_cfg` through to the worker. The worker creates the renderer and calls `render_tile()`. This is the **Strategy Pattern** — the algorithm (rendering) is interchangeable.

---

## 9. benchmark.py

**File:** `benchmark.py`
**Purpose:** Runs the pipeline multiple times with different worker counts and measures performance.

### What it measures:

```
For each worker count p ∈ {1, 2, 4, 8, 16}:
    Run the full pipeline
    Record wall-clock time T(p)

Then compute:
    Speedup:     S(p) = T(1) / T(p)        "How many times faster?"
    Efficiency:  E(p) = S(p) / p × 100%    "How well are we using the workers?"
    Overhead:    O(p) = p × T(p) - T(1)    "Extra work due to parallelism"
```

### Amdahl's Law overlay:

The theoretical maximum speedup is limited by the serial fraction `f_s`:

```
S_max(p) = 1 / (f_s + (1 - f_s) / p)
```

Where `f_s` is the fraction of work that CANNOT be parallelised (tile split + stitch + IPC).

Even with infinite workers:
```
S_max(∞) = 1 / f_s

If f_s = 0.05 (5% serial), max speedup = 20x
If f_s = 0.10 (10% serial), max speedup = 10x
```

### What it produces:

```
output/
├── benchmark_results.csv     ← Raw data for your report
└── plots/
    ├── speedup.png           ← Empirical vs Ideal vs Amdahl curves
    ├── efficiency.png        ← Parallel efficiency vs worker count
    └── time.png              ← Wall-clock time vs worker count
```

---

## 10. Complete Data Flow — End to End

Here's exactly what happens when you run `python coordinator.py --workers 4 --rows 2 --cols 2`:

```
┌─────────────────────────────────────────────────────────────────┐
│  Step 0: Parse CLI args                                         │
│    workers=4, rows=2, cols=2                                    │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  Step 1: Load workflow.json                                     │
│    image: 1920×1080                                             │
│    renderer: {"type": "synthetic"}                              │
│    output: "output/final.png"                                   │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  Step 2: frame_split(1920, 1080, 2, 2)                         │
│                                                                 │
│    Returns 4 tile descriptors:                                  │
│    [                                                            │
│      {id:0, x:0,   y:0,   w:960, h:540},                       │
│      {id:1, x:960, y:0,   w:960, h:540},                       │
│      {id:2, x:0,   y:540, w:960, h:540},                       │
│      {id:3, x:960, y:540, w:960, h:540},                       │
│    ]                                                            │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  Step 3: Build worker args (one tuple per tile)                 │
│                                                                 │
│    renderer_cfg is {"type": "synthetic"}, so 5-arg tuples:      │
│    args = [                                                     │
│      (tile_0, 1920, 1080, "output/tiles", {"type":"synthetic"}),│
│      (tile_1, 1920, 1080, "output/tiles", {"type":"synthetic"}),│
│      (tile_2, 1920, 1080, "output/tiles", {"type":"synthetic"}),│
│      (tile_3, 1920, 1080, "output/tiles", {"type":"synthetic"}),│
│    ]                                                            │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  Step 4: Pool.map(worker.run, args)  with 4 workers             │
│                                                                 │
│    Worker 0:                          Worker 1:                 │
│      worker.run(args[0])                worker.run(args[1])     │
│        → len(args) == 5                   → len(args) == 5      │
│        → get_renderer(cfg)                → get_renderer(cfg)   │
│        → SyntheticRenderer()              → SyntheticRenderer() │
│        → render_tile(tile_0, ...)         → render_tile(tile_1) │
│        → saves tile_0000.png              → saves tile_0001.png │
│                                                                 │
│    Worker 2:                          Worker 3:                 │
│      (same flow for tile_2)             (same flow for tile_3)  │
│        → saves tile_0002.png              → saves tile_0003.png │
│                                                                 │
│    Pool.map returns all 4 results                               │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  Step 5: stitch(tile_results, 1920, 1080, "output/final.png")  │
│                                                                 │
│    canvas = blank 1920×1080 image                               │
│    paste tile_0000.png at (0, 0)                                │
│    paste tile_0001.png at (960, 0)                              │
│    paste tile_0002.png at (0, 540)                              │
│    paste tile_0003.png at (960, 540)                            │
│    save → output/final.png                                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## Quick Reference: Which File Does What

| File | Role | PDC Concept |
|---|---|---|
| `workflow.json` | Pipeline config (DAG definition) | Workflow/DAG specification |
| `operators/frame_split.py` | Splits image into tiles | Workload partitioning |
| `worker.py` | Renders one tile | Task execution unit |
| `coordinator.py` | Orchestrates with `Pool.map` | Static scheduling |
| `scheduler.py` | Orchestrates with `Queue` | Dynamic scheduling / load balancing |
| `operators/stitch.py` | Merges tiles into final image | Distributed aggregation |
| `renderers/base.py` | Renderer interface | Abstraction / Strategy pattern |
| `renderers/synthetic.py` | Fake renderer (for benchmarks) | — |
| `renderers/blender.py` | Real Blender CLI renderer | — |
| `benchmark.py` | Performance measurement + plots | Scalability analysis / Amdahl's Law |
