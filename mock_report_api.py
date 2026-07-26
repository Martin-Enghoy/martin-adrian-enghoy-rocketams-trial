"""RocketAMS trial task: mock report API.

Simulates the Amazon SP-API report lifecycle in miniature:
request a report, poll its status, download the finished document.

Run:
    pip install fastapi uvicorn
    uvicorn mock_report_api:app --port 9000

Behaviour (all intentional, do not "fix" this file):
- Reports sit IN_QUEUE for ~3s, then IN_PROGRESS for 10-30s, then DONE.
- ~15% of reports end in FATAL instead of DONE.
- Polling a report's status more than once every 2 seconds returns 429
  with a Retry-After header.
- At most 5 reports may be active (IN_QUEUE / IN_PROGRESS) at once;
  creating a sixth returns 429.
- The finished document is a gzipped TSV file. You must gunzip it yourself.
"""

import csv
import gzip
import io
import random
import time
import uuid

from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel

app = FastAPI(title="RocketAMS mock report API", version="1.0.0")

REPORT_TYPES = {"SALES_AND_TRAFFIC", "FBA_INVENTORY", "SETTLEMENT"}
MAX_ACTIVE_REPORTS = 5
POLL_INTERVAL_SECONDS = 2.0
QUEUE_SECONDS = 3.0
FAILURE_RATE = 0.15

# reportId -> {report_type, created_at, duration, fate, last_poll_ok}
_reports: dict = {}


class CreateReportRequest(BaseModel):
    reportType: str


def _status(report: dict) -> str:
    elapsed = time.monotonic() - report["created_at"]
    if elapsed < QUEUE_SECONDS:
        return "IN_QUEUE"
    if elapsed < QUEUE_SECONDS + report["duration"]:
        return "IN_PROGRESS"
    return report["fate"]


def _active_count() -> int:
    return sum(1 for r in _reports.values() if _status(r) in ("IN_QUEUE", "IN_PROGRESS"))


@app.get("/")
def root():
    return {
        "service": "RocketAMS mock report API",
        "reportTypes": sorted(REPORT_TYPES),
        "endpoints": [
            "POST /reports",
            "GET /reports/{reportId}",
            "GET /reports/{reportId}/document",
        ],
    }


@app.post("/reports", status_code=202)
def create_report(body: CreateReportRequest):
    if body.reportType not in REPORT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown reportType. Valid types: {sorted(REPORT_TYPES)}",
        )
    if _active_count() >= MAX_ACTIVE_REPORTS:
        raise HTTPException(
            status_code=429,
            detail="Too many active reports. Wait for one to finish.",
            headers={"Retry-After": "10"},
        )
    report_id = str(uuid.uuid4())
    _reports[report_id] = {
        "report_type": body.reportType,
        "created_at": time.monotonic(),
        "duration": random.uniform(10.0, 30.0),
        "fate": "FATAL" if random.random() < FAILURE_RATE else "DONE",
        "last_poll_ok": 0.0,
    }
    return {"reportId": report_id, "reportType": body.reportType, "processingStatus": "IN_QUEUE"}


@app.get("/reports/{report_id}")
def get_report(report_id: str):
    report = _reports.get(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")

    now = time.monotonic()
    if now - report["last_poll_ok"] < POLL_INTERVAL_SECONDS:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded: poll each report at most once every 2 seconds.",
            headers={"Retry-After": "2"},
        )
    report["last_poll_ok"] = now

    return {
        "reportId": report_id,
        "reportType": report["report_type"],
        "processingStatus": _status(report),
    }


@app.get("/reports/{report_id}/document")
def get_report_document(report_id: str):
    report = _reports.get(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")

    status = _status(report)
    if status == "FATAL":
        raise HTTPException(status_code=409, detail="Report failed; no document available.")
    if status != "DONE":
        raise HTTPException(status_code=409, detail=f"Report not ready (status: {status}).")

    # Deterministic per report so re-downloads match.
    rng = random.Random(report_id)
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter="\t")
    writer.writerow(
        ["date", "asin", "title", "units_ordered", "ordered_revenue",
         "sessions", "page_views", "buy_box_pct"]
    )
    asins = [f"B0{rng.randint(10_000_000, 99_999_999)}" for _ in range(10)]
    for day in range(30):
        date = f"2026-06-{day + 1:02d}"
        for i, asin in enumerate(asins):
            units = rng.randint(0, 120)
            sessions = units * rng.randint(5, 20) + rng.randint(0, 200)
            writer.writerow([
                date,
                asin,
                f"Sample Product {i + 1}",
                units,
                round(units * rng.uniform(15.0, 90.0), 2),
                sessions,
                int(sessions * rng.uniform(1.2, 2.5)),
                round(rng.uniform(60.0, 100.0), 1),
            ])

    payload = gzip.compress(buf.getvalue().encode("utf-8"))
    return Response(
        content=payload,
        media_type="application/gzip",
        headers={"Content-Disposition": f'attachment; filename="{report_id}.tsv.gz"'},
    )
