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
import json
import logging
import os
import socket
import time
from contextlib import asynccontextmanager

import psutil
import websockets
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from service import RedisStreamWorker
from service.metrics import MetricsService

load_dotenv()

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# ── configuration ──────────────────────────────────────────────────────────────

GATEWAY_WS_URL: str = os.environ.get("GATEWAY_WS_URL", "")  # empty = reporter disabled
NODE_TYPE: str = os.environ.get("NODE_TYPE", "slave")
PUSH_INTERVAL: int = int(os.environ.get("PUSH_INTERVAL", "5"))
RECONNECT_DELAY: int = int(os.environ.get("RECONNECT_DELAY", "3"))


# ── metrics collector ─────────────────────────────────────────────────────────


class MetricsCollector:
    """
    Collects system metrics using psutil.
    Does NOT depend on Redis — pure in-process collection.
    """

    def __init__(self, node_type: str = "slave"):
        self.node_id = f"{node_type}:{socket.gethostname()}:{os.getpid()}"
        self.node_type = node_type
        self.start_time = time.time()

    def collect(self) -> dict:
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        net = psutil.net_io_counters()

        gpu_info: list[dict] = []
        try:
            import GPUtil  # type: ignore

            for g in GPUtil.getGPUs():
                gpu_info.append(
                    {
                        "id": g.id,
                        "name": g.name,
                        "load_pct": round(g.load * 100, 1),
                        "memory_used_mb": g.memoryUsed,
                        "memory_total_mb": g.memoryTotal,
                        "temperature_c": g.temperature,
                    }
                )
        except Exception:
            pass

        return {
            "node_id": self.node_id,
            "type": self.node_type,
            "status": "online",
            "uptime_seconds": int(time.time() - self.start_time),
            "timestamp": time.time(),
            "cpu": {
                "percent": cpu,
                "per_core": psutil.cpu_percent(percpu=True),
                "core_count": psutil.cpu_count(),
            },
            "memory": {
                "percent": mem.percent,
                "used_gb": round(mem.used / (1024**3), 2),
                "total_gb": round(mem.total / (1024**3), 2),
                "available_gb": round(mem.available / (1024**3), 2),
            },
            "disk": {
                "percent": disk.percent,
                "used_gb": round(disk.used / (1024**3), 2),
                "free_gb": round(disk.free / (1024**3), 2),
                "total_gb": round(disk.total / (1024**3), 2),
            },
            "network": {
                "bytes_sent": net.bytes_sent,
                "bytes_recv": net.bytes_recv,
                "packets_sent": net.packets_sent,
                "packets_recv": net.packets_recv,
            },
            "gpu": gpu_info,
        }


# ── gateway reporter (WS push loop) ──────────────────────────────────────────


class GatewayReporter:
    """
    Maintains a persistent outbound WebSocket connection to the Gateway and
    pushes a metrics snapshot every PUSH_INTERVAL seconds.

    Disabled entirely when GATEWAY_WS_URL is not set — safe to deploy slaves
    that don't have a gateway yet.
    """

    def __init__(self, collector: MetricsCollector):
        self.collector = collector
        self.enabled = bool(GATEWAY_WS_URL)

    async def run(self) -> None:
        if not self.enabled:
            log.info("[GatewayReporter] GATEWAY_WS_URL not set — reporter disabled.")
            return

        while True:
            try:
                await self._connect_and_push()
            except asyncio.CancelledError:
                log.info("[GatewayReporter] Cancelled.")
                raise
            except Exception as exc:
                log.warning(
                    "[GatewayReporter] Unexpected error: %s. Reconnecting in %ds…",
                    exc,
                    RECONNECT_DELAY,
                )
                await asyncio.sleep(RECONNECT_DELAY)

    async def _connect_and_push(self) -> None:
        log.info("[GatewayReporter] Connecting to %s", GATEWAY_WS_URL)

        async with websockets.connect(
            GATEWAY_WS_URL,
            ping_interval=20,
            ping_timeout=10,
            open_timeout=10,
        ) as ws:
            log.info("[GatewayReporter] Connected as %s", self.collector.node_id)

            # Registration frame
            await ws.send(
                json.dumps(
                    {
                        "event": "hello",
                        "node_id": self.collector.node_id,
                        "type": self.collector.node_type,
                    }
                )
            )

            while True:
                payload = self.collector.collect()
                await ws.send(json.dumps(payload))
                log.debug(
                    "[GatewayReporter] Pushed snapshot for %s", self.collector.node_id
                )
                await asyncio.sleep(PUSH_INTERVAL)


# ── shared collector instance (used by reporter AND HTTP endpoints) ────────────

_collector = MetricsCollector(node_type=NODE_TYPE)


# ── lifespan ───────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("[FASTAPI] Lifespan starting...")

    # ── 1. Redis Stream Worker ─────────────────────────────────────────────────
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

    # ── 2. Legacy MetricsService (Redis key reporting) ─────────────────────────
    metrics_service = MetricsService(node_type=NODE_TYPE)
    metrics_task = asyncio.create_task(
        metrics_service.report_loop(), name="metrics-redis"
    )

    # ── 3. Gateway Reporter (outbound WS push to gateway) ─────────────────────
    reporter = GatewayReporter(_collector)
    reporter_task = asyncio.create_task(reporter.run(), name="gateway-reporter")

    log.info("[FASTAPI] All background tasks created.")
    yield

    # ── Graceful shutdown ──────────────────────────────────────────────────────
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
