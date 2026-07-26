"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchJobRows } from "@/lib/api";
import { JobRowsResponse } from "@/types/types";

interface ResultsTableProps {
  jobId: string;
  onClose: () => void;
}

export function ResultsTable({ jobId, onClose }: ResultsTableProps) {
  const { data, isLoading, isError, error } = useQuery<JobRowsResponse>({
    queryKey: ["job-rows", jobId],
    queryFn: () => fetchJobRows(jobId),
    staleTime: Infinity, // Report data never changes
  });
  
  if (isLoading) {
    return (
      <div className="card">Loading report data...</div>
    );
  }
  
  if (isError) {
    return (
      <div className="card error-text">
        Failed to load rows: {(error as Error).message}
      </div>
    );
  }
  
  if (!data) {
    return null;
  }
  
  return (
    <div className="card">
      <div className="card-header">
        <h2>
          Report Results{" "}
          <span className="muted">({data.totalRows} rows)</span>
        </h2>
        <button className="btn-sm" onClick={onClose}>
          ✕ Close
        </button>
      </div>
      
      <div className="table-scroll">
        <table id="results-table">
          <thead>
            <tr>
              <th>Date</th>
              <th>ASIN</th>
              <th>Title</th>
              <th>Units</th>
              <th>Revenue</th>
              <th>Sessions</th>
              <th>Page Views</th>
              <th>Buy Box %</th>
            </tr>
          </thead>
          <tbody>
            {data.rows.map((row, index) => (
              <tr key={index}>
                <td>{row.date}</td>
                <td className="mono">{row.asin}</td>
                <td>{row.title}</td>
                <td className="num">{row.unitsOrdered}</td>
                <td className="num">{row.orderedRevenue.toFixed(2)}</td>
                <td className="num">{row.sessions.toLocaleString()}</td>
                <td className="num">{row.pageViews.toLocaleString()}</td>
                <td className="num">{row.buyBoxPct}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}