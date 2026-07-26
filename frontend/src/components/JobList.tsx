"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchJobs } from "@/lib/api";
import { useSSE } from "@/hooks/useSSE";
import { Job } from "@/types/types";

interface JobListProps {
  selectedJobId: string | null;
  onSelectJob: (jobId: string) => void;
}

const STATUS_ICONS: Record<string, string> = {
  queued: "⏳",
  running: "🔄",
  completed: "✅",
  failed: "❌",
};

function timeAgo(dateStr: string): string {
  const seconds = Math.floor(
    (Date.now() - new Date(dateStr).getTime()) / 1000
  );
  if (seconds < 60) {
    return `${seconds}s ago`;    
  }
  
  const minutes = Math.floor(seconds / 60);  
  if (minutes < 60) {
    return `${minutes}m ago`;
  }
  
  const hours = Math.floor(minutes / 60);
  return `${hours}h ago`;
}

export function JobList({ selectedJobId, onSelectJob }: JobListProps) {
  const { isConnected } = useSSE();
  
  const { data: jobs = [], isLoading, isError } = useQuery<Job[]>({
    queryKey: ["jobs"],
    queryFn: fetchJobs,  
    //Fall back to polling when SSE is disconnected
    refetchInterval: isConnected ? false : 3000,
  });
  
  if (isLoading) {
    return (
      <div className="card">Loading jobs...</div>
    );
  }
  
  if (isError) {
    return (
      <div className="card error-text">Failed to load jobs</div>
    );
  }
  
  return (
    <div className="card">
      <div className="card-header">
        <h2>Jobs</h2>
        <span
          className={`connection-dot ${isConnected ? "connected" : "disconnected"}`}
          title={isConnected ? "SSE connected" : "SSE disconnected: polling fallback"}
        />
      </div>
      
      {jobs.length === 0 ? (
        <p className="empty-state">No jobs yet. Run a report to get started.</p>
      ) : (
        <table id="jobs-table">
          <thead>
            <tr>
              <th>Report Type</th>
              <th>Status</th>
              <th>Retry</th>
              <th>Created</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((job) => (
              <tr
                key={job.id}
                className={selectedJobId === job.id ? "selected" : ""}
              >
                <td>{job.reportType.replace(/_/g, " ")}</td>
                <td>
                  <span className={`status-badge status-${job.status}`}>
                    {STATUS_ICONS[job.status]} {job.status}
                  </span>                  
                </td>
                <td>{job.retryCount > 0 ? job.retryCount : "--"}</td>
                <td>{timeAgo(job.createdAt)}</td>
                <td>
                  {job.status === "completed" && (
                    <button
                      className="btn-sm"
                      onClick={() => onSelectJob(job.id)}
                    >
                      View Rows
                    </button>
                  )}
                  {job.status === "failed" && job.errorMessage && (
                    <span className="error-text" title={job.errorMessage}>
                      ⓘ
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}