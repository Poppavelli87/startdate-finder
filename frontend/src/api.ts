import type {
  AppConfigResponse,
  JobSettings,
  JobStatusResponse,
  ReviewResponse
} from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

export function apiUrl(path: string): string {
  return `${API_BASE_URL}${path}`;
}

async function parseJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `HTTP ${response.status}`);
  }
  return (await response.json()) as T;
}

export async function fetchConfig(): Promise<AppConfigResponse> {
  const response = await fetch(apiUrl("/api/config"));
  return parseJson<AppConfigResponse>(response);
}

export async function createJob(file: File, settings: JobSettings): Promise<string> {
  const form = new FormData();
  form.append("file", file);
  form.append("settings_json", JSON.stringify(settings));
  const response = await fetch(apiUrl("/api/jobs"), {
    method: "POST",
    body: form
  });
  const payload = await parseJson<{ job_id: string }>(response);
  return payload.job_id;
}

export async function fetchStatus(jobId: string): Promise<JobStatusResponse> {
  const response = await fetch(apiUrl(`/api/jobs/${jobId}/status`));
  return parseJson<JobStatusResponse>(response);
}

export async function fetchReview(jobId: string): Promise<ReviewResponse> {
  const response = await fetch(apiUrl(`/api/jobs/${jobId}/review`));
  return parseJson<ReviewResponse>(response);
}

export async function submitReview(
  jobId: string,
  selections: Array<{ row_index: number; candidate_index: number | null; no_match: boolean }>
): Promise<void> {
  const response = await fetch(apiUrl(`/api/jobs/${jobId}/review`), {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ selections })
  });
  await parseJson<{ ok: boolean }>(response);
}

export async function clearCache(): Promise<void> {
  const response = await fetch(apiUrl("/api/cache/clear"), { method: "POST" });
  await parseJson<{ cleared: boolean }>(response);
}
