"use client";

import { useState } from "react";
import { RunReportControl } from "@/components/RunReportControl";
import { JobList } from "@/components/JobList";
import { ResultsTable } from "@/components/ResultsTable";

export default function Home() {
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  
  return (
    <main className="container">
      <header>
        <h1>🚀 RocketAMS Report Pipeline</h1>
      </header>
      
      <RunReportControl />
      <JobList
        selectedJobId={selectedJobId}
        onSelectJob={setSelectedJobId}
      />
      {selectedJobId && (
        <ResultsTable
          jobId={selectedJobId}
          onClose={() => setSelectedJobId(null)}
        />
      )}
    </main>
  );
}