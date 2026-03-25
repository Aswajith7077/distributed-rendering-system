const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface Renderer {
  id: string;
  name: string;
  description: string;
  requires_scene_file: boolean;
  options: Array<{
    id: string;
    name: string;
    type: string;
    options?: string[];
  }>;
}

export interface WorkflowConfig {
  image_width: number;
  image_height: number;
  tiles_rows: number;
  tiles_cols: number;
  workers: number;
  renderer_type: "blender";
  blender_scene_file?: string;
  blender_engine?: "CYCLES" | "BLENDER_EEVEE_NEXT";
  blender_samples?: number;
  blender_device?: "CPU" | "GPU";
  render_mode: "coordinator" | "scheduler";
  frame_start?: number;
  frame_end?: number;
  output_type: "video" | "single_frame";
}


export interface Job {
  job_id: string;
  status: "pending" | "running" | "completed" | "failed";
  created_at: string;
  started_at?: string;
  completed_at?: string;
  workflow: Record<string, unknown>;
  completed_frames?: number;
  total_frames?: number;
  output_type?: "video" | "single_frame";
  result?: {
    workers: number;
    tiles: number;
    render_time_s: number;
    output_path: string;
    scheduler: string;
    download_url: string;
    tiles_dir: string;
  };
  error?: string;
}


export interface TilePreview {
  name: string;
  thumbnail: string;
}

async function fetchJSON<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });
  if (!response.ok) {
    throw new Error(`API Error: ${response.status} ${response.statusText}`);
  }
  return response.json();
}

export async function getRenderers(): Promise<{ renderers: Renderer[] }> {
  return fetchJSON(`${API_BASE}/api/renderers`);
}

export async function getJobs(): Promise<{ jobs: Job[]; total: number }> {
  return fetchJSON(`${API_BASE}/api/jobs`);
}

export async function getJob(jobId: string): Promise<Job> {
  return fetchJSON(`${API_BASE}/api/jobs/${jobId}`);
}

export async function createJob(config: WorkflowConfig): Promise<Job> {
  return fetchJSON(`${API_BASE}/api/jobs`, {
    method: "POST",
    body: JSON.stringify(config),
  });
}

export async function uploadJob(file: File, config: WorkflowConfig): Promise<Job> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("config", JSON.stringify(config));

  const response = await fetch(`${API_BASE}/api/upload/`, {
    method: "POST",
    body: formData,
    // Note: Fetch sets the multipart boundary automatically when body is FormData
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Upload failed");
  }

  return response.json();
}


export async function deleteJob(jobId: string): Promise<{ message: string; job_id: string }> {
  return fetchJSON(`${API_BASE}/api/jobs/${jobId}`, {
    method: "DELETE",
  });
}

export async function getTilesPreview(jobId: string): Promise<{ job_id: string; tiles: TilePreview[] }> {
  return fetchJSON(`${API_BASE}/api/tiles/${jobId}`);
}

export function getDownloadUrl(jobId: string): string {
  return `${API_BASE}/api/download/${jobId}`;
}

export function getFileUrl(jobId: string, filepath: string): string {
  return `${API_BASE}/api/files/${jobId}/${filepath}`;
}

export async function getHealth(): Promise<{
  status: string;
  timestamp: string;
  cpu: { percent: number };
  memory: { total: number; available: number; percent: number; used: number; free: number };
  disk: { total: number; used: number; free: number; percent: number };
  gpu: { available: boolean; gpus: Array<{ name: string; utilization_percent: number; memory_used_mb: number; memory_total_mb: number }> };
  uptime_seconds: number;
}> {
  return fetchJSON(`${API_BASE}/api/health`);
}

export async function getBenchmark(): Promise<{
  p_fraction: number;
  base_time: number;
  actual_data: Array<{ workers: number; avg_time: number }>;
  theoretical_data: Array<{ workers: number; theoretical_speedup: number; theoretical_time: number }>;
}> {
  return fetchJSON(`${API_BASE}/api/benchmark`);
}
