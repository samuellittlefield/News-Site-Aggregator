from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Trend, TrendSnapshot, WikiPage, WikiPageView

router = APIRouter(prefix="/api/trends", tags=["trends"])


class ArticleOut(BaseModel):
    id: int
    headline: Optional[str]
    url: Optional[str]
    source: Optional[str]
    published_at: Optional[datetime]
    description: Optional[str]

    model_config = {"from_attributes": True}


class SummaryOut(BaseModel):
    body: str
    generated_at: datetime

    model_config = {"from_attributes": True}


class WikiPageOut(BaseModel):
    id: int
    title: str
    description: Optional[str]
    extract: Optional[str]
    url: str
    thumbnail_url: Optional[str]
    is_primary: bool
    search_rank: int

    model_config = {"from_attributes": True}


class PageViewOut(BaseModel):
    view_date: date
    views: int

    model_config = {"from_attributes": True}


class TrendOut(BaseModel):
    id: int
    title: str
    traffic_volume: Optional[str]
    fetched_at: datetime
    first_seen_at: Optional[datetime]
    appearance_count: int
    category: Optional[str]
    velocity_abs: int
    velocity_pct: int
    rank_velocity: int
    geo: str
    summary: Optional[SummaryOut]
    wiki_pages: List[WikiPageOut]
    cluster_id: Optional[int]
    cluster_name: Optional[str] = None
    is_active: bool
    signal_score: float
    source: str
    sources_list: List[str] = []
    trend_window: Optional[str] = None
    validated_by: int = 0  # count of distinct source types validating this situation

    model_config = {"from_attributes": True}


class SnapshotOut(BaseModel):
    captured_at: datetime
    rank: Optional[int]
    traffic_volume: Optional[str]
    model_config = {"from_attributes": True}


class TrendDetailOut(TrendOut):
    articles: List[ArticleOut]


@router.get("", response_model=List[TrendOut])
def list_trends(limit: int = 50, db: Session = Depends(get_db)):
    """All active trends sorted by signal score — multi-source aggregation."""
    trends = (
        db.query(Trend)
        .filter(Trend.is_active == True, Trend.source == "rss")  # noqa: E712
        .order_by(Trend.signal_score.desc(), Trend.fetched_at.desc())
        .limit(limit)
        .all()
    )
    for t in trends:
        t.cluster_name = t.cluster.name if t.cluster else None
        # Count distinct source families (google, nyt, wikipedia, reddit)
        src_families = set()
        for s in (t.sources_list or []):
            if s.startswith("google"):
                src_families.add("google")
            elif s.startswith("nyt"):
                src_families.add("nyt")
            elif s == "wikipedia":
                src_families.add("wikipedia")
            elif s == "reddit":
                src_families.add("reddit")
        t.validated_by = len(src_families)
    return trends


@router.get("/rising", response_model=List[TrendOut])
def rising_trends(limit: int = 5, db: Session = Depends(get_db)):
    """
    Active trends with positive momentum, in priority order:
    1. Rank improvement (moved up in the feed since last refresh)
    2. First appearance (just broke into the feed — new entry is itself momentum)
    3. Traffic bucket increase
    """
    return (
        db.query(Trend)
        .filter(
            Trend.is_active == True,  # noqa: E712
            (Trend.rank_velocity > 0) | (Trend.appearance_count == 1) | (Trend.velocity_abs > 0),
        )
        .order_by(
            Trend.rank_velocity.desc(),
            Trend.appearance_count.asc(),   # appearance_count=1 sorts before 2,3…
            Trend.velocity_abs.desc(),
        )
        .limit(limit)
        .all()
    )


POLITICAL_KEYWORDS = [
    "congress", "senate", "president", "election", "republican", "democrat",
    "white house", "court", "supreme", "trump", "biden", "harris", "vote",
    "bill", "law", "policy", "government", "gop", "political", "legislation",
    "governor", "mayor", "primary", "rally", "campaign", "tariff",
]


def _is_political(trend: Trend) -> bool:
    text = f"{trend.title} {trend.summary.body if trend.summary else ''}".lower()
    return trend.category == "Politics" or any(kw in text for kw in POLITICAL_KEYWORDS)


@router.get("/political", response_model=List[TrendOut])
def political_trends(db: Session = Depends(get_db)):
    """Active political trending topics — keyword-broadened, sorted by velocity."""
    active = (
        db.query(Trend)
        .filter(Trend.is_active == True)  # noqa: E712
        .order_by(Trend.rank_velocity.desc(), Trend.velocity_abs.desc(), Trend.appearance_count.asc())
        .all()
    )
    results = [t for t in active if _is_political(t)]
    for t in results:
        t.cluster_name = t.cluster.name if t.cluster else None
    return results


@router.get("/anomalies", response_model=List[TrendOut])
def trend_anomalies(db: Session = Depends(get_db)):
    """
    Anomalous trends — two signals:
    1. SPIKES: Active trends that just broke in or shot up in rank
    2. DROPOFFS: Recently-inactive trends that had been consistently present
       ('suddenly stopped being searched')
    """
    from datetime import timedelta
    from sqlalchemy import or_

    cutoff = __import__("datetime").datetime.now(__import__("datetime").timezone.utc) - timedelta(hours=6)

    # Signal 1: active spikes — new or high rank velocity
    spikes = (
        db.query(Trend)
        .filter(
            Trend.is_active == True,  # noqa: E712
            or_(Trend.appearance_count == 1, Trend.rank_velocity >= 2),
        )
        .order_by(Trend.rank_velocity.desc(), Trend.appearance_count.asc())
        .all()
    )

    # Signal 2: dropoffs — was active for 3+ cycles, recently deactivated
    dropoffs = (
        db.query(Trend)
        .filter(
            Trend.is_active == False,  # noqa: E712
            Trend.appearance_count >= 3,
            Trend.fetched_at >= cutoff,
        )
        .order_by(Trend.appearance_count.desc())
        .limit(5)
        .all()
    )

    results = list({t.id: t for t in (spikes + dropoffs)}.values())
    for t in results:
        t.cluster_name = t.cluster.name if t.cluster else None
    return results


@router.get("/breakout", response_model=List[TrendOut])
def breakout_trends(limit: int = 8, db: Session = Depends(get_db)):
    """Topics surfaced by pytrends that aren't in the Google Trends RSS top feed."""
    return (
        db.query(Trend)
        .filter(Trend.is_active == True, Trend.source == "pytrends")  # noqa: E712
        .order_by(Trend.fetched_at.desc())
        .limit(limit)
        .all()
    )


@router.get("/{trend_id}/pageviews", response_model=List[PageViewOut])
def get_trend_pageviews(trend_id: int, db: Session = Depends(get_db)):
    """Daily Wikipedia page views for this trend's primary article (last 60 days)."""
    trend = db.query(Trend).filter(Trend.id == trend_id).first()
    if not trend:
        raise HTTPException(status_code=404, detail="Trend not found")
    primary = next((p for p in trend.wiki_pages if p.is_primary), None)
    if not primary:
        return []
    return (
        db.query(WikiPageView)
        .filter(WikiPageView.wiki_page_id == primary.id)
        .order_by(WikiPageView.view_date.asc())
        .all()
    )


@router.get("/{trend_id}/history", response_model=List[SnapshotOut])
def get_trend_history(trend_id: int, db: Session = Depends(get_db)):
    return (
        db.query(TrendSnapshot)
        .filter(TrendSnapshot.trend_id == trend_id, TrendSnapshot.rank.isnot(None))
        .order_by(TrendSnapshot.captured_at.asc())
        .all()
    )


@router.get("/{trend_id}", response_model=TrendDetailOut)
def get_trend(trend_id: int, db: Session = Depends(get_db)):
    trend = db.query(Trend).filter(Trend.id == trend_id).first()
    if not trend:
        raise HTTPException(status_code=404, detail="Trend not found")
    return trend
