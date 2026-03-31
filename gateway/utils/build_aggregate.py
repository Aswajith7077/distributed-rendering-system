from typing import Any
import time


def _build_aggregate(slave_registry: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """
    Merge all slave snapshots into a single response payload.
    Adds a gateway-level summary (node count, aggregate CPU/mem).
    """
    nodes = list(slave_registry.values())

    online_nodes = [n for n in nodes if n.get("status") == "online"]
    avg_cpu = (
        round(sum(n["cpu"]["percent"] for n in online_nodes) / len(online_nodes), 1)
        if online_nodes
        else 0.0
    )
    avg_mem = (
        round(sum(n["memory"]["percent"] for n in online_nodes) / len(online_nodes), 1)
        if online_nodes
        else 0.0
    )

    return {
        "event": "metrics_snapshot",
        "gateway_ts": time.time(),
        "summary": {
            "total_nodes": len(nodes),
            "online_nodes": len(online_nodes),
            "offline_nodes": len(nodes) - len(online_nodes),
            "avg_cpu_pct": avg_cpu,
            "avg_memory_pct": avg_mem,
        },
        "nodes": nodes,
    }
