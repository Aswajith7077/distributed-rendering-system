"""
main.py  —  Slave node API server
----------------------------------
Three background tasks run concurrently inside the FastAPI lifespan:

  1. RedisStreamWorker   — consumes rendering jobs from the Redis stream
  2. MetricsService      — writes system metrics to Redis (local reporting / legacy)
  3. GatewayReporter     — pushes live metrics to the Gateway via WebSocket

HTTP endpoints:   /health  /benchmark  /render_callback
WebSocket:        /health  (legacy ping-pong, kept for backwards compat)
"""

import asyncio
import logging

from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from service import RedisStreamWorker
from service import MetricsService
from service import MetricsCollector
from service import GatewayReporter
from config import ConfigService

config = ConfigService()

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


_collector = MetricsCollector(node_type=config.NODE_TYPE)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("[FASTAPI] Lifespan starting...")

    async def run_worker(w: RedisStreamWorker) -> None:
        try:
            log.info("[Worker] Starting…")
            await asyncio.sleep(1)  # brief grace period for Redis to be ready
            await w.setup_group()
            await w.consume()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.error("[Worker] Crashed: %s", exc, exc_info=True)

    worker = RedisStreamWorker()
    worker_task = asyncio.create_task(run_worker(worker), name="redis-worker")

    metrics_service = MetricsService(node_type=config.NODE_TYPE)
    metrics_task = asyncio.create_task(
        metrics_service.report_loop(), name="metrics-redis"
    )

    reporter = GatewayReporter(log=log, config=config, collector=_collector)
    reporter_task = asyncio.create_task(reporter.run(), name="gateway-reporter")

    log.info("[FASTAPI] All background tasks created.")
    yield

    log.info("[FASTAPI] Shutting down background tasks…")
    for task in (worker_task, metrics_task, reporter_task):
        task.cancel()
    await asyncio.gather(
        worker_task, metrics_task, reporter_task, return_exceptions=True
    )
    await metrics_service.close()
    log.info("[FASTAPI] Shutdown complete.")


app = FastAPI(title="Render Slave API", lifespan=lifespan)


# ── HTTP endpoints ─────────────────────────────────────────────────────────────


@app.get("/health")
async def health_check():
    """
    HTTP health check for Docker / load-balancer probes.
    Returns live metrics alongside the status flag.
    """
    metrics = _collector.collect()
    return {
        "status": "healthy",
        "node_id": metrics["node_id"],
        "metrics": metrics,
    }


@app.get("/benchmark")
async def benchmark():
    """
    Returns the current system snapshot as a quick benchmark baseline.
    Replace with a real benchmark workload as needed.
    """
    return {
        "status": "success",
        "snapshot": _collector.collect(),
    }


@app.post("/render_callback")
async def render_callback():
    """
    Receives a completion callback after a tile render job finishes.
    TODO: propagate result to master / update local state.
    """
    return {"status": "success", "message": "Render callback received"}


# ── WebSocket endpoints ────────────────────────────────────────────────────────


@app.websocket("/health")
async def health_ws(websocket: WebSocket):
    """
    Legacy ping-pong health socket — kept for backwards compatibility.
    Each ping returns a live metrics snapshot instead of a static message.
    """
    await websocket.accept()
    try:
        while True:
            await websocket.receive_text()  # wait for any client ping
            await websocket.send_json(_collector.collect())
    except WebSocketDisconnect:
        log.info("[WS /health] Client disconnected.")
