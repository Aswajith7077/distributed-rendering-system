# Distributed Tile-Based Rendering with Dynamic Task Scheduling

> **Course:** Parallel & Distributed Computing
> **Topic:** Distributed tile-based image rendering with DAG-based task scheduling and scalability analysis

---

## Abstract

Rendering is a computationally intensive workload suitable for parallelisation because each image region (tile) can be computed independently, with no inter-region data dependency. This project implements a distributed tile-based rendering system that decomposes a full-resolution image into a grid of tiles, dispatches each tile to an independent worker process, and aggregates the results. Two scheduling strategies are compared — static (`Pool.map`) and dynamic (pull-based work queue) — and their scalability is evaluated using speedup, parallel efficiency, and Amdahl's Law analysis.

---

## System Architecture

```
                    ┌─────────────────────────┐
                    │       Client / CLI       │
                    │  (coordinator.py /       │
                    │   scheduler.py /         │
                    │   benchmark.py)          │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │  frame_split operator   │
                    │  (tile_splitter)        │
                    │  Decomposes frame into  │
                    │  R × C tile descriptors │
                    └────────────┬────────────┘
                                 │  task queue / Pool.map
          ┌──────────────────────┼──────────────────────┐
          │                      │                      │
 ┌────────▼──────┐      ┌────────▼──────┐     ┌────────▼──────┐
 │   Worker 1    │      │   Worker 2    │     │   Worker N    │
 │ renders tile  │      │ renders tile  │     │ renders tile  │
 └────────┬──────┘      └────────┬──────┘     └────────┬──────┘
          │                      │                      │
          └──────────────────────▼──────────────────────┘
                    ┌────────────────────────┐
                    │  stitch operator       │
                    │  (aggregator)          │
                    │  Assembles tile PNGs   │
                    │  into final image      │
                    └────────────────────────┘
```

---

## DAG Task Graph

The rendering pipeline is modelled as a shallow directed acyclic graph (DAG):

```
 [Scene Load / Config]
         │
         ▼
 [Tile Generation]          ← serial, O(N) — generates N tile descriptors
         │
    ┌────┴──────────────────────────────────┐
    │ Tile 0 │ Tile 1 │ Tile 2 │ ... │ Tile N │   ← parallel stage
    └────┬──────────────────────────────────┘
         │
         ▼
 [Image Aggregation]        ← serial, stitch operator
         │
         ▼
     [output.png]
```

The parallel stage is **embarrassingly parallel**: tiles share no data and can be rendered on independent processes or machines with no synchronisation overhead beyond task dispatch.

---

## Scheduling Strategies

| Strategy | File | Mechanism | Load Balancing |
|---|---|---|---|
| Static (Pool.map) | `coordinator.py` | Tasks pre-assigned before execution | No — stragglers block completion |
| Dynamic (work queue) | `scheduler.py` | Workers pull next available tile when free | Yes — idle workers never stall |

### Dynamic Scheduler Design

```
 Task Queue (shared)         Workers (p processes)
 ┌──────────────────┐
 │ tile_0           │◄── Worker 1 pulls → render → push result
 │ tile_1           │◄── Worker 2 pulls → render → push result
 │ ...              │◄── Worker N pulls → render → push result
 │ SENTINEL (None)  │    (re-enqueued by first worker to see it)
 └──────────────────┘
```

Workers emit a **poison pill** (sentinel) back to the queue upon exit so subsequent workers also terminate cleanly — a standard distributed systems shutdown pattern.

---

## Project Structure

```
package/
│
├── coordinator.py      ← Static scheduler  (Pool.map-based)
├── scheduler.py        ← Dynamic scheduler (pull-based Queue)
├── benchmark.py        ← Performance evaluation + matplotlib plots
├── run_demo.py         ← Quick scaling demo (ASCII table + bar chart)
├── workflow.json       ← Pipeline definition (DAG config)
├── requirements.txt
│
├── operators/
│   ├── frame_split.py  ← Tile decomposition operator
│   └── stitch.py       ← Image aggregation operator
│
└── output/
    ├── final.png           ← Stitched output image
    ├── benchmark_results.csv
    ├── tiles/
    │   └── tile_XXXX.png
    └── plots/
        ├── speedup.png
        ├── efficiency.png
        └── time.png
```

---

## Setup

```bash
pip install -r requirements.txt
```

---

## Usage

### Run a single render (static scheduler)
```bash
python coordinator.py
python coordinator.py --workers 8 --rows 4 --cols 4
```

### Run with the dynamic work-queue scheduler
```bash
python scheduler.py
python scheduler.py --workers 8 --rows 4 --cols 4
```

### Quick scaling demo (ASCII table + bar chart)
```bash
python run_demo.py
```

### Full benchmark with plots and CSV
```bash
# HD resolution (fast)
python benchmark.py --resolution hd --workers 1 2 4 8 16

# Full-HD
python benchmark.py --resolution fhd --workers 1 2 4 8 --repeats 3
```

---

## Performance Metrics

### Speedup
```
S(p) = T(1) / T(p)
```

### Parallel Efficiency
```
E(p) = S(p) / p × 100%
```

### Amdahl's Law (theoretical upper bound)
```
S_amdahl(p) = 1 / (f_s + (1 - f_s) / p)

where  f_s = serial fraction of the workload
       p   = number of processors
```

The serial fraction `f_s` includes the tile-split step, stitch step, and inter-process communication overhead. Even a small `f_s` limits maximum achievable speedup (Amdahl's Law).

### Overhead
```
O(p) = p × T(p) − T(1)
```

Overhead grows with `p` due to process spawn cost, IPC, and file I/O for tile images.

---

## Example Results

```
  Workers  |  Time (s)  |  Speedup  |  Efficiency
  ------------------------------------------------
        1  |     42.15  |    1.00x  |      100.0%
        2  |     22.10  |    1.91x  |       95.4%
        4  |     12.08  |    3.49x  |       87.2%
        8  |      7.73  |    5.45x  |       68.2%
       16  |      5.92  |    7.12x  |       44.5%
```

Sub-linear scaling is expected and consistent with Amdahl's Law — the serial fraction (tile split + stitch + IPC) limits perfect linear speedup.

---

## Key PDC Concepts Demonstrated

| Concept | Where in Code |
|---|---|
| Task parallelism | Each tile → independent task |
| Embarrassingly parallel workload | No inter-tile data dependency |
| Workload partitioning | `operators/frame_split.py` |
| Static scheduling | `coordinator.py` (Pool.map) |
| Dynamic scheduling / load balancing | `scheduler.py` (Queue + pull) |
| DAG-based pipeline | `workflow.json` |
| Scalability analysis | `benchmark.py` |
| Amdahl's Law | `benchmark.py` (overlay on speedup plot) |
| Straggler mitigation | `scheduler.py` (dynamic queue) |
| Distributed aggregation | `operators/stitch.py` |
