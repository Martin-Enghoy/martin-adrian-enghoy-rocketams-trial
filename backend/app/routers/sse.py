import asyncio
import json

from fastapi import APIRouter, Request
from starlette.responses import StreamingResponse

router = APIRouter(prefix="/api")

@router.get("/sse")
async def sse_stream(request: Request):
  """Single multiplexed SSE stream for all job state changes."""
  broadcaster = request.app.state.broadcaster
  queue = broadcaster.subscribe()

  async def event_generator():
    try:
      while True:
        try:
          data = await asyncio.wait_for(queue.get(), timeout=30.0)
          yield f"event: job_update\ndata: {json.dumps(data)}\n\n"
        except:
          # Keepalive comment: prevents proxies from closing the connection
          yield ": keepalive\n\n"
    finally:
      broadcaster.unsubscribe(queue)

  return StreamingResponse(
    event_generator(),
    media_type="text/event-stream",
    headers={
      "Cache-Control": "no-cache",
      "Connection": "keep-alive",
      "X-Accel-Buffering": "no", # Prevents nginx/proxy buffering
    },
  )