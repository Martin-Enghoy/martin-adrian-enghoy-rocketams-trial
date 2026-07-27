import { Job, JobRowsResponse } from "@/types/types";

const BASE_API_URL = "/api";

export async function createJob(reportType: string): Promise<Job> {
  const response = await fetch(`${BASE_API_URL}/jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reportType }),
  });
  
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(detail.detail || `Failed to create job (${response.status}).`);
  }
  
  return response.json();
}

export async function fetchJobs(): Promise<Job[]> {
  const response = await fetch(`${BASE_API_URL}/jobs`);
  
  if (!response.ok) {
    throw new Error("Failed to fetch jobs.");
  }
  
  return response.json();
}

export async function fetchJobRows(
  jobId: string,
  page: number = 1,
  pageSize: number = 50,  
): Promise<JobRowsResponse> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });  
  const response = await fetch(`${BASE_API_URL}/jobs/${jobId}/rows?${params}`);
  
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(detail.detail || `Failed to fetch rows (${response.status})`);
  }
  
  return response.json();
}