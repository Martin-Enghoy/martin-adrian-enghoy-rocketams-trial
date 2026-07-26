from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models import Base

engine = create_async_engine(
  settings.database_url,
  echo=False,
  connect_args={"timeout": 30}, # Wait up to 30s when DB gets locked
)

# Enable WAL mode on every new connection: allows concurrent read + one writer
@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_pragma(dbapi_conn, connection_record):
  cursor = dbapi_conn.cursor()
  cursor.execute("PRAGMA journal_mode=WAL")
  cursor.execute("PRAGMA busy_timeout=30000")
  cursor.close()

async_session_factory = async_sessionmaker(
  engine, class_=AsyncSession, expire_on_commit=False
)

async def init_db():
  """Create all tables on startup. Swap for Alembic in production."""
  async with engine.begin() as conn:
    await conn.run_sync(Base.metadata.create_all)