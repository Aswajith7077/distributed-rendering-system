import asyncio
import time
import statistics
from collections import deque
import json

class MetricsAggregator:
    def __init__(self):
        # Window size of 10 seconds for smoothing (adjust as necessary)
        # We store (timestamp, value) tuples
        self.completion_times = deque(maxlen=2000)
        self.tile_durations = deque(maxlen=2000)
        
        # System state
        self.active_workers = 0
        self.queue_depth = 0
        self.failed_tasks = 0
        self.total_completed = 0
        
        # SRE metrics
        self.throughput = 0.0          # tiles/sec
        self.p95_latency = 0.0         # seconds
        self.p99_latency = 0.0         # seconds
        self.avg_render_time = 0.0     # seconds
        
        # Efficiency (Amdahl's)
        self.parallel_fraction = 0.95  # P 
        self.efficiency = 1.0          # E(N)
        self.speedup = 1.0             # S(N)

        self.last_update_time = time.time()
        
        # WebSocket queues for broadcasting
        self.subscribers = set()
        
        self.loop = None

    def set_loop(self, loop):
        self.loop = loop

    def subscribe(self, queue: asyncio.Queue):
        self.subscribers.add(queue)

    def unsubscribe(self, queue: asyncio.Queue):
        self.subscribers.discard(queue)

    def record_job_start(self, workers: int, total_tiles: int):
        self.active_workers += workers
        self.queue_depth += total_tiles
        self._recompute_amdahls(workers)
        self._trigger_update()

    def record_job_end(self, workers: int):
        self.active_workers = max(0, self.active_workers - workers)
        self._recompute_amdahls(max(1, self.active_workers))
        self._trigger_update()

    def record_tile_complete(self, duration_s: float):
        now = time.time()
        self.total_completed += 1
        if self.queue_depth > 0:
            self.queue_depth -= 1
            
        self.completion_times.append(now)
        self.tile_durations.append(duration_s)
        
        self._recompute_metrics(now)
        self._trigger_update()

    def record_tile_failed(self):
        self.failed_tasks += 1
        self._trigger_update()

    def _recompute_amdahls(self, N: int):
        if N < 1:
            N = 1
        # S(N) = 1 / ((1 - P) + P/N)
        self.speedup = 1.0 / ((1.0 - self.parallel_fraction) + (self.parallel_fraction / N))
        self.efficiency = self.speedup / N

    def _recompute_metrics(self, now: float):
        # 10 second sliding window for throughput and latencies
        window = 10.0
        cutoff = now - window
        
        # Filter recent
        recent_durations = []
        recent_count = 0
        
        # Deque is ordered, we can just iterate backwards or count those after cutoff
        # For simplicity, since we only keep 2000 items, just iterate
        for t, d in zip(self.completion_times, self.tile_durations):
            if t >= cutoff:
                recent_durations.append(d)
                recent_count += 1
                
        self.throughput = recent_count / window if window > 0 else 0.0
        
        if recent_durations:
            self.avg_render_time = statistics.mean(recent_durations)
            if len(recent_durations) > 1:
                try:
                    self.p95_latency = statistics.quantiles(recent_durations, n=100)[94]
                    self.p99_latency = statistics.quantiles(recent_durations, n=100)[98]
                except statistics.StatisticsError:
                    self.p95_latency = max(recent_durations)
                    self.p99_latency = max(recent_durations)
            else:
                self.p95_latency = recent_durations[0]
                self.p99_latency = recent_durations[0]
        else:
            # Decay if no recent activities
            self.throughput = max(0.0, self.throughput - 0.5)

    def get_snapshot(self) -> dict:
        now = time.time()
        # Force recompute if idle
        if now - self.last_update_time > 2.0:
            self._recompute_metrics(now)
            self.last_update_time = now
            
        # mock infra network metrics based on load
        message_queue_latency_ms = min(50.0, 2.0 + self.queue_depth * 0.01 + self.throughput * 0.5)
        heartbeat_delay_ms = 15.0 + self.active_workers * 0.2
        
        return {
            "status": "healthy" if self.failed_tasks < 10 else "degraded",
            "system": {
                "active_workers": self.active_workers,
                "queue_depth": self.queue_depth,
                "throughput_tiles_sec": round(self.throughput, 2),
                "failed_tasks": self.failed_tasks,
                "total_completed": self.total_completed
            },
            "performance": {
                "avg_render_time_s": round(self.avg_render_time, 3),
                "p95_latency_s": round(self.p95_latency, 3),
                "p99_latency_s": round(self.p99_latency, 3)
            },
            "network": {
                "msg_queue_latency_ms": round(message_queue_latency_ms, 1),
                "worker_heartbeat_ms": round(heartbeat_delay_ms, 1),
                "payload_size_kb": 256  # Base metric
            },
            "efficiency": {
                "speedup_s_n": round(self.speedup, 2),
                "efficiency_e_n": round(self.efficiency, 3),
                "parallel_fraction_p": self.parallel_fraction
            },
            "timestamp": now
        }

    def _trigger_update(self):
        """Push snapshot to all subscribers"""
        if not self.loop:
            return
            
        snapshot = self.get_snapshot()
        msg = json.dumps(snapshot)
        
        async def _publish():
            for q in list(self.subscribers):
                try:
                    # Put nowait or use timeout, to not block
                    q.put_nowait(msg)
                except asyncio.QueueFull:
                    pass
                    
        asyncio.run_coroutine_threadsafe(_publish(), self.loop)

metrics_aggregator = MetricsAggregator()
