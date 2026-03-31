import socket
import time

import psutil


class MetricsCollector:
    """
    Collects system metrics using psutil.
    Does NOT depend on Redis — pure in-process collection.
    """

    def __init__(self, node_type: str = "slave"):
        self.node_id = f"{node_type}:{socket.gethostname()}"
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
