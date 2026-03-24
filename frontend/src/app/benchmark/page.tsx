"use client";

import { useEffect, useState } from "react";
import { getBenchmark } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { BarChart2, TrendingUp, Loader2, Info } from "lucide-react";
import {
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ComposedChart,
  Bar,
} from "recharts";

type BenchmarkData = Awaited<ReturnType<typeof getBenchmark>>;

export default function BenchmarkPage() {
  const [data, setData] = useState<BenchmarkData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const result = await getBenchmark();
        setData(result);
      } catch (err) {
        setError("Failed to fetch benchmark data.");
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-zinc-500" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="p-8 max-w-6xl mx-auto">
        <div className="bg-red-500/10 border border-red-500/20 text-red-400 p-4 rounded-lg text-sm">
          {error || "No data available."}
        </div>
      </div>
    );
  }

  // Combine theoretical and actual data for the chart
  const chartData = data.theoretical_data.map((td) => {
    const actual = data.actual_data.find((ad) => ad.workers === td.workers);
    let actual_speedup = null;
    if (actual && data.actual_data[0]?.avg_time) {
      actual_speedup = data.actual_data[0].avg_time / actual.avg_time;
    }

    return {
      workers: td.workers,
      "Theoretical Speedup": Number(td.theoretical_speedup.toFixed(2)),
      "Theoretical Time (s)": Number(td.theoretical_time.toFixed(2)),
      "Actual Speedup": actual_speedup ? Number(actual_speedup.toFixed(2)) : undefined,
      "Actual Time (s)": actual ? Number(actual.avg_time.toFixed(2)) : undefined,
    };
  });

  return (
    <div className="p-8 max-w-6xl mx-auto space-y-6">
      <div className="border-b border-zinc-800 pb-4">
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-100 flex items-center gap-2">
          <BarChart2 className="w-6 h-6 text-zinc-400" />
          Amdahl&apos;s Law Benchmarks
        </h1>
        <p className="text-sm text-zinc-500 mt-1">
          Scaling analysis of rendering performance based on historical jobs.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-zinc-400 font-medium">Parallel Portion (p)</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-semibold text-zinc-100">
              {(data.p_fraction * 100).toFixed(0)}%
            </div>
            <p className="text-xs text-zinc-500 mt-1">Estimated parallelizable fraction.</p>
          </CardContent>
        </Card>

        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-zinc-400 font-medium">Base Time (1 Worker)</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-semibold text-zinc-100">
              {data.base_time.toFixed(2)}s
            </div>
            <p className="text-xs text-zinc-500 mt-1">Average time for sequential execution.</p>
          </CardContent>
        </Card>

        <Card className="bg-zinc-900 border-zinc-800 bg-emerald-500/5">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-emerald-400 font-medium flex items-center gap-2">
              <TrendingUp className="w-4 h-4" /> Max Theoretical Speedup
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-semibold text-emerald-300">
              {data.p_fraction === 1 ? "∞" : (1 / (1 - data.p_fraction)).toFixed(2)}x
            </div>
            <p className="text-xs text-emerald-500/70 mt-1">As workers approach infinity.</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        {/* Speedup Chart */}
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader>
            <CardTitle className="text-sm font-medium text-zinc-200">Speedup vs Workers</CardTitle>
            <div className="flex items-center gap-2 text-xs text-zinc-400">
              <Info className="w-3 h-3" />
              S(s) = 1 / ((1 - p) + (p / s))
            </div>
          </CardHeader>
          <CardContent className="h-[400px]">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={chartData} margin={{ top: 20, right: 20, bottom: 20, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
                <XAxis dataKey="workers" stroke="#a1a1aa" fontSize={12} tickLine={false} axisLine={false} tickMargin={10} name="Workers" />
                <YAxis stroke="#a1a1aa" fontSize={12} tickLine={false} axisLine={false} tickFormatter={(v) => `${v}x`} />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#18181b', borderColor: '#27272a', borderRadius: '8px', color: '#f4f4f5' }}
                  itemStyle={{ color: '#f4f4f5' }}
                />
                <Legend iconType="circle" wrapperStyle={{ fontSize: '12px' }} />
                <Line
                  type="monotone"
                  dataKey="Theoretical Speedup"
                  stroke="#34d399"
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 6 }}
                />
                <Bar 
                  dataKey="Actual Speedup" 
                  fill="#818cf8" 
                  radius={[4, 4, 0, 0]}
                  maxBarSize={40}
                />
              </ComposedChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Render Time Chart */}
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader>
            <CardTitle className="text-sm font-medium text-zinc-200">Render Time vs Workers</CardTitle>
            <div className="flex items-center gap-2 text-xs text-zinc-400">
              <Info className="w-3 h-3" />
              Comparing actual times to Amdahl projection
            </div>
          </CardHeader>
          <CardContent className="h-[400px]">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={chartData} margin={{ top: 20, right: 20, bottom: 20, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
                <XAxis dataKey="workers" stroke="#a1a1aa" fontSize={12} tickLine={false} axisLine={false} tickMargin={10} />
                <YAxis stroke="#a1a1aa" fontSize={12} tickLine={false} axisLine={false} tickFormatter={(v) => `${v}s`} />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#18181b', borderColor: '#27272a', borderRadius: '8px', color: '#f4f4f5' }}
                  itemStyle={{ color: '#f4f4f5' }}
                />
                <Legend iconType="circle" wrapperStyle={{ fontSize: '12px' }} />
                <Line
                  type="monotone"
                  dataKey="Theoretical Time (s)"
                  stroke="#fbbf24"
                  strokeWidth={2}
                  strokeDasharray="5 5"
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="Actual Time (s)"
                  stroke="#f87171"
                  strokeWidth={2}
                  dot={{ r: 4 }}
                  activeDot={{ r: 6 }}
                />
              </ComposedChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
