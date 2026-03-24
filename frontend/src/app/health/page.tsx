"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Activity, Cpu, Server, Loader2, Zap, Timer, Network, Layers, GitPullRequest } from "lucide-react";

// Update standard getHealth type + our new snapshot type
type HealthSnapshot = {
  status: string;
  system: {
    active_workers: number;
    queue_depth: number;
    throughput_tiles_sec: number;
    failed_tasks: number;
    total_completed: number;
  };
  performance: {
    avg_render_time_s: number;
    p95_latency_s: number;
    p99_latency_s: number;
  };
  network: {
    msg_queue_latency_ms: number;
    worker_heartbeat_ms: number;
    payload_size_kb: number;
  };
  efficiency: {
    speedup_s_n: number;
    efficiency_e_n: number;
    parallel_fraction_p: number;
  };
  timestamp: number;
};

export default function HealthPage() {
  const [data, setData] = useState<HealthSnapshot | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ws: WebSocket;
    let reconnectTimer: NodeJS.Timeout;

    const connect = () => {
      // Use the current host dynamically or fallback to localhost:8000
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      // Assuming backend runs on 8000. If we are proxying, handle accordingly.
      // Usually, development is on 3000 and backend on 8000.
      const host = window.location.hostname === "localhost" ? "localhost:8000" : window.location.host;
      const wsUrl = `${protocol}//${host}/ws/health`;

      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        setIsConnected(true);
        setError(null);
      };

      ws.onmessage = (event) => {
        try {
          const snapshot = JSON.parse(event.data);
          setData(snapshot);
        } catch (err) {
          console.error("Failed to parse websocket message", err);
        }
      };

      ws.onclose = () => {
        setIsConnected(false);
        // Attempt reconnect after 2s
        reconnectTimer = setTimeout(connect, 2000);
      };

      ws.onerror = (err) => {
        console.error("WebSocket error:", err);
        setError("WebSocket connection error");
        ws.close();
      };
    };

    connect();

    return () => {
      clearTimeout(reconnectTimer);
      if (ws) {
        ws.close();
      }
    };
  }, []);

  if (!data && !error) {
    return (
      <div className="flex h-full items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-zinc-500" />
      </div>
    );
  }

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      <div className="flex items-center justify-between border-b border-zinc-800 pb-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-zinc-100 flex items-center gap-2">
            <Server className="w-6 h-6 text-zinc-400" />
            SRE-Grade Cluster Health
          </h1>
          <p className="text-sm text-zinc-500 mt-1">Real-time distributed system telemetry</p>
        </div>
        <div className="flex items-center gap-2 bg-zinc-900/50 px-3 py-1.5 rounded-full border border-zinc-800">
          <div className={`w-2.5 h-2.5 rounded-full ${isConnected ? "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]" : "bg-red-500"} ${isConnected ? "animate-pulse" : ""}`} />
          <span className="text-sm font-medium text-zinc-300">
            {isConnected ? "Live Stream Connected" : "Connection Lost"}
          </span>
        </div>
      </div>

      {error && !isConnected && (
        <div className="bg-red-500/10 border border-red-500/20 text-red-400 p-4 rounded-lg text-sm flex items-center gap-2">
          <Activity className="w-4 h-4" />
          {error}. Retrying connection...
        </div>
      )}

      {data && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          
          {/* SYSTEM METRICS ROW */}
          <Card className="bg-zinc-900 border-zinc-800 col-span-1 lg:col-span-2">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium flex items-center gap-2 text-zinc-300">
                <Cpu className="w-4 h-4 text-emerald-400" />
                System Workload
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-3 gap-4">
                <div className="bg-zinc-950/50 p-4 rounded-lg border border-zinc-800/50 flex flex-col items-center justify-center">
                  <span className="text-3xl font-bold text-zinc-100">{data.system.active_workers}</span>
                  <span className="text-xs text-zinc-500 mt-1 uppercase tracking-wider font-semibold">Active Workers</span>
                </div>
                <div className="bg-zinc-950/50 p-4 rounded-lg border border-zinc-800/50 flex flex-col items-center justify-center">
                  <span className="text-3xl font-bold text-zinc-100">{data.system.queue_depth}</span>
                  <span className="text-xs text-zinc-500 mt-1 uppercase tracking-wider font-semibold">Queue Depth</span>
                </div>
                <div className="bg-zinc-950/50 p-4 rounded-lg border border-zinc-800/50 flex flex-col items-center justify-center">
                  <span className="text-3xl font-bold text-emerald-400">{data.system.throughput_tiles_sec.toFixed(1)}</span>
                  <span className="text-xs text-zinc-500 mt-1 uppercase tracking-wider font-semibold">Tiles / Sec</span>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* PERFORMANCE LATENCY ROW */}
          <Card className="bg-zinc-900 border-zinc-800 col-span-1 lg:col-span-2">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium flex items-center gap-2 text-zinc-300">
                <Timer className="w-4 h-4 text-amber-400" />
                Performance Latency
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-3">
                   <div className="flex justify-between items-center text-sm">
                     <span className="text-zinc-500">P95 Latency</span>
                     <span className="font-mono text-zinc-300">{data.performance.p95_latency_s.toFixed(3)}s</span>
                   </div>
                   <div className="flex justify-between items-center text-sm">
                     <span className="text-zinc-500">P99 Latency</span>
                     <span className="font-mono text-rose-400 font-semibold">{data.performance.p99_latency_s.toFixed(3)}s</span>
                   </div>
                </div>
                <div className="bg-zinc-950/50 p-3 rounded-lg border border-zinc-800/50 flex flex-col items-center justify-center">
                  <span className="text-2xl font-mono text-zinc-100">{data.performance.avg_render_time_s.toFixed(3)}s</span>
                  <span className="text-[10px] text-zinc-500 mt-1 uppercase tracking-wider">Avg Render Time</span>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* EFFICIENCY METRICS (The Differentiator) */}
          <Card className="bg-zinc-900 border-zinc-800 col-span-1 lg:col-span-2 relative overflow-hidden">
            <div className="absolute top-0 right-0 w-32 h-32 bg-blue-500/10 blur-3xl -mr-16 -mt-16 rounded-full" />
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium flex items-center gap-2 text-zinc-300">
                <Zap className="w-4 h-4 text-blue-400" />
                Amdahl&apos;s Efficiency Math
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4 relative z-10">
                <div className="grid grid-cols-2 gap-6">
                  <div className="space-y-1">
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-zinc-400">Speedup S(N)</span>
                      <span className="font-mono text-blue-300">{data.efficiency.speedup_s_n.toFixed(2)}x</span>
                    </div>
                    {/* Visual bar scaling with active workers vs perfect linear speedup */}
                    <div className="w-full h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                      <div 
                        className="h-full bg-blue-500 transition-all duration-500 ease-out" 
                        style={{ width: `${Math.min(100, (data.efficiency.speedup_s_n / Math.max(1, data.system.active_workers)) * 100)}%` }} 
                      />
                    </div>
                    <p className="text-[10px] text-zinc-500">vs theoretical {data.system.active_workers || 1}x</p>
                  </div>
                  
                  <div className="space-y-1">
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-zinc-400">Efficiency E(N)</span>
                      <span className="font-mono text-indigo-300">{(data.efficiency.efficiency_e_n * 100).toFixed(1)}%</span>
                    </div>
                    <div className="w-full h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                      <div 
                        className={`h-full transition-all duration-500 ease-out ${data.efficiency.efficiency_e_n > 0.8 ? 'bg-emerald-500' : 'bg-amber-500'}`} 
                        style={{ width: `${Math.min(100, data.efficiency.efficiency_e_n * 100)}%` }} 
                      />
                    </div>
                  </div>
                </div>
                
                <div className="border-t border-zinc-800/50 pt-3 mt-2 flex justify-between items-center text-xs">
                  <span className="text-zinc-500 flex items-center gap-1"><Layers className="w-3 h-3" /> Parallel Fraction (P)</span>
                  <span className="font-mono text-zinc-300 bg-zinc-800/50 px-2 py-0.5 rounded">{(data.efficiency.parallel_fraction_p * 100).toFixed(0)}%</span>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* NETWORK / INFRA METRICS */}
          <Card className="bg-zinc-900 border-zinc-800 col-span-1 lg:col-span-2">
             <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium flex items-center gap-2 text-zinc-300">
                <Network className="w-4 h-4 text-purple-400" />
                Network & RPC Health
              </CardTitle>
            </CardHeader>
            <CardContent>
               <div className="space-y-4">
                  <div className="flex justify-between items-center">
                    <div className="flex items-center gap-2">
                      <div className="w-8 h-8 rounded-lg bg-zinc-800/50 flex items-center justify-center border border-zinc-700/50">
                        <Activity className="w-4 h-4 text-purple-400" />
                      </div>
                      <span className="text-sm text-zinc-400">Message Queue Latency</span>
                    </div>
                    <span className="font-mono text-sm text-zinc-200">{data.network.msg_queue_latency_ms.toFixed(1)} ms</span>
                  </div>

                  <div className="flex justify-between items-center">
                    <div className="flex items-center gap-2">
                      <div className="w-8 h-8 rounded-lg bg-zinc-800/50 flex items-center justify-center border border-zinc-700/50">
                        <Activity className="w-4 h-4 text-cyan-400" />
                      </div>
                      <span className="text-sm text-zinc-400">Worker Heartbeat Delays</span>
                    </div>
                    <span className="font-mono text-sm text-zinc-200">{data.network.worker_heartbeat_ms.toFixed(1)} ms</span>
                  </div>
                  
                  <div className="flex justify-between items-center">
                    <div className="flex items-center gap-2">
                      <div className="w-8 h-8 rounded-lg bg-zinc-800/50 flex items-center justify-center border border-zinc-700/50">
                        <GitPullRequest className="w-4 h-4 text-zinc-500" />
                      </div>
                      <span className="text-sm text-zinc-400">Payload Size (Avg)</span>
                    </div>
                    <span className="font-mono text-sm text-zinc-500">{data.network.payload_size_kb} KB</span>
                  </div>
               </div>
            </CardContent>
          </Card>
          
        </div>
      )}
    </div>
  );
}
