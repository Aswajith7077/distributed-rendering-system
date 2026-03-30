"use client";

import { useState, useEffect, useCallback } from "react";
import {
  getRenderers,
  getJobs,
  uploadJob,
  deleteJob,
  getTilesPreview,
  getDownloadUrl,
  type WorkflowConfig,
  type Job,
  type Renderer,
  type TilePreview,
} from "@/lib/api";
import HealthDashboard from "@/components/HealthDashboard";
import { Sidebar } from "@/components/Sidebar";
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
  Activity, // Added Activity icon
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
  const [activeTab, setActiveTab] = useState<"render" | "health">("render");


  const [config, setConfig] = useState<WorkflowConfig>({
    image_width: 1920,
    image_height: 1080,
    tiles_rows: 4,
    tiles_cols: 4,
    workers: 4,
    renderer_type: "blender",
    blender_engine: "CYCLES",
    blender_samples: 128,
    blender_device: "CPU",
    render_mode: "scheduler",
    frame_start: 1,
    frame_end: 1,
    output_type: "video"
  });

  const [sceneFile, setSceneFile] = useState<File | null>(null);


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
              if (data.job.status === "completed" && prevSelected?.status !== "completed") {
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
    if (!sceneFile) {
      alert("Please select a .blend file");
      return;
    }
    
    setSubmitting(true);
    try {
      const job = await uploadJob(sceneFile, config);
      setJobs((prev) => [job, ...prev]);
      setSelectedJob(job);
    } catch (err) {
      console.error("Failed to create job:", err);
      alert(`Error: ${err instanceof Error ? err.message : String(err)}`);
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
    <div className="flex flex-col min-w-0 h-screen">
      <header className="h-16 border-b border-zinc-800/50 flex items-center justify-between px-8 bg-zinc-950/50 backdrop-blur-md z-10">
        <div className="flex items-center gap-8">
          <h1 className="text-lg font-bold bg-gradient-to-r from-zinc-100 to-zinc-400 bg-clip-text text-transparent">
            Blender Distributed Renderer
          </h1>
        </div>
        <div className="flex items-center gap-4">
          <Badge variant="outline" className="text-[10px] border-zinc-800 text-zinc-500 uppercase tracking-widest font-bold px-3 py-1">
            v2.4.1 Alpha
          </Badge>
          <a href="/benchmark">
            <Button variant="secondary" size="sm" className="bg-emerald-500/10 text-emerald-500 hover:bg-emerald-500/20 border-none font-medium text-xs">
              <Activity className="w-3 h-3 mr-1" />
              Scalability Benchmarks
            </Button>
          </a>
        </div>
      </header>

      <ScrollArea className="flex-1">
        <div className="p-8 max-w-7xl mx-auto w-full">
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
                          <Label className="text-xs text-zinc-400">Resolution Width</Label>
                          <Input
                            type="number"
                            value={config.image_width}
                            onChange={(e) =>
                              setConfig({ ...config, image_width: +e.target.value })
                            }
                            className="bg-black/20 border-zinc-800"
                          />
                        </div>
                        <div className="space-y-2">
                          <Label className="text-xs text-zinc-400">Resolution Height</Label>
                          <Input
                            type="number"
                            value={config.image_height}
                            onChange={(e) =>
                              setConfig({ ...config, image_height: +e.target.value })
                            }
                            className="bg-black/20 border-zinc-800"
                          />
                        </div>
                      </div>

                      <div className="space-y-4 p-4 border border-zinc-800 rounded-lg">
                        <Label className="text-xs text-zinc-400 font-semibold">Blender Scene</Label>
                        
                        <div className="space-y-2">
                          <Label className="text-[10px] text-zinc-500 uppercase tracking-wider">Upload .blend File</Label>
                          <Input
                            type="file"
                            accept=".blend"
                            onChange={(e) => setSceneFile(e.target.files?.[0] || null)}
                            className="bg-black/20 border-zinc-800 cursor-pointer"
                          />
                        </div>

                        <div className="grid grid-cols-2 gap-4">
                          <div className="space-y-1">
                            <Label className="text-[10px] text-zinc-500">Engine</Label>
                            <Select
                              value={config.blender_engine}
                              onValueChange={(v) =>
                                setConfig({ ...config, blender_engine: v as any })
                              }
                            >
                              <SelectTrigger className="h-9 bg-black/20">
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="CYCLES">Cycles</SelectItem>
                                <SelectItem value="BLENDER_EEVEE_NEXT">Eevee (Next)</SelectItem>
                              </SelectContent>
                            </Select>
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
                              className="h-9 bg-black/20"
                            />
                          </div>
                        </div>

                        <div className="grid grid-cols-2 gap-4">
                          <div className="space-y-1">
                            <Label className="text-[10px] text-zinc-500">Frame Start</Label>
                            <Input
                              type="number"
                              min={1}
                              value={config.frame_start}
                              onChange={(e) =>
                                setConfig({ ...config, frame_start: +e.target.value })
                              }
                              className="h-9 bg-black/20"
                            />
                          </div>
                          <div className="space-y-1">
                            <Label className="text-[10px] text-zinc-500">Frame End</Label>
                            <Input
                              type="number"
                              min={1}
                              value={config.frame_end}
                              onChange={(e) =>
                                setConfig({ ...config, frame_end: +e.target.value })
                              }
                              className="h-9 bg-black/20"
                            />
                          </div>
                        </div>

                        <div className="space-y-2">
                          <Label className="text-[10px] text-zinc-500">Output Preference</Label>
                          <Select
                            value={config.output_type}
                            onValueChange={(v) =>
                              setConfig({ ...config, output_type: v as any })
                            }
                          >
                            <SelectTrigger className="h-9 bg-black/20">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="video">Final Video (.mp4)</SelectItem>
                              <SelectItem value="single_frame">Single Image (.png)</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                      </div>

                      <Button type="submit" className="w-full bg-zinc-100 text-zinc-950 hover:bg-white" disabled={submitting}>
                        {submitting ? (
                          <>
                            <Loader2 className="w-4 h-4 animate-spin mr-2" />
                            Uploading & Splitting...
                          </>
                        ) : (
                          <>
                            <Play className="w-4 h-4 mr-2 fill-current" />
                            Initialize Render Job
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
                            <div className="mt-3 space-y-1">
                              <div className="flex justify-between text-[10px] text-zinc-500">
                                <span>
                                  {job.status === "completed" 
                                    ? "100%" 
                                    : job.total_frames 
                                      ? `${Math.round(((job.completed_frames || 0) / job.total_frames) * 100)}%`
                                      : "Preparing..."
                                  }
                                </span>
                                <span>
                                  {job.completed_frames || 0} / {job.total_frames || "?"} frames
                                </span>
                              </div>
                              <Progress 
                                value={job.status === "completed" ? 100 : ((job.completed_frames || 0) / (job.total_frames || 1)) * 100} 
                                className="h-1 bg-zinc-800"
                              />
                            </div>
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
                <CardContent className="p-0">
                  {!selectedJob ? (
                    <div className="flex flex-col items-center justify-center py-32 text-zinc-600">
                      <Image className="w-12 h-12 mb-4 opacity-10" />
                      <p className="text-sm font-light">Select a job to view output</p>
                    </div>
                  ) : selectedJob.status === "running" || selectedJob.status === "pending" ? (
                    <div className="p-8 space-y-6">
                      <div className="aspect-video bg-zinc-900/50 rounded-xl border border-zinc-800/50 flex flex-col items-center justify-center gap-4">
                        <Loader2 className="w-8 h-8 animate-spin text-zinc-700" />
                        <div className="text-center">
                          <p className="text-sm text-zinc-400 font-medium">Rendering in progress</p>
                          <p className="text-xs text-zinc-600 mt-1">
                            {selectedJob.completed_frames || 0} / {selectedJob.total_frames || "?"} frames processed
                          </p>
                        </div>
                      </div>
                      <Progress 
                        value={((selectedJob.completed_frames || 0) / (selectedJob.total_frames || 1)) * 100} 
                        className="h-1.5 bg-zinc-900" 
                      />
                    </div>
                  ) : selectedJob.status === "failed" ? (
                    <div className="p-16 text-center">
                      <XCircle className="w-8 h-8 mx-auto mb-4 text-zinc-800" />
                      <p className="text-sm text-zinc-400 font-medium">Processing Failed</p>
                      {selectedJob.error && (
                        <p className="text-xs text-zinc-600 mt-3 p-3 bg-red-950/20 border border-red-900/20 rounded-lg">
                          {selectedJob.error}
                        </p>
                      )}
                    </div>
                  ) : (
                    <div className="p-4 space-y-4">
                      <div className="relative group">
                        <div className="aspect-video bg-black rounded-xl overflow-hidden border border-zinc-800 shadow-2xl transition-transform duration-500 hover:scale-[1.01] flex items-center justify-center">
                          {selectedJob.output_type === "video" ? (
                            <video
                              src={`/api/download/${selectedJob.job_id}`}
                              controls
                              className="w-full h-full"
                            />
                          ) : (
                            <img
                              src={`/api/download/${selectedJob.job_id}`}
                              alt="Render output"
                              className="w-full h-full object-contain"
                            />
                          )}
                        </div>
                        <div className="absolute top-4 right-4 opacity-0 group-hover:opacity-100 transition-opacity">
                          <Badge className="bg-black/60 backdrop-blur-md border-zinc-700 text-zinc-200">
                            {selectedJob.output_type === "video" ? "MP4" : "PNG"}
                          </Badge>
                        </div>
                      </div>

                      <div className="flex gap-3">
                        <Button
                          variant="secondary"
                          className="flex-1 bg-zinc-200 text-zinc-950 hover:bg-white font-semibold transition-all"
                          onClick={() => handleDownload(selectedJob.job_id)}
                        >
                          <Download className="w-4 h-4 mr-2" />
                          Download Final Result
                        </Button>
                      </div>

                      {selectedJob.result && (
                        <div className="grid grid-cols-3 gap-3 text-[11px]">
                          <div className="p-3 bg-zinc-900/50 rounded-xl border border-zinc-800/50">
                            <div className="text-zinc-600 mb-1">Time</div>
                            <div className="font-mono text-zinc-300">
                              {selectedJob.result.render_time_s?.toFixed(2)}s
                            </div>
                          </div>
                          <div className="p-3 bg-zinc-900/50 rounded-xl border border-zinc-800/50">
                            <div className="text-zinc-600 mb-1">Frames</div>
                            <div className="font-mono text-zinc-300">
                              {selectedJob.total_frames}
                            </div>
                          </div>
                          <div className="p-3 bg-zinc-900/50 rounded-xl border border-zinc-800/50">
                            <div className="text-zinc-600 mb-1">Engine</div>
                            <div className="font-mono text-zinc-300">
                              {(selectedJob.workflow as any)?.blender_engine || "CYCLES"}
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
        </div>
      </ScrollArea>
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
