"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { BarChart2, Zap, Clock, Cpu, Activity } from "lucide-react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts";

interface BenchmarkData {
  p_fraction: number;
  base_frame_time: number;
  actual_data: { workers: number; actual_speedup: number; actual_time: number }[];
  theoretical_data: { workers: number; theoretical_speedup: number }[];
  total_jobs_analyzed: number;
}

export default function BenchmarkPage() {
  const [data, setData] = useState<BenchmarkData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchBenchmark() {
      try {
        const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        const res = await fetch(`${API_URL}/api/benchmark`);
        const json = await res.json();
        setData(json);
      } catch (err) {
        console.error("Failed to load benchmark data", err);
      } finally {
        setLoading(false);
      }
    }
    fetchBenchmark();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-zinc-500">
        <Activity className="w-6 h-6 animate-spin mr-2" />
        Loading Benchmark Models...
      </div>
    );
  }

  if (!data) return null;

  // Merge datasets by worker count for plotting
  const maxWorkers = Math.max(...data.theoretical_data.map(d => d.workers));
  const chartData = Array.from({ length: maxWorkers }, (_, i) => {
    const w = i + 1;
    const theoretical = data.theoretical_data.find(d => d.workers === w)?.theoretical_speedup || null;
    const actual = data.actual_data.find(d => d.workers === w)?.actual_speedup || null;
    return { workers: w, theoretical, actual };
  });

  const topSpeedup = data.actual_data.length > 0 
    ? Math.max(...data.actual_data.map(d => d.actual_speedup)) 
    : 0;

  return (
    <div className="flex flex-col min-w-0 h-screen">
      <header className="h-16 border-b border-zinc-800/50 flex items-center justify-between px-8 bg-zinc-950/50 backdrop-blur-md z-10 font-sans shrink-0">
        <div className="flex items-center gap-4">
          <h1 className="text-lg font-bold bg-gradient-to-r from-zinc-100 to-zinc-400 bg-clip-text text-transparent">
            Performance Benchmarks
          </h1>
          <Badge className="bg-emerald-500/10 text-emerald-500 border-none font-medium">
            Amdahl&apos;s Law
          </Badge>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-xs text-zinc-500">
            {data.total_jobs_analyzed} Job{data.total_jobs_analyzed !== 1 ? 's' : ''} Analyzed
          </span>
        </div>
      </header>

      <ScrollArea className="flex-1">
        <div className="p-8 max-w-7xl mx-auto w-full space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <Card className="bg-zinc-900/50 border-zinc-800">
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-xs font-medium text-zinc-400">Peak Speedup</CardTitle>
                <Zap className="w-4 h-4 text-emerald-500" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-zinc-100">{topSpeedup.toFixed(1)}x</div>
                <p className="text-[10px] text-zinc-500 mt-1">Relative to single core</p>
              </CardContent>
            </Card>

            <Card className="bg-zinc-900/50 border-zinc-800">
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-xs font-medium text-zinc-400">Parallelizable Fraction</CardTitle>
                <Cpu className="w-4 h-4 text-purple-500" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-zinc-100">{(data.p_fraction * 100).toFixed(1)}%</div>
                <p className="text-[10px] text-zinc-500 mt-1">Formula (P)</p>
              </CardContent>
            </Card>

            <Card className="bg-zinc-900/50 border-zinc-800">
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-xs font-medium text-zinc-400">Avg Base Frame Time</CardTitle>
                <Clock className="w-4 h-4 text-amber-500" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-zinc-100">{data.base_frame_time.toFixed(1)}s</div>
                <p className="text-[10px] text-zinc-500 mt-1">Baseline inference/render measure</p>
              </CardContent>
            </Card>
          </div>

          <Card className="bg-zinc-900/50 border-zinc-800">
            <CardHeader>
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                <BarChart2 className="w-4 h-4 text-zinc-500" />
                Scalability Analysis
              </CardTitle>
            </CardHeader>
            <CardContent className="h-[400px] pt-4">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
                  <XAxis 
                    dataKey="workers" 
                    stroke="#52525b" 
                    fontSize={12} 
                    tickLine={false} 
                    axisLine={false}
                    tickFormatter={(val) => `${val} Nodes`}
                  />
                  <YAxis 
                    stroke="#52525b" 
                    fontSize={12} 
                    tickLine={false} 
                    axisLine={false}
                    tickFormatter={(val) => `${val}x`}
                  />
                  <Tooltip 
                    contentStyle={{ backgroundColor: "#18181b", border: "1px solid #27272a", borderRadius: "8px" }}
                    labelStyle={{ color: "#a1a1aa", marginBottom: "4px" }}
                  />
                  <Legend verticalAlign="top" height={36} iconType="circle" />
                  <Line 
                    type="monotone" 
                    name="Theoretical Limit (Amdahl's)"
                    dataKey="theoretical" 
                    stroke="#a855f7" 
                    strokeWidth={2}
                    strokeDasharray="5 5"
                    dot={false}
                  />
                  <Line 
                    type="monotone" 
                    name="Actual Average Speedup"
                    dataKey="actual" 
                    stroke="#10b981" 
                    strokeWidth={3}
                    dot={{ r: 4, fill: "#10b981", strokeWidth: 0 }}
                    activeDot={{ r: 6, fill: "#10b981", stroke: "#fff" }}
                    connectNulls
                  />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </div>
      </ScrollArea>
    </div>
  );
}
