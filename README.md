# RocketAMS Report Pipeline

A full-stack mini-app that orchestrates long-running Amazon-style report jobs: requesting reports from an unreliable third-party API, polling for completion with backoff, handling failures with auto-retry, and surfacing results in a live dashboard.

## Architecture

```
Frontend (:3000)  ──proxy──▸  Backend (:8000)  ──HTTP──▸  Mock API (:9000)
     │                             │
     │◂──── SSE (direct) ─────────│
                                   │
                              SQLite (WAL)
```

- **Backend:** FastAPI (Python) with async polling, SQLAlchemy + SQLite, SSE broadcasting
- **Frontend:** Next.js 16 (App Router), TypeScript, TanStack React Query v5
- **Real-time:** Server-Sent Events for live job status, with refetchInterval fallback

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 22+
- npm

### 1. Start the Mock API

```bash
pip install fastapi uvicorn
uvicorn mock_report_api:app --port 9000
```

### 2. Start the Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8000 --reload
```

### 3. Start the Frontend

```bash
cd frontend
npm install
npm run dev
```

### 4. Open the Dashboard

Navigate to **http://localhost:3000**

### Docker (Alternative)

```bash
docker compose up --build
# Open http://localhost:3000
```

## Running Tests

```bash
cd backend
source .venv/bin/activate
python -m pytest tests/ -v
```

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Polling | In-process asyncio tasks | Fits trial scale; state persisted to DB for restart recovery |
| Real-time | SSE (direct to backend) | Simpler than WebSockets; Next.js proxy buffers streams, so SSE connects directly with CORS |
| Database | SQLite with WAL mode | Zero infrastructure; WAL enables concurrent reads during writes |
| Retry | Auto-retry FATAL once | ~15% failure rate makes auto-retry impactful; same job record, incremented retry_count |
| Backoff | Dynamic (Retry-After + exponential) | Respects API headers; exponential backoff capped at 10s as safety net |

## What I'd Do Next

If I stopped here, the next priorities would be:
- Alembic migrations instead of `create_all()` for schema evolution
- E2E tests with Playwright
- Rate limiting on the backend API itself

## Production Notes

What would change to run this reliably at **500 reports/day across 40 accounts**:

### Infrastructure
- **Task queue:** Replace in-process asyncio polling with **Celery + Redis**. Horizontal worker scaling. Dead-letter queue for permanently failed jobs.
- **Database:** **PostgreSQL** with connection pooling (PgBouncer). Partition `report_rows` table by month. The SQLAlchemy ORM layer makes this a config change.
- **Deployment:** Kubernetes with auto-scaling workers. Liveness probes on poller health. Graceful shutdown that drains active polls before termination.

### Reliability
- **Rate limiting:** Per-account rate limit tracking using a token bucket algorithm, respecting SP-API's per-marketplace limits.
- **Retry policy:** Configurable per-account retry limits with exponential backoff. Circuit breaker pattern for accounts with sustained failures.
- **Idempotency:** Deduplicate report requests by (account_id, report_type, date_range) to prevent wasted API calls.

### Observability
- **Logging:** Structured JSON logging (structlog) with correlation IDs per job.
- **Metrics:** Prometheus counters for job throughput, failure rate, poll latency, retry rate. Grafana dashboards.
- **Alerting:** PagerDuty alerts on failure rate spikes (>25% over 15-minute window).

### Multi-tenancy
- **Account isolation:** JWT auth with account claims. Row-level security in PostgreSQL.
- **Data pipeline:** Stream completed report rows to a data warehouse (BigQuery/Snowflake) for cross-account analytics. Decouple ingestion from serving.
