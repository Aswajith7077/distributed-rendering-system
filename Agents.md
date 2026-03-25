# Distributed Tile Rendering System - Architecture & Context

## Overview
This project is a resilient distributed platform designed to orchestrate and execute Blender rendering tasks across multiple containerized nodes. It relies on a microservices architecture communicating exclusively through object storage and stream-based message brokering to achieve horizontal scalability for heavy 3D rendering jobs.

## Core Services

### 1. Gateway Node (`/gateway`)
- **Technology Profile**: Python, FastAPI, Contextlib, FFmpeg
- **Core Responsibilities**:
  - **API Ingestion**: Exposes REST endpoints (e.g., `/api/upload/`) for clients to submit `.blend` scene files alongside their configuration metadata (render engine, dimensions, frames, samples).
  - **Storage Orchestration**: Uploads incoming `.blend` assets into the centralized MinIO object store.
  - **Task Dispatching**: Utilizes `task_splitter.py` to fractionalize a multi-frame rendering job into individual atomic frame tasks, appending them to the Redis `jobs_stream` queue and tracking the total task footprint in Redis (`job:{job_id}:total_frames`).
  - **Result Aggregation**: Runs a background `RedisStatusStreamListener` spawned during the FastAPI lifespan. It constantly listens to the `jobs_stream_ack` stream to monitor worker outcomes. Once all frames for a given job are successfully tallied as completed, the Listener pulls the images from MinIO, compiles them into a single `final_result.mp4` video via `ffmpeg`, and uploads the final compilation back to storage.

### 2. Slave/Worker Nodes (`/slave`)
- **Technology Profile**: Python, asyncio, Blender Headless CLI
- **Core Responsibilities**:
  - **Job Execution**: Acts as a Redis Stream consumer joining the `workers_group` consumer group. It continuously requests new tasks from the `jobs_stream`.
  - **Asset Retrieval**: Pulls the necessary `.blend` file from MinIO into a localized `/tmp` environment.
  - **Headless Rendering**: Invokes the `BlenderRenderer.process_job()` method, which spins up a subprocess executing `blender -b scene.blend` with specific frame constraints and python-expr scripts to render the exact tile or frame needed.
  - **Upload & Acknowledgment**: Pushes the rendered `.png` outputs securely to MinIO under `jobs/{job_id}/output/`, and subsequently broadcasts an acknowledgment Pydantic payload (`status: done`, `job_id`) onto the `jobs_stream_ack` stream.

### 3. Redis (Message Broker & State Tracker)
- **Role**: High-throughput task queue and state management.
- **Components**:
  - **`jobs_stream`**: The primary job queue where the gateway inserts tasks and slaves claim them.
  - **`jobs_stream_ack`**: The reverse queue where slaves post task success/failure.
  - **Key-Value Store**: Maintains job state metrics like `job:{id}:total_frames` and `job:{id}:completed_frames` safely tracked atomically through `.incr()`.

### 4. MinIO (Blob Object Storage)
- **Role**: Acts as the shared filesystem layer. Rather than transferring massive files over API connections or Redis, all services use MinIO.
- **Pathing Convention**:
  - `jobs/{job_id}/input/scene.blend` - Raw 3D scene data.
  - `jobs/{job_id}/output/frame_000n.png` - Independently rendered task artifacts.
  - `jobs/{job_id}/final_result.mp4` - Consolidated video artifact composed by the gateway.

## Full System Workflow

1. **Submission**: A user uploads an animation bundle to `/api/upload/`.
2. **Persistence**: The Gateway saves the initial `.blend` to MinIO.
3. **Chunking**: The Gateway splits the animation into 1-task-per-frame chunks, establishes the total frame expectations in Redis, and publishes the tasks into `jobs_stream`.
4. **Acquisition**: A scaling fleet of Worker nodes (`worker1`, `worker2`, etc.) consume the tasks dynamically.
5. **Processing**: Workers download the `.blend`, isolate their assigned frame, invoke the Blender engine, and push a localized `.png` up to MinIO.
6. **Reporting**: The Worker publishes its success to `jobs_stream_ack` and acks its message off the main queue.
7. **Synthesis**: The Gateway's `RedisStatusStreamListener` catches the worker's tick. When `completed_frames == total_frames`, it runs a local `ffmpeg` process merging the scattered images into an `.mp4`.
8. **Finalization**: The final video is shipped back to MinIO and Redis tracking data is cleanly sanitized.
