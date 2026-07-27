export interface Job {
  id: string;
  reportType: string;
  status: "queued" | "running" | "completed" | "failed";
  reportId: string | null;
  retryCount: number;
  retryOfJobId: string | null;
  errorMessage: string | null;
  createdAt: string;
  updatedAt: string;
  completedAt: string | null;
}

export interface ReportRow {
  date: string;
  asin: string;
  title: string;
  unitsOrdered: number;
  orderedRevenue: number;
  sessions: number;
  pageViews: number;
  buyBoxPct: number;
}

export interface JobRowsResponse {
  jobId: string;
  totalRows: number;
  page: number;
  pageSize: number;
  totalPages: number;
  rows: ReportRow[];
}

export const REPORT_TYPES = [
  "SALES_AND_TRAFFIC",
  "FBA_INVENTORY",
  "SETTLEMENT",
] as const;

export type ReportType = (typeof REPORT_TYPES)[number];