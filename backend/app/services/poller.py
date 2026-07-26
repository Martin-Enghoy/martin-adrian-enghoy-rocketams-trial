import asyncio
import csv
import gzip
import io
import json
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.models import Job, ReportRow
from app.services.report_client import RateLimitError, ReportClient

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SSE Broadcaster
# ---------------------------------------------------------------------------

class Broadcaster:
  """Fan-out job updates to all connected SSE clients."""

  def __init__(self) -> None:
    self._queues: list[asyncio.Queue] = []

  def subscribe(self) -> asyncio.Queue:
    queue: asyncio.Queue = asyncio.Queue()
    self._queues.append(queue)
    logger.debug("SSE client subscribed (%d total)", len(self._queues))
    return queue

  def unsubscribe(self, queue: asyncio.Queue) -> None:
    try:
      self._queues.remove(queue)
    except ValueError:
      pass
    logger.debug("SSE client unsubscribed (%d remaining)", len(self._queues))

  async def broadcast(self, event: dict) -> None:
    for queue in self._queues:
      await queue.put(event)

# ---------------------------------------------------------------------------
# Poller Manager
# ---------------------------------------------------------------------------

class PollerManager:
  """Manages one asyncio.Task per active job."""

  def __init__(
    self,
    report_client: ReportClient,
    session_factory: async_sessionmaker[AsyncSession],
    broadcaster: Broadcaster,    
  ) -> None:
    self._report_client = report_client
    self._session_factory = session_factory
    self._broadcaster = broadcaster
    self._tasks: dict[str, asyncio.Task] = {}

  # Public API
  
  async def start_job(self, job_id: str) -> None:
    """Spawn a polling task for the given job."""
    if job_id in self._tasks:
      return

    task = asyncio.create_task(self._run(job_id), name=f"poll-{job_id[:8]}")
    self._tasks[job_id] = task
    task.add_done_callback(lambda _t: self._tasks.pop(job_id, None))

  async def resume_all(self) -> None:
    """On startup, resume polling for all non-terminal jobs."""
    async with self._session_factory() as session:
      result = await session.execute(
        select(Job).where(Job.status.in_(["queued", "running"]))
      )
      jobs = result.scalars().all()
    for job in jobs:
      logger.info("Resuming job %s (status=%s)", job.id, job.status)
      await self.start_job(job.id)

  async def shutdown(self) -> None:
    """Cancel all active polling tasks on app shutdown."""
    for task in self._tasks.values():
      task.cancel()
    if self._tasks:
      await asyncio.gather(*self._tasks.values(), return_exceptions=True)

  # Internal
  
  async def _run(self, job_id: str) -> None:
    """Full lifecycle for one job: create -> poll -> download/retry -> done."""
    try:
      # Load current state
      async with self._session_factory() as session:
        job = await session.get(Job, job_id)
        if not Job:
          logger.error("Job %s not found in DB", job_id)
          return
        report_type = job.report_type
        report_id = job.report_id
        retry_count = job.retry_count
        status = job.status

      # Step 1: If still queued, request a report from the mock API
      if status == "queued":
        report_id = await self._report_client.create_report(report_type)
        async with self._session_factory() as session:
          job = await session.get(Job, job_id)
          job.report_id = report_id
          job.status = "running"
          job.updated_at = datetime.now(timezone.utc)
          await session.commit()
          await self._broadcast_job(job)

      # Step 2: Poll until terminal state
      backoff = settings.poll_base_interval
      while True:
        await asyncio.sleep(backoff)

        try:
          api_status = await self._report_client.get_report_status(report_id)
          backoff = settings.poll_base_interval # reset backoff on success
        except RateLimitError as err:
          backoff = max(err.retry_after, backoff * 2)
          backoff = min(backoff, settings.poll_max_interval)
          logger.warning(
            "Rate limited polling job %s, backoff=%.1fs", job_id, backoff
          )
          continue

        logger.debug("Job %s -> mock API status: %s", job_id, api_status)

        if api_status in ("IN_QUEUE", "IN_PROGRESS"):
          continue

        if api_status == "DONE":
          await self._handle_done(job_id, report_id)
          return

        if api_status == "FATAL":
          if retry_count < settings.max_retries:
            # Auto-retry: request a new report, keep polling
            retry_count += 1
            logger.info(
              "Job %s FATAL -> auto-retry #%d", job_id, retry_count
            )
            report_id = await self._report_client.create_report(
              report_type
            )
            async with self._session_factory() as session:
              job = await session.get(Job, job_id)
              job.report_id = report_id
              job.retry_count = retry_count
              job.updated_at = datetime.now(timezone.utc)
              await session.commit()
              await self._broadcast_job(job)
            backoff = settings.poll_base_interval
            continue
          else:
            await self._mark_failed(
              job_id, "Report FATAL after exhausting retries"
            )
            return
    except asyncio.CancelledError:
      logger.info("Polling cancelled for job %s", job_id)
    except Exception as exc:
      logger.exception("Unexpected error polling job %s", job_id)
      await self._mark_failed(job_id, str(exc))

  async def _handle_done(self, job_id: str, report_id: str) -> None:
    """Download the gzipped TSV, decompress, parse, and persist rows."""
    raw = await self._report_client.download_document(report_id)
    tsv_text = gzip.decompress(raw).decode("utf-8")
    reader = csv.DictReader(io.StringIO(tsv_text), delimiter="\t")

    rows: list[ReportRow] = []
    for record in reader:
      rows.append(
        ReportRow(
          job_id=job_id,
          date=record["date"],
          asin=record["asin"],
          title=record["title"],
          units_ordered=int(record["units_ordered"]),
          ordered_revenue=float(record["ordered_revenue"]),
          sessions=int(record["sessions"]),
          page_views=int(record["page_views"]),
          buy_box_pct=float(record["buy_box_pct"]),
        )
      )
    
    async with self._session_factory() as session:
      job = await session.get(Job, job_id)
      session.add_all(rows)
      job.status = "completed"
      job.updated_at = datetime.now(timezone.utc)
      job.completed_at = datetime.now(timezone.utc)
      await session.commit()
      await self._broadcast_job(job)

    logger.info("Job %s completed. %d rows persisted", job_id, len(rows))

  async def _mark_failed(self, job_id: str, reason: str) -> None:
    """Mark a job as failed with an error message."""
    try:
      async with self._session_factory() as session:
        job = await session.get(Job, job_id)
        if job and job.status not in ("completed", "failed"):
          job.status = "failed"
          job.error_message = reason
          job.updated_at = datetime.now(timezone.utc)
          await session.commit()
          await self._broadcast_job(job)
          logger.info("Job %s marked failed: %s", job_id, reason)
    except Exception:
      logger.exception("Failed to mark job %s as failed", job_id)

  async def _broadcast_job(self, job: Job) -> None:
    """Push a job state update to all SSE clients."""
    await self._broadcaster.broadcast(
      {
        "id": job.id,
        "reportType": job.report_type,
        "status": job.status,
        "reportId": job.report_id,
        "retryCount": job.retry_count,
        "retryOfJobId": job.retry_of_job_id,
        "errorMessage": job.error_message,
        "createdAt": job.created_at.isoformat() if job.created_at else None,
        "updatedAt": job.updated_at.isoformat() if job.updated_at else None,
        "completedAt": (
          job.completed_at.isoformat() if job.completed_at else None
        ),
      }
    )