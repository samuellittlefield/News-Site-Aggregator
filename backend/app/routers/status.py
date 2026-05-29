from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ServiceStatus
from app.services.service_status import INDICATOR_ORDER

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


@router.get("", response_model=List[ServiceStatusOut])
def get_statuses(db: Session = Depends(get_db)):
    rows = db.query(ServiceStatus).all()
    rows.sort(key=lambda r: (INDICATOR_ORDER.get(r.indicator, 99), r.name))
    return rows
