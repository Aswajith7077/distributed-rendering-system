"use client";

import { useState, useEffect, useCallback } from "react";
import {
  getRenderers,
  getJobs,
  createJob,
  deleteJob,
  getTilesPreview,
  getDownloadUrl,
  type WorkflowConfig,
  type Job,
  type Renderer,
  type TilePreview,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Textarea } from "@/components/ui/textarea";
import {
  Play,
  Trash2,
  Download,
  RefreshCw,
  Image,
  Layers,
  Cpu,
  Grid3X3,
  Loader2,
  CheckCircle,
  XCircle,
  Clock,
  Server,
  ChevronDown,
  ChevronRight,
} from "lucide-react";

export default function Home() {
  const [renderers, setRenderers] = useState<Renderer[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [tilePreviews, setTilePreviews] = useState<TilePreview[]>([]);
  const [loadingTiles, setLoadingTiles] = useState(false);
  const [showConfig, setShowConfig] = useState(true);

  const [config, setConfig] = useState<WorkflowConfig>({
    image_width: 1920,
    image_height: 1080,
    tiles_rows: 4,
    tiles_cols: 4,
    workers: 4,
    renderer_type: "synthetic",
    blender_scene_file: "",
    blender_engine: "CYCLES",
    blender_samples: 128,
    blender_device: "CPU",
    render_mode: "coordinator",
  });

  const fetchRenderers = useCallback(async () => {
    try {
      const data = await getRenderers();
      setRenderers(data.renderers);
    } catch (err) {
      console.error("Failed to fetch renderers:", err);
    }
  }, []);

  const fetchJobs = useCallback(async () => {
    try {
      const data = await getJobs();
      setJobs(data.jobs);
      if (selectedJob) {
        const updated = data.jobs.find((j) => j.job_id === selectedJob.job_id);
        if (updated) setSelectedJob(updated);
      }
    } catch (err) {
      console.error("Failed to fetch jobs:", err);
    } finally {
      setLoading(false);
    }
  }, [selectedJob]);

  useEffect(() => {
    fetchRenderers();
    fetchJobs();
    
    const eventSource = new EventSource(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/events`);
    
    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "job_created" || data.type === "job_updated") {
          setJobs((prevJobs) => {
            const index = prevJobs.findIndex(j => j.job_id === data.job.job_id);
            if (index >= 0) {
              const newJobs = [...prevJobs];
              newJobs[index] = data.job;
              return newJobs;
            } else {
              return [data.job, ...prevJobs];
            }
          });
          
          setSelectedJob((prevSelected) => {
            if (prevSelected?.job_id === data.job.job_id) {
              if (data.job.status === "completed" && prevSelected.status !== "completed") {
                getTilesPreview(data.job.job_id).then(res => setTilePreviews(res.tiles)).catch(console.error);
              }
              return data.job;
            }
            return prevSelected;
          });
        } else if (data.type === "job_deleted") {
          setJobs(prev => prev.filter(j => j.job_id !== data.job_id));
          setSelectedJob(prev => prev?.job_id === data.job_id ? null : prev);
        }
      } catch (err) {
        // Ignore keepalive messages
      }
    };

    return () => eventSource.close();
  }, [fetchRenderers, fetchJobs]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const job = await createJob(config);
      setJobs((prev) => [job, ...prev]);
      setSelectedJob(job);
    } catch (err) {
      console.error("Failed to create job:", err);
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (jobId: string) => {
    try {
      await deleteJob(jobId);
      setJobs((prev) => prev.filter((j) => j.job_id !== jobId));
      if (selectedJob?.job_id === jobId) setSelectedJob(null);
    } catch (err) {
      console.error("Failed to delete job:", err);
    }
  };

  const handleViewResults = async (job: Job) => {
    if (selectedJob?.job_id !== job.job_id) {
      setTilePreviews([]);
    }
    setSelectedJob(job);
    if (job.status === "completed") {
      setLoadingTiles(true);
      try {
        const data = await getTilesPreview(job.job_id);
        setTilePreviews(data.tiles);
      } catch (err) {
        console.error("Failed to fetch tiles:", err);
      } finally {
        setLoadingTiles(false);
      }
    }
  };

  const handleDownload = (jobId: string) => {
    window.open(getDownloadUrl(jobId), "_blank");
  };

  return (
    <div className="min-h-screen bg-zinc-950">
      <header className="border-b border-zinc-800">
        <div className="max-w-6xl mx-auto px-6 py-5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Grid3X3 className="w-5 h-5 text-zinc-400" />
            <h1 className="text-sm font-medium tracking-tight text-zinc-200">
              Tile Renderer
            </h1>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => fetchJobs()}
            disabled={loading}
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          </Button>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
          <div className="lg:col-span-3 space-y-4">
            <Card>
              <CardHeader
                className="cursor-pointer hover:bg-zinc-900/50 transition-colors"
                onClick={() => setShowConfig(!showConfig)}
              >
                <div className="flex items-center justify-between">
                  <CardTitle className="text-sm font-medium flex items-center gap-2">
                    <Server className="w-4 h-4 text-zinc-500" />
                    Configuration
                  </CardTitle>
                  {showConfig ? (
                    <ChevronDown className="w-4 h-4 text-zinc-500" />
                  ) : (
                    <ChevronRight className="w-4 h-4 text-zinc-500" />
                  )}
                </div>
              </CardHeader>

              {showConfig && (
                <CardContent>
                  <form onSubmit={handleSubmit} className="space-y-6">
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label className="text-xs text-zinc-400">Width</Label>
                        <Input
                          type="number"
                          value={config.image_width}
                          onChange={(e) =>
                            setConfig({ ...config, image_width: +e.target.value })
                          }
                        />
                      </div>
                      <div className="space-y-2">
                        <Label className="text-xs text-zinc-400">Height</Label>
                        <Input
                          type="number"
                          value={config.image_height}
                          onChange={(e) =>
                            setConfig({ ...config, image_height: +e.target.value })
                          }
                        />
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label className="text-xs text-zinc-400">Tile Rows</Label>
                        <Input
                          type="number"
                          min={1}
                          max={32}
                          value={config.tiles_rows}
                          onChange={(e) =>
                            setConfig({ ...config, tiles_rows: +e.target.value })
                          }
                        />
                      </div>
                      <div className="space-y-2">
                        <Label className="text-xs text-zinc-400">Tile Cols</Label>
                        <Input
                          type="number"
                          min={1}
                          max={32}
                          value={config.tiles_cols}
                          onChange={(e) =>
                            setConfig({ ...config, tiles_cols: +e.target.value })
                          }
                        />
                      </div>
                    </div>

                    <div className="space-y-2">
                      <Label className="text-xs text-zinc-400">Workers</Label>
                      <Input
                        type="number"
                        min={1}
                        max={128}
                        value={config.workers}
                        onChange={(e) =>
                          setConfig({ ...config, workers: +e.target.value })
                        }
                      />
                    </div>

                    <div className="space-y-3">
                      <Label className="text-xs text-zinc-400">Render Mode</Label>
                      <div className="grid grid-cols-2 gap-2">
                        <Button
                          type="button"
                          variant={config.render_mode === "coordinator" ? "default" : "outline"}
                          size="sm"
                          onClick={() =>
                            setConfig({ ...config, render_mode: "coordinator" })
                          }
                          className="h-auto py-3"
                        >
                          <div className="text-left">
                            <div className="text-xs font-medium">Coordinator</div>
                            <div className="text-[10px] opacity-60">Static</div>
                          </div>
                        </Button>
                        <Button
                          type="button"
                          variant={config.render_mode === "scheduler" ? "default" : "outline"}
                          size="sm"
                          onClick={() =>
                            setConfig({ ...config, render_mode: "scheduler" })
                          }
                          className="h-auto py-3"
                        >
                          <div className="text-left">
                            <div className="text-xs font-medium">Scheduler</div>
                            <div className="text-[10px] opacity-60">Dynamic</div>
                          </div>
                        </Button>
                      </div>
                    </div>

                    <div className="space-y-2">
                      <Label className="text-xs text-zinc-400">Renderer</Label>
                      <Select
                        value={config.renderer_type}
                        onValueChange={(v) =>
                          setConfig({ ...config, renderer_type: v })
                        }
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {renderers.map((r) => (
                            <SelectItem key={r.id} value={r.id}>
                              {r.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>

                    {config.renderer_type === "blender" && (
                      <div className="space-y-4 p-4 border border-zinc-800 rounded-lg">
                        <Label className="text-xs text-zinc-400">Blender Settings</Label>
                        <div className="space-y-2">
                          <Label className="text-[10px] text-zinc-500">Scene File</Label>
                          <Input
                            placeholder="C:\path\to\scene.blend"
                            value={config.blender_scene_file || ""}
                            onChange={(e) =>
                              setConfig({ ...config, blender_scene_file: e.target.value })
                            }
                          />
                        </div>
                        <div className="grid grid-cols-2 gap-2">
                          <div className="space-y-1">
                            <Label className="text-[10px] text-zinc-500">Engine</Label>
                            <Select
                              value={config.blender_engine}
                              onValueChange={(v) =>
                                setConfig({ ...config, blender_engine: v })
                              }
                            >
                              <SelectTrigger className="h-8">
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="CYCLES">Cycles</SelectItem>
                                <SelectItem value="BLENDER_EEVEE_NEXT">Eevee</SelectItem>
                              </SelectContent>
                            </Select>
                          </div>
                          <div className="space-y-1">
                            <Label className="text-[10px] text-zinc-500">Device</Label>
                            <Select
                              value={config.blender_device}
                              onValueChange={(v) =>
                                setConfig({ ...config, blender_device: v })
                              }
                            >
                              <SelectTrigger className="h-8">
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="CPU">CPU</SelectItem>
                                <SelectItem value="GPU">GPU</SelectItem>
                              </SelectContent>
                            </Select>
                          </div>
                        </div>
                        <div className="space-y-1">
                          <Label className="text-[10px] text-zinc-500">Samples</Label>
                          <Input
                            type="number"
                            min={1}
                            value={config.blender_samples}
                            onChange={(e) =>
                              setConfig({ ...config, blender_samples: +e.target.value })
                            }
                            className="h-8"
                          />
                        </div>
                      </div>
                    )}

                    <Button type="submit" className="w-full" disabled={submitting}>
                      {submitting ? (
                        <>
                          <Loader2 className="w-4 h-4 animate-spin" />
                          Starting...
                        </>
                      ) : (
                        <>
                          <Play className="w-4 h-4" />
                          Start Render
                        </>
                      )}
                    </Button>
                  </form>
                </CardContent>
              )}
            </Card>

            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium flex items-center justify-between">
                  <span className="flex items-center gap-2">
                    <Clock className="w-4 h-4 text-zinc-500" />
                    Jobs
                  </span>
                  <Badge variant="secondary" className="text-xs">
                    {jobs.length}
                  </Badge>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ScrollArea className="h-[300px] pr-4">
                  {loading ? (
                    <div className="flex items-center justify-center py-12">
                      <Loader2 className="w-5 h-5 animate-spin text-zinc-500" />
                    </div>
                  ) : jobs.length === 0 ? (
                    <div className="text-center py-12 text-zinc-500 text-sm">
                      No jobs yet
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {jobs.map((job) => (
                        <div
                          key={job.job_id}
                          onClick={() => handleViewResults(job)}
                          className={`p-3 rounded-lg border cursor-pointer transition-all ${
                            selectedJob?.job_id === job.job_id
                              ? "border-zinc-600 bg-zinc-900"
                              : "border-zinc-800 hover:border-zinc-700"
                          }`}
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                              <StatusIcon status={job.status} />
                              <div>
                                <div className="font-mono text-xs text-zinc-300">
                                  {job.job_id}
                                </div>
                                <div className="text-[10px] text-zinc-500">
                                  {new Date(job.created_at).toLocaleTimeString()}
                                </div>
                              </div>
                            </div>
                            <div className="flex items-center gap-1">
                              {job.status === "completed" && (
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  className="h-7 w-7"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleDownload(job.job_id);
                                  }}
                                >
                                  <Download className="w-3 h-3" />
                                </Button>
                              )}
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-7 w-7"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleDelete(job.job_id);
                                }}
                              >
                                <Trash2 className="w-3 h-3" />
                              </Button>
                            </div>
                          </div>
                          {job.result && (
                            <div className="mt-2 flex gap-4 text-[10px] text-zinc-500">
                              <span>{job.result.tiles} tiles</span>
                              <span>{job.result.workers} workers</span>
                              {job.result.render_time_s && (
                                <span>{job.result.render_time_s.toFixed(2)}s</span>
                              )}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </ScrollArea>
              </CardContent>
            </Card>
          </div>

          <div className="lg:col-span-2">
            <Card className="sticky top-6">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium flex items-center gap-2">
                  <Image className="w-4 h-4 text-zinc-500" />
                  Output
                </CardTitle>
              </CardHeader>
              <CardContent>
                {!selectedJob ? (
                  <div className="text-center py-16 text-zinc-500 text-sm">
                    Select a job
                  </div>
                ) : selectedJob.status === "running" || selectedJob.status === "pending" ? (
                  <div className="space-y-4">
                    <div className="flex items-center justify-center py-8">
                      <Loader2 className="w-6 h-6 animate-spin text-zinc-400" />
                    </div>
                    <div className="space-y-1 text-center">
                      <p className="text-sm text-zinc-300 capitalize">
                        {selectedJob.status}
                      </p>
                      <p className="text-xs text-zinc-500">Rendering in progress</p>
                    </div>
                    <Progress value={null} className="h-1" />
                  </div>
                ) : selectedJob.status === "failed" ? (
                  <div className="text-center py-16">
                    <XCircle className="w-6 h-6 mx-auto mb-3 text-zinc-600" />
                    <p className="text-sm text-zinc-400">Failed</p>
                    {selectedJob.error && (
                      <p className="text-xs text-zinc-500 mt-2 max-h-24 overflow-auto">
                        {selectedJob.error}
                      </p>
                    )}
                  </div>
                ) : loadingTiles ? (
                  <div className="flex items-center justify-center py-16">
                    <Loader2 className="w-5 h-5 animate-spin text-zinc-500" />
                  </div>
                ) : (
                  <div className="space-y-4">
                    <div className="space-y-2">
                      <div className="aspect-video bg-zinc-900 rounded-lg overflow-hidden">
                        <img
                          src={`/api/download/${selectedJob.job_id}`}
                          alt="Render output"
                          className="w-full h-full object-contain"
                          onError={(e) => {
                            (e.target as HTMLImageElement).style.display = "none";
                          }}
                        />
                      </div>
                      <Button
                        variant="outline"
                        size="sm"
                        className="w-full"
                        onClick={() => handleDownload(selectedJob.job_id)}
                      >
                        <Download className="w-4 h-4" />
                        Download
                      </Button>
                    </div>

                    {tilePreviews.length > 0 && (
                      <div className="space-y-2">
                        <Label className="text-xs text-zinc-400">
                          Tiles ({tilePreviews.length})
                        </Label>
                        <div className="grid grid-cols-4 gap-1">
                          {tilePreviews.map((tile) => (
                            <div
                              key={tile.name}
                              className="aspect-square bg-zinc-900 rounded overflow-hidden"
                            >
                              <img
                                src={`data:image/png;base64,${tile.thumbnail}`}
                                alt={tile.name}
                                className="w-full h-full object-cover"
                              />
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {selectedJob.result && (
                      <div className="grid grid-cols-2 gap-2 text-xs">
                        <div className="p-2 bg-zinc-900 rounded">
                          <div className="text-zinc-500">Tiles</div>
                          <div className="font-mono text-zinc-200">
                            {selectedJob.result.tiles}
                          </div>
                        </div>
                        <div className="p-2 bg-zinc-900 rounded">
                          <div className="text-zinc-500">Workers</div>
                          <div className="font-mono text-zinc-200">
                            {selectedJob.result.workers}
                          </div>
                        </div>
                        <div className="p-2 bg-zinc-900 rounded">
                          <div className="text-zinc-500">Time</div>
                          <div className="font-mono text-zinc-200">
                            {selectedJob.result.render_time_s?.toFixed(2)}s
                          </div>
                        </div>
                        <div className="p-2 bg-zinc-900 rounded">
                          <div className="text-zinc-500">Mode</div>
                          <div className="font-mono text-zinc-200 capitalize">
                            {selectedJob.result.scheduler}
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      </main>
    </div>
  );
}

function StatusIcon({ status }: { status: string }) {
  switch (status) {
    case "completed":
      return <CheckCircle className="w-4 h-4 text-zinc-400" />;
    case "failed":
      return <XCircle className="w-4 h-4 text-zinc-600" />;
    case "running":
      return <Loader2 className="w-4 h-4 animate-spin text-zinc-400" />;
    default:
      return <Clock className="w-4 h-4 text-zinc-600" />;
  }
}
