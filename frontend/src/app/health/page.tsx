"use client";

import HealthDashboard from "@/components/HealthDashboard";
import { ScrollArea } from "@/components/ui/scroll-area";

export default function HealthPage() {
  return (
    <div className="flex flex-col min-w-0 h-screen">
      {/* ── Page header ─────────────────────────────────────────────────────── */}
      <header className="h-16 shrink-0 border-b border-zinc-800/50 flex items-center justify-between px-8 bg-zinc-950/50 backdrop-blur-md z-10">
        <h1 className="text-base font-bold bg-gradient-to-r from-zinc-100 to-zinc-400 bg-clip-text text-transparent">
          Cluster Health
        </h1>
        <span className="text-[10px] border border-zinc-800 text-zinc-500 uppercase tracking-widest font-bold px-3 py-1 rounded-full">
          Real-time Monitoring
        </span>
      </header>

      {/* ── Scrollable content ───────────────────────────────────────────────── */}
      <ScrollArea className="flex-1">
        <div className="p-8 max-w-7xl mx-auto w-full">
          <HealthDashboard />
        </div>
      </ScrollArea>
    </div>
  );
}
