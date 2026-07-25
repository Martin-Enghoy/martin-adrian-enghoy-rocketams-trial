from datetime import datetime

from pydantic import BaseModel

class CreateJobRequest(BaseModel):
  reportType: str

class JobResponse(BaseModel):
  id: str
  reportType: str
  status: str
  reportId: str | None = None
  retryCount: int = 0
  retryOfJobId: str | None = None
  errorMessage: str | None = None
  createdAt: datetime
  updatedAt: datetime
  completedAt: datetime | None = None

class ReportRowResponse(BaseModel):
  date: str
  asin: str
  title: str
  unitsOrdered: int
  orderedRevenue: float
  sessions: int
  pageViews: int
  buyBoxPct: float

class JobRowsResponse(BaseModel):
  jobId: str
  totalRows: int
  rows: list[ReportRowResponse]