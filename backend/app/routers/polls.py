from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import CompetitiveDistrict, HousePoll
from app.services.house_polls import fetch_generic_ballot
from app.services.votehub import compute_average as compute_votehub_average

router = APIRouter(prefix="/api/polls", tags=["polls"])

COOK_HEIGHT = {
    "Toss-up": 60_000,
    "Lean D": 35_000,
    "Lean R": 35_000,
    "Likely D": 15_000,
    "Likely R": 15_000,
}


def _margin_to_color(margin: Optional[float], cook: Optional[str]) -> list[int]:
    """Returns [R, G, B, A] based on partisan margin (dem - rep)."""
    if margin is None:
        # Use Cook rating as proxy
        cook_colors = {
            "Toss-up": [150, 80, 160, 200],
            "Lean D":  [80, 140, 220, 200],
            "Lean R":  [220, 60,  80, 200],
            "Likely D":[30, 100, 220, 180],
            "Likely R":[210, 20,  40, 180],
        }
        return cook_colors.get(cook or "", [90, 90, 90, 180])

    if margin > 10:   return [30, 100, 220, 220]
    if margin > 5:    return [80, 140, 220, 220]
    if margin > 2:    return [130, 140, 200, 220]
    if margin > -2:   return [150, 80, 160, 220]
    if margin > -5:   return [200, 100, 110, 220]
    if margin > -10:  return [220, 60,  80, 220]
    return [210, 20, 40, 220]


# ── /api/polls/house ──────────────────────────────────────────────────────────

class HousePollOut(BaseModel):
    id: int
    poll_id: str
    pollster: str
    grade: Optional[str]
    state: str
    district: int
    start_date: Optional[datetime]
    end_date: Optional[datetime]
    sample_size: Optional[int]
    population: Optional[str]
    dem: Optional[float]
    rep: Optional[float]
    source_url: Optional[str]

    model_config = {"from_attributes": True}


@router.get("/house", response_model=List[HousePollOut])
def get_house_polls(limit: int = 200, db: Session = Depends(get_db)):
    return (
        db.query(HousePoll)
        .order_by(HousePoll.end_date.desc().nullslast(), HousePoll.fetched_at.desc())
        .limit(limit)
        .all()
    )


# ── /api/polls/house/districts ────────────────────────────────────────────────

class DistrictOut(BaseModel):
    state: str
    district: int
    cook_rating: Optional[str]
    dem_2024: Optional[float]
    rep_2024: Optional[float]
    margin_2024: Optional[float]
    lat: float
    lng: float
    incumbent_party: Optional[str]
    poll_count: int
    poll_intensity: float
    height: float
    latest_margin: Optional[float]
    latest_dem: Optional[float]
    latest_rep: Optional[float]
    latest_pollster: Optional[str]
    latest_date: Optional[datetime]
    color: list[int]


@router.get("/house/districts", response_model=List[DistrictOut])
def get_house_districts(db: Session = Depends(get_db)):
    districts = db.query(CompetitiveDistrict).all()
    now = datetime.now(timezone.utc)
    results = []

    # Compute max intensity for normalization
    max_intensity = 1.0

    district_polls: dict[tuple, list] = {}
    all_polls = db.query(HousePoll).all()
    for p in all_polls:
        key = (p.state, p.district)
        district_polls.setdefault(key, []).append(p)

    # First pass: compute intensities
    intensities: dict[tuple, float] = {}
    for dist in districts:
        key = (dist.state, dist.district)
        polls = district_polls.get(key, [])
        intensity = sum(
            1.0 / ((now - p.end_date).days + 1)
            for p in polls if p.end_date and p.end_date <= now
        )
        intensities[key] = intensity
        if intensity > max_intensity:
            max_intensity = intensity

    MAX_HEIGHT = 80_000.0

    for dist in districts:
        key = (dist.state, dist.district)
        polls = district_polls.get(key, [])
        intensity = intensities.get(key, 0.0)

        # Latest poll
        latest = max(polls, key=lambda p: p.end_date or datetime.min.replace(tzinfo=timezone.utc), default=None)
        latest_margin = (latest.dem - latest.rep) if latest and latest.dem and latest.rep else None

        # Height: polls drive it up, Cook rating sets the floor
        cook_floor = COOK_HEIGHT.get(dist.cook_rating or "", 10_000)
        if intensity > 0:
            poll_height = (intensity / max_intensity) * MAX_HEIGHT
            height = max(poll_height, cook_floor)
        else:
            height = float(cook_floor)

        color = _margin_to_color(latest_margin, dist.cook_rating)

        results.append(DistrictOut(
            state=dist.state,
            district=dist.district,
            cook_rating=dist.cook_rating,
            dem_2024=dist.dem_2024,
            rep_2024=dist.rep_2024,
            margin_2024=dist.margin_2024,
            lat=dist.lat,
            lng=dist.lng,
            incumbent_party=dist.incumbent_party,
            poll_count=len(polls),
            poll_intensity=round(intensity, 3),
            height=round(height, 1),
            latest_margin=round(latest_margin, 1) if latest_margin is not None else None,
            latest_dem=latest.dem if latest else None,
            latest_rep=latest.rep if latest else None,
            latest_pollster=latest.pollster if latest else None,
            latest_date=latest.end_date if latest else None,
            color=color,
        ))

    results.sort(key=lambda d: d.height, reverse=True)
    return results


# ── /api/polls/generic-ballot ─────────────────────────────────────────────────

class GenericBallotOut(BaseModel):
    source: str
    rep: float
    dem: float


@router.get("/generic-ballot", response_model=List[GenericBallotOut])
async def get_generic_ballot(db: Session = Depends(get_db)):
    rows = await fetch_generic_ballot(db)
    results = [GenericBallotOut(**r) for r in rows if r.get("rep") and r.get("dem")]
    votehub_avg = compute_votehub_average(db, "generic-ballot")
    if votehub_avg:
        results.append(GenericBallotOut(
            source="VoteHub (live average)",
            dem=votehub_avg["dem"],
            rep=votehub_avg["rep"],
        ))
    return results
