import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import async_session_factory, init_db
from app.routers import jobs, sse
from app.services.poller import Broadcaster, PollerManager
from app.services.report_client import ReportClient

logging.basicConfig(
  level=logging.INFO,
  format="%(asctime)s %(levelname)-8s %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
  # ── Startup ──────────────────────────────────────────────
  logger.info("Initializing database...")
  await init_db()

  report_client = ReportClient()
  broadcaster = Broadcaster()
  poller_manager = PollerManager(report_client, async_session_factory, broadcaster)

  app.state.report_client = report_client
  app.state.broadcaster = broadcaster
  app.state.poller_manager = poller_manager

  # Resume any jobs that were being processed before a restart
  await poller_manager.resume_all()
  logger.info("Backend ready.")

  yield

  # ── Shutdown ──────────────────────────────────────────────
  logger.info("Shutting down...")
  await poller_manager.shutdown()
  await report_client.close()


app = FastAPI(
  title="RocketAMS Report Pipeline",
  version="0.1.0",
  lifespan=lifespan,
)

app.include_router(jobs.router)
app.include_router(sse.router)

@app.get("/")
async def root():
  return {"service": "RocketAMS Report Pipeline", "status": "ok"}