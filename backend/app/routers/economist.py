from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import EconYouGovCrosstab, EconYouGovReport
from app.services.economist_yougov import (
    QUESTION_LABELS,
    QUESTION_ORDER,
    TRACKED_QUESTIONS,
)

router = APIRouter(prefix="/api/economist", tags=["economist"])


def _net_from_topline(topline: Optional[dict]) -> Optional[float]:
    tl = topline or {}
    if "Approve" in tl and "Disapprove" in tl:
        return tl["Approve"] - tl["Disapprove"]
    return None


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


# ── Available questions (for the frontend switcher) ───────────────────────────

class QuestionOut(BaseModel):
    key: str
    label: str
    report_count: int
    latest_net: Optional[float]


@router.get("/questions", response_model=List[QuestionOut])
def get_questions(db: Session = Depends(get_db)):
    """Tracked questions that actually have data, ordered Core-first."""
    rows = (
        db.query(EconYouGovCrosstab, EconYouGovReport)
        .join(EconYouGovReport, EconYouGovCrosstab.report_id == EconYouGovReport.id)
        .all()
    )
    # group by key, track count + most-recent topline
    agg: dict[str, dict] = {}
    for ct, rep in rows:
        a = agg.setdefault(ct.question_key, {"count": 0, "latest": None, "latest_tl": None})
        a["count"] += 1
        end = rep.end_date
        if a["latest"] is None or (end is not None and end > a["latest"]):
            a["latest"] = end
            a["latest_tl"] = ct.topline

    out = [
        QuestionOut(
            key=key,
            label=QUESTION_LABELS.get(key, key),
            report_count=a["count"],
            latest_net=_net_from_topline(a["latest_tl"]),
        )
        for key, a in agg.items()
    ]
    order = {k: i for i, k in enumerate(QUESTION_ORDER)}
    out.sort(key=lambda q: order.get(q.key, 999))
    return out


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
        out.append(TrendPoint(
            report_id=rep.id, end_date=rep.end_date,
            sample_size=rep.sample_size, topline=ct.topline or {},
            net=_net_from_topline(ct.topline),
        ))
    return out


# ── Full crosstab for one report+question ─────────────────────────────────────

class CrosstabOut(BaseModel):
    report_id: int
    end_date: Optional[date]
    sample_size: Optional[int]
    source_url: Optional[str]
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
        source_url=rep.source_url,
        question_key=ct.question_key, question_code=ct.question_code,
        question_title=ct.question_title, question_text=ct.question_text,
        blocks=ct.blocks,
    )
