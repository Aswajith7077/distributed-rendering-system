// ── Types matching the gateway's /ws/metrics broadcast payload ─────────────

export interface CpuMetrics {
  percent: number;
  per_core: number[];
  core_count: number;
}

export interface MemoryMetrics {
  percent: number;
  used_gb: number;
  total_gb: number;
  available_gb: number;
}

export interface DiskMetrics {
  percent: number;
  used_gb: number;
  free_gb: number;
  total_gb: number;
}

export interface NetworkMetrics {
  bytes_sent: number;
  bytes_recv: number;
  packets_sent: number;
  packets_recv: number;
}

export interface GpuMetrics {
  id: number;
  name: string;
  load_pct: number;
  memory_used_mb: number;
  memory_total_mb: number;
  temperature_c: number;
}

export interface NodeMetrics {
  node_id: string;
  type: "slave" | "master" | string;
  status: "online" | "offline";
  uptime_seconds: number;
  timestamp: number;
  cpu: CpuMetrics;
  memory: MemoryMetrics;
  disk: DiskMetrics;
  network: NetworkMetrics;
  gpu: GpuMetrics[];
}

export interface ClusterSummary {
  total_nodes: number;
  online_nodes: number;
  offline_nodes: number;
  avg_cpu_pct: number;
  avg_memory_pct: number;
}

export interface MetricsSnapshot {
  event: "metrics_snapshot";
  gateway_ts: number;
  summary: ClusterSummary;
  nodes: NodeMetrics[];
}

/** Point in the rolling CPU history sparkline */
export interface CpuHistoryPoint {
  t: number;   // unix ms
  v: number;   // cpu percent 0-100
}
