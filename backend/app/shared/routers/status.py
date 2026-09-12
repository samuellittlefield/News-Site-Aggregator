from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ServiceStatus, SourceRun
from app.shared.services.service_status import INDICATOR_ORDER
from app.shared.services.source_run import SOURCE_CADENCE

router = APIRouter(prefix="/api/status", tags=["status"])


class ServiceStatusOut(BaseModel):
    id: int
    name: str
    indicator: str
    description: Optional[str]
    icon: Optional[str]
    page_url: Optional[str]
    fetched_at: datetime

    model_config = {"from_attributes": True}


class SourceRunOut(BaseModel):
    source_id: str
    label: str
    status: str                          # success | failure | never_run
    last_run_at: Optional[datetime]
    last_success_at: Optional[datetime]
    error_message: Optional[str]
    item_count: Optional[int]
    cadence_minutes: int


@router.get("", response_model=List[ServiceStatusOut])
def get_statuses(db: Session = Depends(get_db)):
    rows = db.query(ServiceStatus).all()
    rows.sort(key=lambda r: (INDICATOR_ORDER.get(r.indicator, 99), r.name))
    return rows


@router.get("/sources", response_model=List[SourceRunOut])
def get_source_runs(db: Session = Depends(get_db)):
    """Per-source ingestion health (feature: ingestion-health).

    Returns exactly one entry per registered scheduler job — the canonical list
    comes from `SOURCE_CADENCE`, not the live `scheduler` object, so it stays
    correct even when the scheduler is gated off (e.g. DISABLE_SCHEDULER=1 in
    tests). Any registered source without a `SourceRun` row yet is synthesised as
    a distinct `never_run` entry rather than omitted (AC-6).
    """
    rows = {r.source_id: r for r in db.query(SourceRun).all()}
    out: List[SourceRunOut] = []
    for source_id, meta in SOURCE_CADENCE.items():
        row = rows.get(source_id)
        if row is None:
            out.append(SourceRunOut(
                source_id=source_id,
                label=meta.label,
                status="never_run",
                last_run_at=None,
                last_success_at=None,
                error_message=None,
                item_count=None,
                cadence_minutes=meta.cadence_minutes,
            ))
        else:
            out.append(SourceRunOut(
                source_id=row.source_id,
                label=row.label,
                status=row.status,
                last_run_at=row.last_run_at,
                last_success_at=row.last_success_at,
                error_message=row.error_message,
                item_count=row.item_count,
                cadence_minutes=row.cadence_minutes,
            ))
    return out
