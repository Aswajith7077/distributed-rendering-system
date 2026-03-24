# Distributed Tile-Based Rendering System

A complete end-to-end distributed rendering pipeline built as a full-stack application. The system decomposes high-resolution images into smaller tiles, renders them in parallel across multiple worker processes using different scheduling strategies, and stitches them back together. 

It includes a Next.js frontend for configuration, a FastAPI backend for job management, and a robust Python core for parallel processing and rendering.

---

## 🏗️ System Architecture

The project is divided into three main comp    onents:

### 1. `server`/ (Core Engine)
The heart of the system, responsible for the mathematical and distributed computing aspects of the rendering pipeline.
- **Tile Decomposition (`operators/frame_split.py`)**: Breaks down a full-resolution target image into a grid of independent tile descriptors.
- **Parallel Computing**: Features two distinct scheduling architectures:
  - **Static Scheduler (`coordinator.py`)**: Uses Python's `multiprocessing.Pool.map` to pre-assign tasks to workers. Useful for demonstrating the "straggler problem" where uneven workloads block completion.
  - **Dynamic Scheduler (`scheduler.py`)**: Uses a pull-based work queue where workers pull the next available tile when free. Implements automatic load balancing and avoids the straggler problem.
- **Rendering Backends (`renderers/`)**: Designed with a Strategy pattern to support multiple backends:
  - **Synthetic**: Procedural generation (gradient + sine wave) simulating CPU-bound rendering workloads.
  - **Blender**: Headless CLI integration to render real 3D scenes (`.blend` files) by manipulating Blender's border rendering limits per tile.
- **Aggregation (`operators/stitch.py`)**: Reconstructs the final image by pasting all rendered tiles onto a master canvas.
- **Benchmarking (`benchmark.py`)**: Evaluates scalability, computing speedup, parallel efficiency, overhead, and plots the results against theoretical bounds like Amdahl's Law.

### 2. `backend`/ (REST API)
A FastAPI web server that acts as the bridge between the frontend GUI and the core execution engine.
- Manages asynchronous render jobs using background tasks and a local jobs database.
- Translates API requests into `workflow.json` configurations the engine understands.
- Triggers either the coordinator or scheduler models based on the request.
- Exposes endpoints to check job status, download output tiles in progress, and retrieve the final stitched image.

### 3. `frontend`/ (Web UI)
A modern Next.js web application (React, Tailwind CSS, shadcn/ui) that provides an intuitive interface for the system.
- Allows users to configure aspects of the job dynamically: Resolution (Width/Height), Tile Grid (Rows/Cols), Worker Count, and Renderer Type.
- Visualises the overall progress and provides a gallery to view the individual tile boundaries and the final rendered output.

---

## 🚀 Getting Started

To run the full stack locally, you need to start the backend and frontend separately. 

### Prerequisites
- Python 3.10+
- Node.js 18+

### Setup & Run Backend
The API needs to be running to accept tasks from the frontend.

```bash
cd backend
python -m venv .venv
# Activate venv:
# Windows: .venv\Scripts\activate
# Unix: source .venv/bin/activate

pip install -r requirements.txt
python main.py
```
*The backend API will run at http://localhost:8000*

### Setup & Run Frontend
The frontend provides the visual configuration tool.

```bash
cd frontend
npm install
npm run dev
```
*The web interface will be accessible at http://localhost:3000*

### Running Core Benchmark Tests (CLI only)
If you want to run the raw core engine tests and performance metrics natively without the UI:

```bash
cd server
pip install -r requirements.txt

# Run a single static scheduler task
python coordinator.py --workers 4 --rows 2 --cols 2

# Run a single dynamic queue task 
python scheduler.py --workers 4 --rows 2 --cols 2

# Run a full benchmark generating CSVs and scaling plots
python benchmark.py --resolution hd --workers 1 2 4 8
```




---

## 🧠 Educational Value
This project was developed for a Parallel & Distributed Computing context to demonstrate:
- **Task Parallelism**: Splitting an embarrassingly parallel workload (no inter-tile dependencies).
- **Load Balancing**: The measurable difference between static pre-allocation vs. dynamic work-stealing queues.
- **Distributed System Patterns**: Implementing "poison pill" (sentinel) termination patterns for shared task queues.
- **Amdahl's Law**: Quantifying how serial fractional overheads (tile splitting, IPC, stitching) mathematically cap maximum achievable speedup regardless of worker count.
