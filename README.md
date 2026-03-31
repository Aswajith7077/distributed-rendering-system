# Distributed Tile-Based Rendering System

A resilient distributed platform designed to orchestrate and execute Blender rendering tasks across multiple containerized or standalone nodes. This system achieves horizontal scalability for heavy 3D rendering jobs by using a microservices architecture communicating through object storage and stream-based message brokering.

## 1. What is the Application?
This application is a **Distributed Rendering Cluster** for Blender. It allows users to upload `.blend` scenes and render them significantly faster by splitting the animation into individual tasks and distributing them to a fleet of worker nodes.

## 2. What was the Problem?
Rendering high-quality 3D animations (especially using Cycles) is a computationally expensive and time-consuming process. On a single machine, a multi-frame animation could take hours or days to complete. Furthermore, if a single machine fails mid-render, the entire process might need to be restarted without careful state management.

## 3. How This Application Solves It?
The system solves this through **parallel task distribution**:
- **Atomic Splitting**: The gateway splits a large rendering job into atomic "tasks" (e.g., one task per frame).
- **Asynchronous Execution**: Multiple worker nodes ("Slaves") pull these tasks from a Redis Stream and process them concurrently.
- **Distributed Storage**: All input assets and rendered outputs are stored in a centralized MinIO object store, ensuring all nodes have access to the same data without complex file sharing.
- **Fault Tolerance**: If a slave node goes offline, the task remains in the Redis Stream (pending acknowledgment) and can be reclaimed by another active worker.
- **Real-Time Monitoring**: A frontend dashboard provides live telemetry (CPU, RAM, progress) for all connected hardware.

## 4. High-Level Project Overview
- **`gateway/`**: The orchestration hub. It handles API requests, manages the Redis task queue, monitors slave health, and aggregates individual rendered frames into a final video using `ffmpeg`.
- **`slave/`**: The worker node. It listens for tasks, downloads the necessary `.blend` file, invokes Blender headlessly to render its assigned frame, and uploads the resulting image.
- **`frontend/`**: A modern Next.js dashboard for submitting jobs and tracking the cluster's performance and status in real-time.
- **Architecture**:
  - **Redis**: Acts as the message broker (`jobs_stream`) and state tracker.
  - **MinIO**: Acts as the shared filesystem for large binary assets (`.blend` files and `.png` outputs).

## 5. Installation and Setup

### Prerequisites
- Python 3.10+
- Node.js 18+
- Blender (installed and available in PATH for Slave nodes)
- Redis and MinIO (running locally or via Docker)

### 1. Unified Environment Setup
It is recommended to use a virtual environment for the Python components.
```bash
# From the root directory
python -m venv .venv
# Windows: .venv\Scripts\activate
# Unix: source .venv/bin/activate
```

### 2. Gateway Setup
```bash
cd gateway
pip install -r requirements.txt
python run.py
```
*The gateway will run at http://localhost:8000*

### 3. Slave Setup
You can run multiple slave processes on different ports to simulate a cluster.
```bash
cd slave
pip install -r requirements.txt
# Run first slave
python run.py --port 8001
# Run second slave (in a new terminal)
python run.py --port 8002
```

### 4. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
*The web interface will be accessible at http://localhost:3000*

---

## 🛠️ Developed for PDC
This project demonstrates key concepts in **Parallel & Distributed Computing**:
- **Amdahl's Law**: Benchmarking theoretical vs. actual speedup.
- **Load Balancing**: Dynamic task distribution via shared streams.
- **Cluster Orchestration**: Real-time health monitoring and task synchronization.
