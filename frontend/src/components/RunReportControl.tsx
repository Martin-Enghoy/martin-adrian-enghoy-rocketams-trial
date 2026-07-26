"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { createJob } from "@/lib/api";
import { Job, REPORT_TYPES, ReportType } from "@/types/types";

export function RunReportControl() {
  const [reportType, setReportType] = useState<ReportType>("SALES_AND_TRAFFIC");
  const queryClient = useQueryClient();
  
  const mutation = useMutation({
    mutationFn: (type: string) => createJob(type),
    onSuccess: (newJob: Job) => {
      // Immediately add to cache for instance feedback
      queryClient.setQueryData<Job[]>(["jobs"], (old) => {
        return old ? [newJob, ...old] : [newJob]
      });
    },
  });
  
  return (
    <div className="control-bar">
      <select
        id="report-type-select"
        value={reportType}
        onChange={(e) => setReportType(e.target.value as ReportType)}
        disabled={mutation.isPending}
      >
        {REPORT_TYPES.map((type) => (
          <option key={type} value={type}>
            {type.replace(/_/g, " ")}
          </option>
        ))}
      </select>
      
      <button
        id="run-report-btn"
        onClick={() => mutation.mutate(reportType)}
        disabled={mutation.isPending}
      >
        {mutation.isPending ? "Submitting..." : "Run Report"}
      </button>
      
      {mutation.isError && (
        <span className="error-text">
          {(mutation.error as Error).message}
        </span>
      )}
    </div>
  );
}