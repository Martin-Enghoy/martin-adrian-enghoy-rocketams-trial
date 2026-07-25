from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models import Base

engine = create_async_engine(settings.database_url, echo=False)
async_session_factory = async_sessionmaker(
  engine, class_=AsyncSession, expire_on_commit=False
)

async def init_db():
  """Create all tables on startup. Swap for Alembic in production."""
  async with engine.begin() as conn:
    await conn.run_sync(Base.metadata.create_all)