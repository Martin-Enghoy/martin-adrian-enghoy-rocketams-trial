import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select, func

from app.database import async_session_factory
from app.models import Job, ReportRow
from app.schemas import (
  CreateJobRequest,
  JobResponse,
  JobRowsResponse,
  ReportRowResponse,
)

router = APIRouter(prefix="/api")

VALID_REPORT_TYPES = {"SALES_AND_TRAFFIC", "FBA_INVENTORY", "SETTLEMENT"}

def _to_response(job: Job) -> JobResponse:
  return JobResponse(
    id=job.id,
    reportType=job.report_type,
    status=job.status,
    reportId=job.report_id,
    retryCount=job.retry_count,
    retryOfJobId=job.retry_of_job_id,
    errorMessage=job.error_message,
    createdAt=job.created_at,
    updatedAt=job.updated_at,
    completedAt=job.completed_at,
  )

@router.post("/jobs", status_code=201, response_model=JobResponse)
async def create_job(body: CreateJobRequest, request: Request):
  if body.reportType not in VALID_REPORT_TYPES:
    raise HTTPException(
      status_code=400,
      detail=f"Invalid Report Type. Valid: {sorted(VALID_REPORT_TYPES)}",
    )

  now = datetime.now(timezone.utc)
  job = Job(
    id=str(uuid.uuid4()),
    report_type=body.reportType,
    status="queued",
    created_at=now,
    updated_at=now,
  )

  async with async_session_factory() as session:
    session.add(job)
    await session.commit()
    await session.refresh(job)

  # Fire off the poller task (non-blocking)
  await request.app.state.poller_manager.start_job(job.id)

  return _to_response(job)

@router.get("/jobs", response_model=list[JobResponse])
async def list_jobs():
  async with async_session_factory() as session:
    result = await session.execute(select(Job).order_by(Job.created_at.desc()))
    jobs = result.scalars().all()
  return [_to_response(j) for j in jobs]

@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str):
  async with async_session_factory() as session:
    job = await session.get(Job, job_id)
  if not job:
    raise HTTPException(status_code=404, detail="Job not found.")
  return _to_response(job)

@router.get("/jobs/{job_id}/rows", response_model=JobRowsResponse)
async def get_job_rows(job_id: str, page: int = 1, page_size: int = 50):
  if page < 1:
    page = 1
  if page_size < 1 or page_size > 200:
    page_size = 50
        
  async with async_session_factory() as session:
    job = await session.get(Job, job_id)
    if not job:
      raise HTTPException(status_code=404, detail="Job not found.")
    if job.status != "completed":
      raise HTTPException(
        status_code=409,
        detail=f"Job not completed (status: {job.status})",
      )

    count_result = await session.execute(
      select(func.count()).select_from(ReportRow).where(ReportRow.job_id == job_id)
    )
    total_rows = count_result.scalar_one()

    # Paginated Query
    offset = (page - 1) * page_size
    result = await session.execute(
      select(ReportRow)
      .where(ReportRow.job_id == job_id)
      .order_by(ReportRow.id)
      .offset(offset)
      .limit(page_size)
    )
    rows = result.scalars().all()

  total_pages = max(1, (total_rows + page_size - 1) // page_size)

  return JobRowsResponse(
    jobId=job_id,
    totalRows=len(rows),
    page=page,
    pageSize=page_size,
    totalPages=total_pages,
    rows=[
      ReportRowResponse(
        date=row.date,
        asin=row.asin,
        title=row.title,
        unitsOrdered=row.units_ordered,
        orderedRevenue=row.ordered_revenue,
        sessions=row.sessions,
        pageViews=row.page_views,
        buyBoxPct=row.buy_box_pct,
      )
      for row in rows
    ],
  )