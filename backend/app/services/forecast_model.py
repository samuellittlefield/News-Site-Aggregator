"""
Experimental in-house seat-forecast model (House + Senate).

A transparent fundamentals-plus-environment Monte-Carlo. Per-seat prior is the
2024 presidential lean (vendored from The Downballot); the live generic-ballot
average swings every seat by how much the national mood has moved since 2024; an
incumbency term nudges toward the sitting party; then each simulation draws a
*shared* national error (so seats move together → correlated outcomes) plus
per-seat idiosyncratic noise. Counting wins across thousands of sims yields a
control probability and a seat distribution.

DELIBERATELY UNCALIBRATED — the spread/adjustment constants in
`forecast_constants.py` are judgment values, not fit to history (that's Phase F).
The Senate model is intentionally crude: it applies a House-vote environment to
state presidential leans and ignores candidate quality, so it will over-credit
the out-party in incumbent-anchored states.
"""
import csv
import logging
import os
from typing import Optional

import numpy as np
from sqlalchemy.orm import Session

from app.services import forecast_constants as C
from app.services.votehub import compute_average

logger = logging.getLogger(__name__)

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def _load_csv(name: str) -> list:
    with open(os.path.join(_DATA_DIR, name), newline="") as f:
        return list(csv.DictReader(f))


# Static baselines loaded once at import (tiny, vendored).
_HOUSE = _load_csv("house_2024_pres.csv")          # state, district, dem_margin, incumbent_party
_STATE_LEAN = {r["state"]: float(r["dem_margin"]) for r in _load_csv("state_pres_2024.csv")}
_SENATE = _load_csv("senate_2026.csv")             # state, incumbent_party, is_special


def _inc_dir(party: str) -> float:
    """+1 toward Dems if a Democrat holds the seat, −1 if Republican, else 0."""
    p = (party or "").upper()[:1]
    return 1.0 if p == "D" else (-1.0 if p == "R" else 0.0)


def _national_swing(db: Session) -> float:
    """How much more Democratic the mood is now vs. the 2024 presidential baseline."""
    gb = compute_average(db, "generic-ballot")
    if gb and gb.get("margin") is not None:
        return gb["margin"] - C.NATIONAL_PRES_MARGIN_2024_D
    return 0.0  # neutral fallback if VoteHub window is empty


def _simulate(base_margins: np.ndarray, n_sims: int, tau: float, delta: float,
              rng: np.random.Generator) -> np.ndarray:
    """Return per-sim count of Democratic seat wins for the given seats."""
    eps = rng.normal(0.0, tau, size=(n_sims, 1))            # shared national error
    nu = rng.normal(0.0, delta, size=(n_sims, base_margins.size))
    margins = base_margins[None, :] + eps + nu
    return (margins > 0.0).sum(axis=1)


def _summary(dem_seats: np.ndarray, threshold: int, total_label_seats: int,
             swing: float, delta: float) -> dict:
    p_dem = float((dem_seats >= threshold).mean())
    return {
        "dem_prob": round(p_dem, 4),
        "rep_prob": round(1 - p_dem, 4),
        "median_dem_seats": int(np.median(dem_seats)),
        "p10_dem_seats": int(np.percentile(dem_seats, 10)),
        "p90_dem_seats": int(np.percentile(dem_seats, 90)),
        "n_sims": int(dem_seats.size),
        "swing_d": round(swing, 1),
        "params": {"tau": C.TAU, "delta": delta, "incumbency_adv": C.INCUMBENCY_ADV},
        "note": "experimental — uncalibrated",
    }


def run_model(db: Session, n_sims: int = C.N_SIMS, seed: Optional[int] = None) -> dict:
    rng = np.random.default_rng(seed)
    swing = _national_swing(db)

    # ── House: simulate all 435 seats ───────────────────────────────────────
    h_prior = np.array([float(r["dem_margin"]) for r in _HOUSE])
    h_inc = np.array([_inc_dir(r["incumbent_party"]) for r in _HOUSE])
    h_base = h_prior + C.INCUMBENCY_ADV * h_inc + swing
    h_dem = _simulate(h_base, n_sims, C.TAU, C.DELTA_HOUSE, rng)
    house = _summary(h_dem, C.HOUSE_MAJORITY, 435, swing, C.DELTA_HOUSE)

    # ── Senate: carry-over baseline + the seats up in 2026 ──────────────────
    up_dem_now = sum(1 for r in _SENATE if _inc_dir(r["incumbent_party"]) > 0)
    carryover_d = C.CURRENT_SENATE["D"] - up_dem_now
    s_prior = np.array([_STATE_LEAN.get(r["state"], 0.0) for r in _SENATE])
    s_inc = np.array([_inc_dir(r["incumbent_party"]) for r in _SENATE])
    s_base = s_prior + C.INCUMBENCY_ADV * s_inc + swing
    s_dem = carryover_d + _simulate(s_base, n_sims, C.TAU, C.DELTA_SENATE, rng)
    senate = _summary(s_dem, C.SENATE_DEM_CONTROL, 100, swing, C.DELTA_SENATE)

    logger.info(
        "Forecast model: swing D%+.1f | House P(D)=%.2f med=%d | Senate P(D)=%.2f med=%d",
        swing, house["dem_prob"], house["median_dem_seats"],
        senate["dem_prob"], senate["median_dem_seats"],
    )
    return {"house": house, "senate": senate}
