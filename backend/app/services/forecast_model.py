"""
Experimental in-house seat-forecast model (House + Senate).

A transparent fundamentals-plus-environment Monte-Carlo. Per-seat prior is the
2024 presidential lean (vendored from The Downballot); the live generic-ballot
average swings every seat by how much the national mood has moved since 2024; an
incumbency term nudges toward the sitting party; then each simulation draws a
*shared* national error (so seats move together → correlated outcomes) plus
per-seat idiosyncratic noise. Counting wins across thousands of sims yields a
control probability and a seat distribution.

Both chambers blend a last-same-office result with the 2024 presidential lean,
each detrended by its year's national baseline, so the prior carries incumbency
strength (e.g. Maine's R Senate lean despite the state voting Harris; House
crossover seats held by the incumbent party). House = 2024 House result + 2024
pres; Senate = last Senate result (2020, or 2022 for the FL/OH specials) + 2024 pres.

DELIBERATELY UNCALIBRATED — the spread/adjustment/blend constants in
`forecast_constants.py` are judgment values, not fit to history (that's the rest of
Phase F). The Senate model still ignores candidate-specific quality and retirements
(an open seat keeps its old incumbency lean), so treat divergences as signal to dig
into, not truth.
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
# House prior file blends 2024 presidential lean with the 2024 House result.
_HOUSE = _load_csv("house_priors.csv")             # state, district, pres2024_margin, house2024_margin, incumbent_party
_STATE_LEAN = {r["state"]: float(r["dem_margin"]) for r in _load_csv("state_pres_2024.csv")}
_SENATE = _load_csv("senate_2026.csv")             # state, incumbent_party, is_special
# Last same-seat Senate result margin (2020 for Class 2, 2022 for FL/OH specials).
_SEN_PRIOR = {r["state"]: float(r["dem_margin"]) for r in _load_csv("senate_prior_results.csv")}


def _inc_dir(party: str) -> float:
    """+1 toward Dems if a Democrat holds the seat, −1 if Republican, else 0."""
    p = (party or "").upper()[:1]
    return 1.0 if p == "D" else (-1.0 if p == "R" else 0.0)


def _current_env(db: Session) -> float:
    """The current national environment (Dem−Rep), i.e. the live generic-ballot
    margin. Seats are modeled as `lean-vs-nation + this`. Falls back to the 2024
    presidential margin (a neutral swing) if the VoteHub window is empty."""
    gb = compute_average(db, "generic-ballot")
    if gb and gb.get("margin") is not None:
        return gb["margin"]
    return C.NATIONAL_PRES_MARGIN_2024_D


def _house_lean(row: dict) -> float:
    """Blended partisan lean (vs nation) for a House seat: the 2024 House result
    (embeds incumbency) and the 2024 presidential lean, each detrended by its
    year's national baseline. Falls back to pure presidential lean for the
    uncontested seats that have no two-party House margin."""
    pres_lean = float(row["pres2024_margin"]) - C.NATIONAL_PRES_MARGIN_2024_D
    if not row["house2024_margin"]:
        return pres_lean
    house_lean = float(row["house2024_margin"]) - C.NATIONAL_HOUSE_2024_D
    w = C.HOUSE_PRIOR_BLEND
    return w * house_lean + (1 - w) * pres_lean


def _senate_lean(state: str, is_special: bool, blend: float) -> float:
    """Blended partisan lean (vs nation) for a Senate seat: the last same-seat
    result and the 2024 presidential lean, each detrended by its year's national
    baseline. The last-result component is what carries incumbency strength.
    `blend` is the weight on the last-result lean (0 = pure presidential)."""
    pres_lean = _STATE_LEAN.get(state, 0.0) - C.NATIONAL_PRES_MARGIN_2024_D
    baseline = C.NATIONAL_2022_D if is_special else C.NATIONAL_PRES_2020_D
    last_lean = _SEN_PRIOR.get(state, _STATE_LEAN.get(state, 0.0)) - baseline
    return blend * last_lean + (1 - blend) * pres_lean


def _simulate(base_margins: np.ndarray, n_sims: int, tau: float, delta: float,
              rng: np.random.Generator) -> np.ndarray:
    """Return per-sim count of Democratic seat wins for the given seats."""
    eps = rng.normal(0.0, tau, size=(n_sims, 1))            # shared national error
    nu = rng.normal(0.0, delta, size=(n_sims, base_margins.size))
    margins = base_margins[None, :] + eps + nu
    return (margins > 0.0).sum(axis=1)


def _summary(dem_seats: np.ndarray, threshold: int, swing: float,
             tau: float, delta: float, inc: float) -> dict:
    p_dem = float((dem_seats >= threshold).mean())
    return {
        "dem_prob": round(p_dem, 4),
        "rep_prob": round(1 - p_dem, 4),
        "median_dem_seats": int(np.median(dem_seats)),
        "p10_dem_seats": int(np.percentile(dem_seats, 10)),
        "p90_dem_seats": int(np.percentile(dem_seats, 90)),
        "n_sims": int(dem_seats.size),
        "swing_d": round(swing, 1),
        "params": {"tau": tau, "delta": delta, "incumbency_adv": inc},
        "note": "experimental",
    }


def run_model(db: Session, n_sims: int = C.N_SIMS, seed: Optional[int] = None, *,
              tau: Optional[float] = None, delta_house: Optional[float] = None,
              delta_senate: Optional[float] = None, incumbency_adv: Optional[float] = None,
              senate_prior_blend: Optional[float] = None) -> dict:
    # Resolve overridable knobs (fall back to the judgment defaults).
    tau = C.TAU if tau is None else tau
    delta_house = C.DELTA_HOUSE if delta_house is None else delta_house
    delta_senate = C.DELTA_SENATE if delta_senate is None else delta_senate
    inc = C.INCUMBENCY_ADV if incumbency_adv is None else incumbency_adv
    blend = C.SENATE_PRIOR_BLEND if senate_prior_blend is None else senate_prior_blend

    rng = np.random.default_rng(seed)
    env = _current_env(db)                                  # nation now (Dem−Rep)
    swing = env - C.NATIONAL_PRES_MARGIN_2024_D             # vs 2024 pres, for display

    # ── House: simulate all 435 seats (blended lean + environment) ──────────
    h_lean = np.array([_house_lean(r) for r in _HOUSE])
    h_inc = np.array([_inc_dir(r["incumbent_party"]) for r in _HOUSE])
    h_base = h_lean + env + inc * h_inc
    h_dem = _simulate(h_base, n_sims, tau, delta_house, rng)
    house = _summary(h_dem, C.HOUSE_MAJORITY, swing, tau, delta_house, inc)

    # ── Senate: carry-over baseline + the seats up in 2026 ──────────────────
    # Seat prior blends last-same-seat result (incumbency) with presidential lean.
    up_dem_now = sum(1 for r in _SENATE if _inc_dir(r["incumbent_party"]) > 0)
    carryover_d = C.CURRENT_SENATE["D"] - up_dem_now
    s_lean = np.array([_senate_lean(r["state"], r["is_special"] == "1", blend) for r in _SENATE])
    s_inc = np.array([_inc_dir(r["incumbent_party"]) for r in _SENATE])
    s_base = s_lean + env + inc * s_inc
    s_dem = carryover_d + _simulate(s_base, n_sims, tau, delta_senate, rng)
    senate = _summary(s_dem, C.SENATE_DEM_CONTROL, swing, tau, delta_senate, inc)

    logger.info(
        "Forecast model: swing D%+.1f | House P(D)=%.2f med=%d | Senate P(D)=%.2f med=%d",
        swing, house["dem_prob"], house["median_dem_seats"],
        senate["dem_prob"], senate["median_dem_seats"],
    )
    return {"house": house, "senate": senate}
