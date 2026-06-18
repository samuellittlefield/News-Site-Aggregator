"""
Election forecast endpoints.

`/api/forecasts/congress` normalizes the control-of-Congress prediction markets
already stored in `PredictionMarket` (Kalshi is the guaranteed source; Polymarket
is matched opportunistically) into per-chamber Democratic/Republican probabilities,
and appends a static list of model link-outs (Silver Bulletin, Race to the WH,
Split Ticket) that are cited but not ingested.
"""
import logging
import re
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.services import forecast_constants as MC
from app.services.forecast_model import run_model

logger = logging.getLogger(__name__)

from app.database import get_db
from app.models import PredictionMarket

router = APIRouter(prefix="/api/forecasts", tags=["forecasts"])

# Kalshi control series ticker prefixes for the 2026 midterms.
KALSHI_PREFIX = {"house": "CONTROLH-2026", "senate": "CONTROLS-2026"}
# Opportunistic Polymarket matching: chamber word + a control/win phrase.
POLY_CHAMBER = {"house": "house", "senate": "senate"}
POLY_CONTROL = re.compile(r"control|balance of power|win|majority|flip", re.I)

REFERENCES = [
    {
        "name": "Silver Bulletin",
        "publisher": "Nate Silver",
        "url": "https://www.natesilver.net/p/generic-ballot-average-2026-nate-silver-bulletin-congress-polls",
        "note": "Daily generic-ballot average; full 2026 model forthcoming (paywalled).",
    },
    {
        "name": "Race to the WH",
        "publisher": "Race to the WH",
        "url": "https://www.racetothewh.com/house",
        "note": "House/Senate/Gov model with district-level ratings.",
    },
    {
        "name": "Split Ticket",
        "publisher": "Split Ticket",
        "url": "https://split-ticket.org/category/modeling/",
        "note": "Monte-Carlo chamber-control model built on aggregated polling.",
    },
]


class ForecastSource(BaseModel):
    platform: str
    dem_prob: Optional[float] = None
    rep_prob: Optional[float] = None
    url: Optional[str] = None
    dem_market_id: Optional[int] = None  # PredictionMarket.id, for /api/markets/{id}/history
    rep_market_id: Optional[int] = None


class ChamberModel(BaseModel):
    """Our experimental in-house model — kept separate from the market consensus."""
    dem_prob: float
    rep_prob: float
    median_dem_seats: int
    p10_dem_seats: int
    p90_dem_seats: int
    n_sims: int
    note: str


class ChamberForecast(BaseModel):
    chamber: str
    title: str
    dem_prob: Optional[float] = None  # market consensus (mean across platforms) — model NOT blended in
    rep_prob: Optional[float] = None
    sources: List[ForecastSource]
    model: Optional[ChamberModel] = None


class CongressForecastOut(BaseModel):
    chambers: List[ChamberForecast]
    references: list


def _kalshi_source(db: Session, chamber: str) -> Optional[ForecastSource]:
    prefix = KALSHI_PREFIX[chamber]
    rows = (
        db.query(PredictionMarket)
        .filter(
            PredictionMarket.platform == "kalshi",
            PredictionMarket.active == True,  # noqa: E712
            PredictionMarket.market_id.like(f"{prefix}%"),
        )
        .all()
    )
    if not rows:
        return None
    src = ForecastSource(platform="kalshi")
    for r in rows:
        if r.market_id.endswith("-D"):
            src.dem_prob = r.yes_price
            src.dem_market_id = r.id
            src.url = r.url
        elif r.market_id.endswith("-R"):
            src.rep_prob = r.yes_price
            src.rep_market_id = r.id
            src.url = src.url or r.url
    if src.dem_prob is None and src.rep_prob is None:
        return None
    return src


def _outcome_price(outcomes: list, *needles: str) -> Optional[float]:
    for o in outcomes or []:
        name = str(o.get("name", "")).lower()
        if any(n in name for n in needles):
            price = o.get("price")
            if isinstance(price, (int, float)):
                return round(float(price), 4)
    return None


def _polymarket_source(db: Session, chamber: str) -> Optional[ForecastSource]:
    word = POLY_CHAMBER[chamber]
    rows = (
        db.query(PredictionMarket)
        .filter(
            PredictionMarket.platform == "polymarket",
            PredictionMarket.active == True,  # noqa: E712
        )
        .order_by(PredictionMarket.volume_24h.desc().nullslast())
        .all()
    )
    for r in rows:
        text = f"{r.event_title or ''} {r.question or ''}".lower()
        if word not in text or not POLY_CONTROL.search(text):
            continue
        # Single market with party outcomes, e.g. ["Democrats","Republicans"]
        dem = _outcome_price(r.outcomes, "dem")
        rep = _outcome_price(r.outcomes, "rep")
        if dem is None and rep is None:
            continue
        return ForecastSource(
            platform="polymarket",
            dem_prob=dem,
            rep_prob=rep,
            url=r.url,
            dem_market_id=r.id,
            rep_market_id=r.id,
        )
    return None


def _mean(values: List[Optional[float]]) -> Optional[float]:
    nums = [v for v in values if v is not None]
    return round(sum(nums) / len(nums), 4) if nums else None


def _chamber_model(model_out: Optional[dict], chamber: str) -> Optional[ChamberModel]:
    block = (model_out or {}).get(chamber)
    if not block:
        return None
    return ChamberModel(
        dem_prob=block["dem_prob"],
        rep_prob=block["rep_prob"],
        median_dem_seats=block["median_dem_seats"],
        p10_dem_seats=block["p10_dem_seats"],
        p90_dem_seats=block["p90_dem_seats"],
        n_sims=block["n_sims"],
        note=block["note"],
    )


@router.get("/congress", response_model=CongressForecastOut)
def congress_forecast(db: Session = Depends(get_db)):
    # In-house experimental model (fixed seed so the displayed number is stable
    # across refreshes). Failure here must not break the market forecast.
    try:
        model_out = run_model(db, seed=2026)
    except Exception:  # noqa: BLE001
        logger.exception("Forecast model failed; serving market-only forecast")
        model_out = None

    chambers: List[ChamberForecast] = []
    for chamber, title in (("house", "Control of the House"), ("senate", "Control of the Senate")):
        sources = [
            s for s in (_kalshi_source(db, chamber), _polymarket_source(db, chamber)) if s is not None
        ]
        chambers.append(
            ChamberForecast(
                chamber=chamber,
                title=title,
                # Headline consensus is MARKET-ONLY; the model is reported separately.
                dem_prob=_mean([s.dem_prob for s in sources]),
                rep_prob=_mean([s.rep_prob for s in sources]),
                sources=sources,
                model=_chamber_model(model_out, chamber),
            )
        )
    return CongressForecastOut(chambers=chambers, references=REFERENCES)


class ModelSimOut(BaseModel):
    house: ChamberModel
    senate: ChamberModel
    defaults: dict


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


@router.get("/model", response_model=ModelSimOut)
def model_sim(
    tau: float = Query(MC.TAU),
    delta_house: float = Query(MC.DELTA_HOUSE),
    delta_senate: float = Query(MC.DELTA_SENATE),
    incumbency_adv: float = Query(MC.INCUMBENCY_ADV),
    senate_prior_blend: float = Query(MC.SENATE_PRIOR_BLEND),
    db: Session = Depends(get_db),
):
    """Re-run the experimental model with tunable knobs (for the live controls).
    Params are clamped to sane ranges. Fixed seed so slider changes show the
    *parameter* effect, not Monte-Carlo noise."""
    out = run_model(
        db, seed=2026,
        tau=_clamp(tau, 0.0, 10.0),
        delta_house=_clamp(delta_house, 0.5, 15.0),
        delta_senate=_clamp(delta_senate, 0.5, 15.0),
        incumbency_adv=_clamp(incumbency_adv, 0.0, 15.0),
        senate_prior_blend=_clamp(senate_prior_blend, 0.0, 1.0),
    )
    return ModelSimOut(
        house=_chamber_model(out, "house"),
        senate=_chamber_model(out, "senate"),
        defaults={
            "tau": MC.TAU,
            "delta_house": MC.DELTA_HOUSE,
            "delta_senate": MC.DELTA_SENATE,
            "incumbency_adv": MC.INCUMBENCY_ADV,
            "senate_prior_blend": MC.SENATE_PRIOR_BLEND,
        },
    )
