from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import EconYouGovCrosstab, EconYouGovReport
from app.services.economist_yougov import TRACKED_QUESTIONS

router = APIRouter(prefix="/api/economist", tags=["economist"])


# ── Reports list ──────────────────────────────────────────────────────────────

class ReportOut(BaseModel):
    id: int
    source_url: str
    title: Optional[str]
    start_date: Optional[date]
    end_date: Optional[date]
    sample_size: Optional[int]
    sample_desc: Optional[str]
    fetched_at: datetime
    question_keys: List[str]

    model_config = {"from_attributes": True}


@router.get("/reports", response_model=List[ReportOut])
def get_reports(db: Session = Depends(get_db)):
    reports = (
        db.query(EconYouGovReport)
        .order_by(EconYouGovReport.end_date.desc().nullslast())
        .all()
    )
    return [
        ReportOut(
            id=r.id, source_url=r.source_url, title=r.title,
            start_date=r.start_date, end_date=r.end_date,
            sample_size=r.sample_size, sample_desc=r.sample_desc,
            fetched_at=r.fetched_at,
            question_keys=[c.question_key for c in r.crosstabs],
        )
        for r in reports
    ]


# ── Approval / topline time series ────────────────────────────────────────────

class TrendPoint(BaseModel):
    report_id: int
    end_date: Optional[date]
    sample_size: Optional[int]
    topline: dict
    net: Optional[float]


@router.get("/trend/{question_key}", response_model=List[TrendPoint])
def get_trend(question_key: str, db: Session = Depends(get_db)):
    """Time series of toplines for a tracked question (oldest -> newest)."""
    if question_key not in TRACKED_QUESTIONS:
        raise HTTPException(404, f"Unknown question_key. Tracked: {list(TRACKED_QUESTIONS)}")
    rows = (
        db.query(EconYouGovCrosstab, EconYouGovReport)
        .join(EconYouGovReport, EconYouGovCrosstab.report_id == EconYouGovReport.id)
        .filter(EconYouGovCrosstab.question_key == question_key)
        .order_by(EconYouGovReport.end_date.asc().nullsfirst())
        .all()
    )
    out = []
    for ct, rep in rows:
        tl = ct.topline or {}
        net = None
        if "Approve" in tl and "Disapprove" in tl:
            net = tl["Approve"] - tl["Disapprove"]
        out.append(TrendPoint(
            report_id=rep.id, end_date=rep.end_date,
            sample_size=rep.sample_size, topline=tl, net=net,
        ))
    return out


# ── Full crosstab for one report+question ─────────────────────────────────────

class CrosstabOut(BaseModel):
    report_id: int
    end_date: Optional[date]
    sample_size: Optional[int]
    question_key: str
    question_code: Optional[str]
    question_title: Optional[str]
    question_text: Optional[str]
    blocks: list

    model_config = {"from_attributes": True}


@router.get("/crosstab/{question_key}", response_model=CrosstabOut)
def get_crosstab(question_key: str, report_id: Optional[int] = None,
                 db: Session = Depends(get_db)):
    """Full demographic crosstab. Defaults to the most recent report."""
    q = (
        db.query(EconYouGovCrosstab, EconYouGovReport)
        .join(EconYouGovReport, EconYouGovCrosstab.report_id == EconYouGovReport.id)
        .filter(EconYouGovCrosstab.question_key == question_key)
    )
    if report_id is not None:
        q = q.filter(EconYouGovReport.id == report_id)
    else:
        q = q.order_by(EconYouGovReport.end_date.desc().nullslast())
    row = q.first()
    if not row:
        raise HTTPException(404, "No crosstab found for that question/report")
    ct, rep = row
    return CrosstabOut(
        report_id=rep.id, end_date=rep.end_date, sample_size=rep.sample_size,
        question_key=ct.question_key, question_code=ct.question_code,
        question_title=ct.question_title, question_text=ct.question_text,
        blocks=ct.blocks,
    )
