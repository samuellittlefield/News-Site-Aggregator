import collections
import csv
import os
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Candidate, CompetitiveDistrict, HousePoll, HouseRetirement
from app.services.house_polls import fetch_generic_ballot
from app.services.votehub import compute_average as compute_votehub_average

router = APIRouter(prefix="/api/polls", tags=["polls"])

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def _load_csv(name: str) -> list:
    with open(os.path.join(_DATA_DIR, name), newline="") as f:
        return list(csv.DictReader(f))


# Vendored full-coverage baselines (tiny, loaded once at import).
_PRIORS = _load_csv("house_priors.csv")  # state, district, pres2024_margin, house2024_margin, incumbent_party
_HEX = {(r["state"], r["district"]): (int(r["q"]), int(r["r"])) for r in _load_csv("house_hexgrid.csv")}

def _cand_district(district: str) -> int:
    """house_priors uses 'AL' for at-large; FEC/poll tables key at-large as 0."""
    return 0 if district == "AL" else int(district)


def _derived_rating(margin: Optional[float]) -> str:
    """Full-coverage competitiveness label from the presidential margin (D−R),
    used where there's no official Cook rating. Thresholds are tuned to pres
    margins, which run wider than race ratings."""
    if margin is None:
        return "Unknown"
    a = abs(margin)
    side = "D" if margin > 0 else "R"
    if a < 4:
        return "Toss-up"
    if a < 9:
        return f"Lean {side}"
    if a < 18:
        return f"Likely {side}"
    return f"Safe {side}"


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

class CandidateOut(BaseModel):
    """One candidate in a district. Deliberately an extensible object so future
    'resources' (bio, links, issue tags, news) attach as new fields without
    reshaping the map payload."""
    name: str
    party: Optional[str]                  # DEM/REP/IND/...
    incumbent_challenge: Optional[str]    # I (incumbent) / C (challenger) / O (open)
    fundraising_total: Optional[float]
    fec_id: Optional[str]                 # FEC candidate id → fec.gov profile link


class LatestPoll(BaseModel):
    margin: Optional[float]               # dem − rep
    dem: Optional[float]
    rep: Optional[float]
    pollster: Optional[str]
    date: Optional[datetime]


class DepartingIncumbent(BaseModel):
    """The sitting member who isn't seeking re-election (→ open seat). FEC still
    lists them as an active candidate, so this comes from the Wikipedia
    retirements list, not FEC."""
    name: str
    party: Optional[str]
    reason: Optional[str]


class DistrictOut(BaseModel):
    state: str
    district: str                         # "1".."52" or "AL" (at-large)
    label: str                            # "PA-08" / "AK-AL"
    q: int                                # axial hex coords (pointy-top)
    r: int
    pres_margin_2024: Optional[float]     # presidential D−R — drives the hex color
    house_margin_2024: Optional[float]    # 2024 House result D−R (None if uncontested)
    incumbent_party: Optional[str]        # D / R / O
    cook_rating: Optional[str]            # official rating where we have one (sparse)
    rating: str                           # derived full-coverage label
    open_seat: bool                       # incumbent not seeking re-election
    departing_incumbent: Optional[DepartingIncumbent]
    poll_count: int
    latest_poll: Optional[LatestPoll]
    candidates: List[CandidateOut]


@router.get("/house/districts", response_model=List[DistrictOut])
def get_house_districts(db: Session = Depends(get_db)):
    """Full 435-district hex-cartogram feed: each district's partisan lean, hex
    position, candidate list (names + fundraising), and any polls. Built off the
    vendored house_priors universe so coverage is complete regardless of which
    districts have polls or Cook ratings."""
    # Group candidates and polls by district; official Cook ratings where present.
    cands: dict = collections.defaultdict(list)
    for c in db.query(Candidate).filter(Candidate.office == "H").all():
        if c.district is None:
            continue
        cands[(c.state, c.district)].append(c)

    cook = {(d.state, d.district): d.cook_rating for d in db.query(CompetitiveDistrict).all()}

    # Departing incumbents (open seats) — keyed by (state, district).
    retire = {(r.state, r.district): r for r in db.query(HouseRetirement).all()}

    polls: dict = collections.defaultdict(list)
    for p in db.query(HousePoll).all():
        polls[(p.state, p.district)].append(p)

    results = []
    for row in _PRIORS:
        state, district = row["state"], row["district"]
        q, r = _HEX.get((state, district), (0, 0))
        pres = float(row["pres2024_margin"]) if row["pres2024_margin"] else None
        house_m = float(row["house2024_margin"]) if row["house2024_margin"] else None
        di = _cand_district(district)

        ret = retire.get((state, di))
        departing = DepartingIncumbent(
            name=ret.member_name, party=ret.party, reason=ret.reason,
        ) if ret else None

        clist = sorted(
            cands.get((state, di), []),
            key=lambda c: -(c.fundraising_total or 0.0),
        )
        plist = polls.get((state, di), [])
        latest = max(
            plist,
            key=lambda p: p.end_date or datetime.min.replace(tzinfo=timezone.utc),
            default=None,
        )
        latest_poll = None
        if latest:
            margin = (latest.dem - latest.rep) if latest.dem is not None and latest.rep is not None else None
            latest_poll = LatestPoll(
                margin=round(margin, 1) if margin is not None else None,
                dem=latest.dem, rep=latest.rep,
                pollster=latest.pollster, date=latest.end_date,
            )

        results.append(DistrictOut(
            state=state,
            district=district,
            label=f"{state}-{district}",
            q=q, r=r,
            pres_margin_2024=pres,
            house_margin_2024=house_m,
            incumbent_party=row.get("incumbent_party") or None,
            cook_rating=cook.get((state, di)),
            rating=_derived_rating(pres),
            open_seat=ret is not None,
            departing_incumbent=departing,
            poll_count=len(plist),
            latest_poll=latest_poll,
            candidates=[CandidateOut(
                name=c.name, party=c.party,
                incumbent_challenge=c.incumbent_challenge,
                fundraising_total=c.fundraising_total,
                fec_id=c.fec_id,
            ) for c in clist],
        ))

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
