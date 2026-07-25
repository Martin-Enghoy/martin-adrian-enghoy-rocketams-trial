import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
  pass

class Job(Base):
  __tablename__ = "jobs"

  id: Mapped[str] = mapped_column(
    String, primary_key=True, default=lambda: str(uuid.uuid4())
  )
  report_type: Mapped[str] = mapped_column(String, nullable=False)
  status: Mapped[str] = mapped_column(String, nullable=False, default="queued")
  report_id: Mapped[str | None] = mapped_column(String, nullable=True)
  retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
  retry_of_job_id: Mapped[str | None] = mapped_column(String, nullable=True)
  error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
  created_at: Mapped[datetime] = mapped_column(
    DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
  )
  updated_at: Mapped[datetime] = mapped_column(
    DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
  )
  completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

class ReportRow(Base):
  __tablename__ = "report_rows"

  id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  job_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
  date: Mapped[str] = mapped_column(String, nullable=False)
  asin: Mapped[str] = mapped_column(String, nullable=False)
  title: Mapped[str] = mapped_column(String, nullable=False)
  units_ordered: Mapped[int] = mapped_column(Integer, nullable=False)
  ordered_revenue: Mapped[float] = mapped_column(Float, nullable=False)
  sessions: Mapped[int] = mapped_column(Integer, nullable=False)
  page_views: Mapped[int] = mapped_column(Integer, nullable=False)
  buy_box_pct: Mapped[int] = mapped_column(Float, nullable=False)