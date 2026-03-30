"use client";

import { Cpu, MemoryStick, Wifi, Server, Activity } from "lucide-react";
import type { ClusterSummary } from "@/lib/types/metrics";

interface SummaryBarProps {
  summary: ClusterSummary;
}

function Chip({
  icon: Icon,
  label,
  value,
  color,
}: {
  icon: React.ElementType;
  label: string;
  value: string;
  color: string;
}) {
  return (
    <div className="flex items-center gap-3 bg-zinc-900/60 border border-zinc-800/60 rounded-xl px-4 py-3 min-w-[140px] backdrop-blur-sm">
      <div className={`p-2 rounded-lg ${color}`}>
        <Icon className="w-4 h-4" />
      </div>
      <div>
        <p className="text-[10px] text-zinc-500 uppercase tracking-widest font-semibold">{label}</p>
        <p className="text-sm font-bold text-zinc-100 font-mono">{value}</p>
      </div>
    </div>
  );
}

export function SummaryBar({ summary }: SummaryBarProps) {
  return (
    <div className="w-full">
      {/* Top label row */}
      <div className="flex items-center gap-2 mb-3">
        <Activity className="w-4 h-4 text-zinc-500" />
        <span className="text-[11px] text-zinc-500 uppercase tracking-widest font-semibold">Cluster Overview</span>
      </div>

      {/* Chips */}
      <div className="flex flex-wrap gap-3">
        <Chip
          icon={Server}
          label="Total Nodes"
          value={String(summary.total_nodes)}
          color="bg-indigo-500/10 text-indigo-400"
        />
        <Chip
          icon={Wifi}
          label="Online"
          value={String(summary.online_nodes)}
          color="bg-emerald-500/10 text-emerald-400"
        />
        {summary.offline_nodes > 0 && (
          <Chip
            icon={Server}
            label="Offline"
            value={String(summary.offline_nodes)}
            color="bg-red-500/10 text-red-400"
          />
        )}
        <Chip
          icon={Cpu}
          label="Avg CPU"
          value={`${summary.avg_cpu_pct.toFixed(1)}%`}
          color={
            summary.avg_cpu_pct > 80
              ? "bg-red-500/10 text-red-400"
              : summary.avg_cpu_pct > 60
              ? "bg-amber-500/10 text-amber-400"
              : "bg-sky-500/10 text-sky-400"
          }
        />
        <Chip
          icon={MemoryStick}
          label="Avg Memory"
          value={`${summary.avg_memory_pct.toFixed(1)}%`}
          color={
            summary.avg_memory_pct > 85
              ? "bg-red-500/10 text-red-400"
              : summary.avg_memory_pct > 65
              ? "bg-amber-500/10 text-amber-400"
              : "bg-violet-500/10 text-violet-400"
          }
        />
      </div>
    </div>
  );
}
