"use client";

import { cn } from "@/lib/utils";
import type { WSStatus } from "@/lib/useClusterMetrics";

interface StatusPillProps {
  status: WSStatus;
  lastTick: number | null;
}

const CONFIG: Record<WSStatus, { label: string; dot: string; text: string; bg: string; border: string }> = {
  connected:    { label: "Live",          dot: "bg-emerald-400 animate-pulse", text: "text-emerald-400", bg: "bg-emerald-400/10", border: "border-emerald-400/20" },
  connecting:   { label: "Connecting…",  dot: "bg-amber-400 animate-pulse",   text: "text-amber-400",   bg: "bg-amber-400/10",   border: "border-amber-400/20"   },
  reconnecting: { label: "Reconnecting…",dot: "bg-amber-400 animate-pulse",   text: "text-amber-400",   bg: "bg-amber-400/10",   border: "border-amber-400/20"   },
  disconnected: { label: "Disconnected", dot: "bg-red-500",                    text: "text-red-400",     bg: "bg-red-500/10",     border: "border-red-500/20"     },
};

export function StatusPill({ status, lastTick }: StatusPillProps) {
  const c = CONFIG[status];

  const tickLabel = lastTick
    ? `Updated ${Math.round((Date.now() - lastTick) / 1000)}s ago`
    : null;

  return (
    <div className="flex items-center gap-3">
      {tickLabel && (
        <span className="text-[10px] text-zinc-600 hidden sm:block">{tickLabel}</span>
      )}
      <div className={cn("flex items-center gap-2 px-3 py-1 rounded-full border text-[11px] font-medium", c.bg, c.border, c.text)}>
        <span className={cn("w-2 h-2 rounded-full shrink-0", c.dot)} />
        {c.label}
      </div>
    </div>
  );
}
