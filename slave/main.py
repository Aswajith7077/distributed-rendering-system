import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from contextlib import asynccontextmanager
from service import RedisStreamWorker


worker_task = None
worker = None  # ← don't initialize at module level


@asynccontextmanager
async def lifespan(app: FastAPI):
    global worker_task, worker

    print("[FASTAPI] Lifespan starting...")  # ← add this to confirm lifespan runs

    try:
        print("[FASTAPI] Creating worker...")
        worker = RedisStreamWorker()  # ← initialize here, inside the event loop

        print("[FASTAPI] Setting up consumer group...")
        await worker.setup_group()
        print("[FASTAPI] Setup complete, starting consume task...")
    except Exception as e:
        print(f"[FASTAPI] FATAL: Worker setup failed: {e}")
        import traceback

        traceback.print_exc()
        raise

    async def run_worker():
        try:
            await worker.consume()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"[WORKER CRASH] Unhandled exception: {e}")
            import traceback

            traceback.print_exc()

    worker_task = asyncio.create_task(run_worker())
    print("[FASTAPI] Worker task created")

    yield

    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        print("[FASTAPI] Worker stopped cleanly")

    if worker:
        await worker.close()


app = FastAPI(title="Render Slave API", lifespan=lifespan)


@app.websocket("/health")
async def health_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time health monitoring of the slave node.
    """
    await websocket.accept()
    try:
        while True:
            # Wait for any message from the client (e.g., a ping)
            data = await websocket.receive_text()

            # Send back the health status
            # You can extend this to include actual metrics like CPU, Memory usage, etc.
            health_status = {
                "status": "healthy",
                "message": "Slave node is running",
                "received_ping": data,
            }
            await websocket.send_json(health_status)
    except WebSocketDisconnect:
        print("Client disconnected from health testing WebSocket.")


@app.post("/render_callback")
async def render_callback():
    """
    HTTP endpoint to receive callbacks when a tile rendering is completed.
    """
    # TODO: Implement taking the rendered result and updating local state or notifying the master
    return {"status": "success", "message": "Render callback received"}


@app.get("/benchmark")
async def benchmark():
    """
    HTTP endpoint to trigger or retrieve benchmark results for this slave node.
    """
    # TODO: Implement retrieving benchmark metrics or running a quick benchmark
    return {"status": "success", "benchmark_score": 100}


# if __name__ == "__main__":
#     import uvicorn
#     # Make sure to install uvicorn: pip install uvicorn
#     uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
