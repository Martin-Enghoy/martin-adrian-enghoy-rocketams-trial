"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Job } from "@/types/types";

export function useSSE() {
  const queryClient = useQueryClient();
  const [isConnected, setIsConnected] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);
  
  useEffect(() => {
    const eventSource = new EventSource("/api/sse");
    eventSourceRef.current = eventSource;
    
    eventSource.onopen = () => {
      setIsConnected(true);
    };
    
    eventSource.addEventListener("job_update", (event: MessageEvent) => {
      const job: Job = JSON.parse(event.data);
      
      // Push into the jobs list cache
      queryClient.setQueryData<Job[]>(["jobs"], (old) => {
        if (!old) {
          return [job];
        }
        
        const index = old.findIndex((data) => data.id === job.id);
        if (index >= 0) {
          const updated = [...old];
          updated[index] = job;
          return updated;
        }
        
        // New job: prepend
        return [job, ...old];
      });
    });
    
    
    eventSource.onerror = () => {
      setIsConnected(false);
      // EventSource auto-reconnects by default
    };
    
    return () => {
      eventSource.close();
      eventSourceRef.current = null;
      setIsConnected(false);
    };
  }, [queryClient]);
  
  return { isConnected };
}
