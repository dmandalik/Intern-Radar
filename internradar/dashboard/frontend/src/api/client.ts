import { buildQueryString } from "../lib/filters";
import type { FilterOptions, JobListResponse, JobQuery, SettingsResponse, SummaryResponse, DashboardJob } from "../lib/types";

const API_BASE = "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
    },
    ...init,
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail ?? `Request failed with status ${response.status}`);
  }
  return (await response.json()) as T;
}

export function getHealth(): Promise<{ ok: boolean; database_ready: boolean; frontend_ready: boolean }> {
  return request("/health");
}

export function getSummary(): Promise<SummaryResponse> {
  return request("/summary");
}

export function getJobs(query: JobQuery): Promise<JobListResponse> {
  const params = buildQueryString(query);
  return request(`/jobs${params ? `?${params}` : ""}`);
}

export function getJob(jobId: string): Promise<DashboardJob> {
  return request(`/jobs/${jobId}`);
}

export function getFilters(): Promise<FilterOptions> {
  return request("/filters");
}

export function getLatestScan(): Promise<{ latest_scan: Record<string, unknown> | null }> {
  return request("/scan-runs/latest");
}

export function getSettings(): Promise<SettingsResponse> {
  return request("/settings");
}

export function postJobAction(jobId: string, action: string, notes?: string): Promise<{ ok: boolean; job: DashboardJob }> {
  return request(`/jobs/${jobId}/action`, {
    method: "POST",
    body: JSON.stringify({ action, notes }),
  });
}

export function postJobNotes(jobId: string, notes: string): Promise<{ ok: boolean; job: DashboardJob }> {
  return request(`/jobs/${jobId}/notes`, {
    method: "POST",
    body: JSON.stringify({ notes }),
  });
}

export function postExport(payload: Record<string, unknown>): Promise<{ ok: boolean; paths: string[] }> {
  return request("/export", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
