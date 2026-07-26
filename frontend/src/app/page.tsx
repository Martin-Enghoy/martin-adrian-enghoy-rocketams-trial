"use client";

import { useState, useRef, useEffect } from "react";
import { RunReportControl } from "@/components/RunReportControl";
import { JobList } from "@/components/JobList";
import { ResultsTable } from "@/components/ResultsTable";

export default function Home() {
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const resultsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (selectedJobId && resultsRef.current) {
      resultsRef.current.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [selectedJobId]);
  
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
        <div ref={resultsRef}>
          <ResultsTable
            jobId={selectedJobId}
            onClose={() => setSelectedJobId(null)}
          />
        </div>
      )}
    </main>
  );
}