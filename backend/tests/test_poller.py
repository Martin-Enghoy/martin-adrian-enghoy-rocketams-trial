"""Unit tests for polling / backoff logic and report client."""

import asyncio
import gzip

import httpx
import pytest
import respx

from app.services.report_client import RateLimitError, ReportClient

# ---------------------------------------------------------------------------
# ReportClient tests
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_api():
  """Activate respx mock for the mock API base URL."""
  with respx.mock(base_url="http://localhost:9000", assert_all_called=False) as r:
    yield r

@pytest.fixture
def client():
  return ReportClient()

@pytest.mark.asyncio
async def test_create_report_success(mock_api, client):
  """Happy path: report creation returns 202 with reportId."""
  mock_api.post("/reports").mock(
    return_value=httpx.Response(
      202,
      json={"reportId": "abc-123", "reportType": "SALES_AND_TRAFFIC", "processingStatus": "IN_QUEUE"},
    )
  )

  report_id = await client.create_report("SALES_AND_TRAFFIC")
  assert report_id == "abc-123"

@pytest.mark.asyncio
async def test_create_report_429_then_success(mock_api, client):
  """429 on first attempt, success on retry. Verifies backoff loop."""
  mock_api.post("/reports").mock(
    side_effect=[
      httpx.Response(429, headers={"Retry-After": "0.1"}, json={"detail": "Too many"}),
      httpx.Response(
        202,
        json={"reportId": "retry-ok", "reportType": "FBA_INVENTORY", "processingStatus": "IN_QUEUE"},
      ),
    ]
  )

  report_id = await client.create_report("FBA_INVENTORY")
  assert report_id == "retry-ok"
  assert mock_api.post("/reports").call_count == 2

@pytest.mark.asyncio
async def test_create_report_400_raises(mock_api, client):
  """Invalid report type returns 400: should raise immediately, not retry."""
  mock_api.post("/reports").mock(
    return_value=httpx.Response(400, json={"detail": "Unknown reportType"})
  )

  with pytest.raises(httpx.HTTPStatusError) as exc_info:
    await client.create_report("INVALID_TYPE")
  assert exc_info.value.response.status_code == 400

@pytest.mark.asyncio
async def test_get_report_status_success(mock_api, client):
  """Happy path: status poll returns processingStatus."""
  mock_api.get("/reports/abc-123").mock(
    return_value=httpx.Response(
      200,
      json={"reportId": "abc-123", "reportType": "SALES_AND_TRAFFIC", "processingStatus": "IN_PROGRESS"},
    )
  )

  status = await client.get_report_status("abc-123")
  assert status == "IN_PROGRESS"

@pytest.mark.asyncio
async def test_get_report_status_429_raises_rate_limit(mock_api, client):
  """429 on poll raises RateLimitError with retry_after value."""
  mock_api.get("/reports/abc-123").mock(
    return_value=httpx.Response(
      429,
      headers={"Retry-After": "2"},
      json={"detail": "Rate limit exceeded"},
    )
  )

  with pytest.raises(RateLimitError) as exc_info:
    await client.get_report_status("abc-123")
  assert exc_info.value.retry_after == 2.0

@pytest.mark.asyncio
async def test_download_document_success(mock_api, client):
  """Happy path: download returns gzipped content."""
  tsv_content = "date\tasin\n2026-06-01\tB012345678\n"
  payload = gzip.compress(tsv_content.encode("utf-8"))

  mock_api.get("/reports/abc-123/document").mock(
    return_value=httpx.Response(
      200,
      content=payload,
      headers={"Content-Type": "application/gzip"},
    )
  )

  raw = await client.download_document("abc-123")
  assert gzip.decompress(raw).decode("utf-8") == tsv_content

@pytest.mark.asyncio
async def test_download_document_409_raises(mock_api, client):
  """409 when report not ready: should raise."""
  mock_api.get("/reports/abc-123/document").mock(
    return_value=httpx.Response(409, json={"detail": "Report not ready"})
  )

  with pytest.raises(httpx.HTTPStatusError) as exc_info:
    await client.download_document("abc-123")
  assert exc_info.value.response.status_code == 409


# ---------------------------------------------------------------------------
# Backoff behavior tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_backoff_respects_retry_after_header(mock_api, client):
  """When 429 has Retry-After=0.1, create_report should wait at least that long."""
  call_times = []

  def track_call(request):
    call_times.append(asyncio.get_event_loop().time())
    if len(call_times) < 3:
      return httpx.Response(429, headers={"Retry-After": "0.1"}, json={"detail": "wait"})
    return httpx.Response(
      202,
      json={"reportId": "backoff-ok", "reportType": "SETTLEMENT", "processingStatus": "IN_QUEUE"},
    )

  mock_api.post("/reports").mock(side_effect=track_call)

  report_id = await client.create_report("SETTLEMENT")
  assert report_id == "backoff-ok"
  assert len(call_times) == 3

  # Each gap should be at least 0.1s (the Retry-After value)
  for i in range(1, len(call_times)):
    gap = call_times[i] - call_times[i - 1]
    assert gap >= 0.09, f"Gap {i}: {gap:.3f}s — too short, backoff not respected"