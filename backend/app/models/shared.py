from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Text, text

from app.models.base import Base


class ServiceStatus(Base):
    __tablename__ = "service_status"

    # Legacy table: id has no redundant ix index; fetched_at is NOT NULL DEFAULT
    # now() in prod. Reflects prod's actual schema (alembic-migrations drift check).
    id = Column(Integer, primary_key=True, index=False)
    name = Column(String, nullable=False, unique=True)
    indicator = Column(String, nullable=False, default="none")   # none | minor | major | critical
    description = Column(String, nullable=True)
    icon = Column(String, nullable=True)
    page_url = Column(String, nullable=True)
    fetched_at = Column(
        DateTime(timezone=True), nullable=False, server_default=text("now()"),
        default=lambda: datetime.now(timezone.utc),
    )


class SourceRun(Base):
    """Per-source ingestion health: one upserted current-state row per scheduler
    job id (matching `scheduler.add_job(..., id=...)`). Not an append-only log —
    each run overwrites the row for its `source_id` (see ingestion-health AC-4).

    `last_run_at` is the last time the job fired (success or failure);
    `last_success_at` is preserved from the last *successful* run so the UI can
    show "last good data 5h ago" even while the latest run is failing.
    """
    __tablename__ = "source_runs"

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(String, nullable=False, unique=True)   # e.g. "kalshi_job"
    label = Column(String, nullable=False)                    # human-readable name
    status = Column(String, nullable=False, default="never_run")  # success|failure|never_run
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    last_success_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    item_count = Column(Integer, nullable=True)               # nullable: not every job returns one
    cadence_minutes = Column(Integer, nullable=False)         # expected interval → per-source staleness
