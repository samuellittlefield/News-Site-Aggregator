from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import VoteHubPoll
from app.services.votehub import compute_average

router = APIRouter(prefix="/api/votehub", tags=["votehub"])


class VoteHubPollOut(BaseModel):
    id: int
    votehub_id: str
    poll_type: str
    subject: Optional[str]
    pollster: Optional[str]
    sponsors: list
    start_date: Optional[datetime]
    end_date: Optional[datetime]
    sample_size: Optional[int]
    population: Optional[str]
    approve: Optional[float]
    disapprove: Optional[float]
    dem: Optional[float]
    rep: Optional[float]
    url: Optional[str]
    fetched_at: datetime

    model_config = {"from_attributes": True}


class PollSetOut(BaseModel):
    average: Optional[dict]
    polls: List[VoteHubPollOut]


def _recent_polls(db: Session, poll_type: str, limit: int) -> List[VoteHubPoll]:
    return (
        db.query(VoteHubPoll)
        .filter(VoteHubPoll.poll_type == poll_type)
        .order_by(VoteHubPoll.end_date.desc().nullslast())
        .limit(limit)
        .all()
    )


@router.get("/approval", response_model=PollSetOut)
def get_approval(db: Session = Depends(get_db)):
    return PollSetOut(
        average=compute_average(db, "approval"),
        polls=[VoteHubPollOut.model_validate(p) for p in _recent_polls(db, "approval", 25)],
    )


@router.get("/generic-ballot", response_model=PollSetOut)
def get_generic_ballot(db: Session = Depends(get_db)):
    return PollSetOut(
        average=compute_average(db, "generic-ballot"),
        polls=[VoteHubPollOut.model_validate(p) for p in _recent_polls(db, "generic-ballot", 25)],
    )


@router.get("/polls", response_model=List[VoteHubPollOut])
def list_polls(
    poll_type: str = Query("approval"),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
):
    return [VoteHubPollOut.model_validate(p) for p in _recent_polls(db, poll_type, limit)]
