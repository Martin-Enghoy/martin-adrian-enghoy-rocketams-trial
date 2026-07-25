import asyncio
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

class RateLimitError(Exception):
  """Raised when the mock API returns 429 on a poll request."""

  def __init__(self, retry_after: float):
    self.retry_after = retry_after
    super().__init__(f"Rate limited. Retry after {retry_after}s")

class ReportClient:
  def __init__(self) -> None:
    self.client = httpx.AsyncClient(
      base_url=settings.mock_api_url, timeout=30.0
    )

  async def create_report(self, report_type: str) -> str:
    """POST /reports -> returns reportId. Retries on 429 with backoff."""
    backoff = settings.poll_base_interval
    while True:
      response = await self._client.post(
        "/reports", json={"reportType": report_type}
      )

      if response.status_code == 202:
        return response.json()["reportId"]

      if response.status_code == 429:
        retry_after = float(response.headers.get("Retry-After", str(backoff)))
        wait = max(retry_after, backoff)
        logger.warning(
          "429 on create_report (type=%s), waiting %.1fs", report_type, wait
        )
        await asyncio.sleep(wait)
        backoff = min(backoff * 2, settings.poll_max_interval)
      else:
        response.raise_for_status()

  async def get_report_status(self, report_id: str) -> str:
    """GET /reports/{reportId} -> returns processingStatus. Raises RateLimitError on 429."""
    response = await self._client.get(f"/reports/{report_id}")
    if response.status_code == 429:
      retry_after = float(response.headers.get("Retry-After", "2"))
      raise RateLimitError(retry_after)

    response.raise_for_status()
    return response.json()["processingStatus"]

  async def download_document(self, report_id: str) -> bytes:
    """GET /reports/{reportId}/document -> returns gzipped bytes."""
    response = await self._client.get(f"/reports/{report_id}/document")
    response.raise_for_status()
    return response.content

  async def close(self) -> None:
    await self._client.aclose()