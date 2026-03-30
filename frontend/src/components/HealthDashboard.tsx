"use client";

import { useEffect, useState } from "react";
import { Activity } from "lucide-react";
import { useClusterMetrics } from "@/lib/useClusterMetrics";
import { StatusPill } from "@/components/health/StatusPill";
import { SummaryBar } from "@/components/health/SummaryBar";
import { NodeCard } from "@/components/health/NodeCard";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ── skeleton loader ───────────────────────────────────────────────────────────

function NodeSkeleton() {
  return (
    <div className="rounded-2xl border border-zinc-800/40 bg-zinc-900/30 p-4 space-y-4 animate-pulse">
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-xl bg-zinc-800" />
        <div className="space-y-1.5 flex-1">
          <div className="h-3 bg-zinc-800 rounded w-2/3" />
          <div className="h-2 bg-zinc-800/60 rounded w-1/3" />
        </div>
        <div className="h-5 w-14 bg-zinc-800 rounded-full" />
      </div>
      <div className="h-10 bg-zinc-800/50 rounded-lg" />
      <div className="space-y-2">
        <div className="h-2 bg-zinc-800 rounded w-full" />
        <div className="h-1.5 bg-zinc-800/60 rounded w-full" />
      </div>
      <div className="space-y-2">
        <div className="h-2 bg-zinc-800 rounded w-full" />
        <div className="h-1.5 bg-zinc-800/60 rounded w-full" />
      </div>
    </div>
  );
}

// ── empty state ───────────────────────────────────────────────────────────────

function EmptyState({ isConnecting }: { isConnecting: boolean }) {
  return (
    <div className="col-span-full py-24 flex flex-col items-center justify-center gap-4 rounded-2xl border border-dashed border-zinc-800 bg-zinc-900/20">
      <div className="relative">
        <Activity className="w-10 h-10 text-zinc-700" />
        {isConnecting && (
          <span className="absolute -top-1 -right-1 w-3 h-3 rounded-full bg-amber-400 animate-ping" />
        )}
      </div>
      <div className="text-center">
        <p className="text-sm font-medium text-zinc-400">
          {isConnecting ? "Connecting to gateway…" : "No nodes reporting"}
        </p>
        <p className="text-xs text-zinc-600 mt-1">
          {isConnecting
            ? "Establishing WebSocket connection"
            : "Waiting for worker nodes to come online"}
        </p>
      </div>
    </div>
  );
}

// ── main dashboard ────────────────────────────────────────────────────────────

export default function HealthDashboard() {
  const { snapshot, status, lastTick, cpuHistory } = useClusterMetrics(API_URL);

  // Track whether we've ever received a snapshot (to decide skeleton vs empty)
  const [everReceived, setEverReceived] = useState(false);
  useEffect(() => {
    if (snapshot) setEverReceived(true);
  }, [snapshot]);

  const isConnecting = status === "connecting" || status === "reconnecting";
  const nodes = snapshot?.nodes ?? [];
  const summary = snapshot?.summary ?? null;

  return (
    <div className="space-y-8">
      {/* ── Header row ─────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-xl bg-emerald-500/10 border border-emerald-500/10">
            <Activity className="w-5 h-5 text-emerald-400" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-zinc-100">Cluster Health</h2>
            <p className="text-[11px] text-zinc-500">
              Real-time metrics · ws/metrics
            </p>
          </div>
        </div>
        <StatusPill status={status} lastTick={lastTick} />
      </div>

      {/* ── Summary bar ─────────────────────────────────────────────────────── */}
      {summary && <SummaryBar summary={summary} />}

      {/* ── Node grid ───────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
        {/* Skeletons while first load is in progress */}
        {!everReceived && isConnecting && (
          <>
            <NodeSkeleton />
            <NodeSkeleton />
          </>
        )}

        {/* Actual node cards */}
        {nodes.map((node) => (
          <NodeCard
            key={node.node_id}
            node={node}
            history={cpuHistory[node.node_id] ?? []}
          />
        ))}

        {/* Empty state after connect with no nodes */}
        {everReceived && nodes.length === 0 && (
          <EmptyState isConnecting={isConnecting} />
        )}

        {/* Still connecting and nothing received */}
        {!everReceived && !isConnecting && (
          <EmptyState isConnecting={false} />
        )}
      </div>

      {/* ── Last updated footer ─────────────────────────────────────────────── */}
      {lastTick && (
        <p className="text-center text-[10px] text-zinc-700">
          Last broadcast received at{" "}
          {new Date(lastTick).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
          })}
          {" · "}
          {nodes.length} node{nodes.length !== 1 ? "s" : ""} reporting
        </p>
      )}
    </div>
  );
}
