"use client";

import {
  Cpu,
  HardDrive,
  Clock,
  Server,
  Wifi,
  WifiOff,
  Zap,
  Database,
} from "lucide-react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import {
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip,
  YAxis,
} from "recharts";
import type { NodeMetrics, CpuHistoryPoint } from "@/lib/types/metrics";
import { cn } from "@/lib/utils";

// ── helpers ───────────────────────────────────────────────────────────────────

function formatUptime(seconds: number): string {
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (d > 0) return `${d}d ${h}h ${m}m`;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m ${seconds % 60}s`;
}

function formatBytes(bytes: number): string {
  if (bytes >= 1_073_741_824) return `${(bytes / 1_073_741_824).toFixed(1)} GB`;
  if (bytes >= 1_048_576)     return `${(bytes / 1_048_576).toFixed(1)} MB`;
  if (bytes >= 1_024)         return `${(bytes / 1_024).toFixed(1)} KB`;
  return `${bytes} B`;
}

/** Returns Tailwind colour tokens based on a percentage value */
function stressColor(pct: number, thresholds = [60, 80]): { bar: string; text: string } {
  if (pct >= thresholds[1]) return { bar: "bg-red-500",   text: "text-red-400" };
  if (pct >= thresholds[0]) return { bar: "bg-amber-500", text: "text-amber-400" };
  return { bar: "bg-emerald-500", text: "text-emerald-400" };
}

// ── sub-components ────────────────────────────────────────────────────────────

function MetricRow({
  icon: Icon,
  label,
  value,
  percent,
  note,
}: {
  icon: React.ElementType;
  label: string;
  value: string;
  percent: number;
  note?: string;
}) {
  const color = stressColor(percent);
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-[11px]">
        <span className="text-zinc-500 flex items-center gap-1.5">
          <Icon className="w-3 h-3" />
          {label}
          {note && <span className="text-zinc-600">{note}</span>}
        </span>
        <span className={cn("font-mono font-semibold", color.text)}>{value}</span>
      </div>
      <div className="relative h-1.5 w-full rounded-full bg-zinc-800 overflow-hidden">
        <div
          className={cn("h-full rounded-full transition-all duration-700", color.bar)}
          style={{ width: `${Math.min(percent, 100)}%` }}
        />
      </div>
    </div>
  );
}

function CpuSparkline({ history }: { history: CpuHistoryPoint[] }) {
  if (history.length < 2) return null;

  const data = history.map((p) => ({ v: p.v }));

  return (
    <div className="h-10 w-full -mx-0.5">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 0, right: 0, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="cpuGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor="#60a5fa" stopOpacity={0.25} />
              <stop offset="95%" stopColor="#60a5fa" stopOpacity={0}    />
            </linearGradient>
          </defs>
          <YAxis domain={[0, 100]} hide />
          <Tooltip
            contentStyle={{ background: "#18181b", border: "1px solid #3f3f46", borderRadius: 8, fontSize: 10 }}
            formatter={(v: string | number | undefined | readonly (string | number)[]) => [v ? `${Number(v).toFixed(1)}%` : "0%", "CPU"]}
            labelFormatter={() => ""}
          />
          <Area
            type="monotone"
            dataKey="v"
            stroke="#60a5fa"
            strokeWidth={1.5}
            fill="url(#cpuGrad)"
            dot={false}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

// ── main card ─────────────────────────────────────────────────────────────────

interface NodeCardProps {
  node:    NodeMetrics;
  history: CpuHistoryPoint[];
}

export function NodeCard({ node, history }: NodeCardProps) {
  const isOnline = node.status === "online";
  const hostname = node.node_id.includes(":") ? node.node_id.split(":").pop()! : node.node_id;

  return (
    <Card
      className={cn(
        "relative overflow-hidden bg-zinc-900/40 border backdrop-blur-xl transition-all duration-300",
        isOnline
          ? "border-zinc-800/50 hover:border-zinc-700/60 shadow-xl shadow-black/20"
          : "border-zinc-800/30 opacity-60"
      )}
    >
      {/* Subtle top-edge glow when online */}
      {isOnline && (
        <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-emerald-500/40 to-transparent" />
      )}

      <CardHeader className="pb-3 pt-4 px-4">
        <div className="flex items-center justify-between">
          {/* Node identity */}
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-sky-500/10 text-sky-400 border border-sky-500/10">
              <Server className="w-4 h-4" />
            </div>
            <div>
              <p className="text-sm font-semibold text-zinc-100 leading-tight">{hostname}</p>
              <p className="text-[10px] uppercase tracking-widest text-zinc-500 mt-0.5 font-medium">
                {node.type}
              </p>
            </div>
          </div>

          {/* Status badge */}
          <Badge
            className={cn(
              "text-[10px] font-medium border px-2 py-0.5 flex items-center gap-1.5",
              isOnline
                ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-400"
                : "bg-red-500/10 border-red-500/20 text-red-400"
            )}
          >
            {isOnline ? (
              <Wifi className="w-2.5 h-2.5" />
            ) : (
              <WifiOff className="w-2.5 h-2.5" />
            )}
            {node.status}
          </Badge>
        </div>

        {/* CPU sparkline */}
        <div className="mt-3">
          <div className="flex items-center justify-between mb-1 text-[10px] text-zinc-600">
            <span className="flex items-center gap-1">
              <Cpu className="w-2.5 h-2.5" /> CPU History (last {history.length} ticks)
            </span>
            <span className="font-mono text-sky-400">{node.cpu.percent.toFixed(1)}%</span>
          </div>
          <CpuSparkline history={history} />
        </div>
      </CardHeader>

      <CardContent className="px-4 pb-4 space-y-3 pt-0">
        {/* Divider */}
        <div className="h-px bg-zinc-800/60" />

        {/* Per-core pill row */}
        {node.cpu.per_core && node.cpu.per_core.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {node.cpu.per_core.slice(0, 16).map((v, i) => {
              const c = stressColor(v);
              return (
                <div
                  key={i}
                  title={`Core ${i}: ${v.toFixed(0)}%`}
                  className={cn("w-4 h-4 rounded-sm text-[7px] flex items-center justify-center font-mono border border-zinc-800", c.bar, "opacity-80")}
                >
                  {v.toFixed(0)}
                </div>
              );
            })}
            {node.cpu.per_core.length > 16 && (
              <span className="text-[9px] text-zinc-600 self-center">+{node.cpu.per_core.length - 16}</span>
            )}
          </div>
        )}

        {/* Memory */}
        <MetricRow
          icon={Database}
          label="Memory"
          value={`${node.memory.percent.toFixed(1)}%`}
          percent={node.memory.percent}
          note={` · ${node.memory.used_gb.toFixed(1)} / ${node.memory.total_gb.toFixed(1)} GB`}
        />

        {/* Disk */}
        <MetricRow
          icon={HardDrive}
          label="Disk"
          value={`${node.disk.percent.toFixed(1)}%`}
          percent={node.disk.percent}
          note={` · ${node.disk.free_gb.toFixed(1)} GB free`}
        />

        {/* Network row */}
        <div className="flex items-center justify-between pt-1 text-[10px] text-zinc-500">
          <span className="flex items-center gap-1">
            <Zap className="w-3 h-3 text-violet-400" />
            Net ↑ {formatBytes(node.network.bytes_sent)} · ↓ {formatBytes(node.network.bytes_recv)}
          </span>
        </div>

        {/* GPU section */}
        {node.gpu && node.gpu.length > 0 ? (
          <div className="border-t border-zinc-800/50 pt-2 space-y-2">
            {node.gpu.map((g) => (
              <div key={g.id} className="space-y-1">
                <div className="flex justify-between text-[10px]">
                  <span className="text-zinc-500 truncate max-w-[70%]">{g.name}</span>
                  <span className="font-mono text-violet-400">{g.load_pct.toFixed(1)}%</span>
                </div>
                <Progress value={g.load_pct} className="h-1 bg-zinc-800" />
                <p className="text-[9px] text-zinc-600">
                  {g.memory_used_mb} / {g.memory_total_mb} MB · {g.temperature_c}°C
                </p>
              </div>
            ))}
          </div>
        ) : null}

        {/* Footer */}
        <div className="flex items-center gap-1 text-[10px] text-zinc-600 pt-1 border-t border-zinc-800/50">
          <Clock className="w-3 h-3" />
          Uptime {formatUptime(node.uptime_seconds)}
          <span className="ml-auto">
            {node.cpu.core_count} core{node.cpu.core_count !== 1 ? "s" : ""}
          </span>
        </div>
      </CardContent>
    </Card>
  );
}
