"""Forecast-model determinism (AC-3 / TC-4).

`run_model` reads only `_current_env(db)` (generic-ballot average, which falls
back to a constant on an empty VoteHub window) and `_fundraising_edges(db)` (empty
without Candidate rows) from the DB; the per-seat priors are vendored CSVs. So an
empty test DB is a valid, fixed input set — determinism is governed purely by the
RNG seed. A smaller `n_sims` keeps the test fast without affecting determinism.
"""
from app.elections.services.forecast_model import run_model

N = 2000


def test_same_seed_is_identical(db):
    first = run_model(db, n_sims=N, seed=42)
    second = run_model(db, n_sims=N, seed=42)
    assert first == second


def test_different_seed_differs(db):
    baseline = run_model(db, n_sims=N, seed=42)
    other = run_model(db, n_sims=N, seed=43)
    assert baseline != other
    # The differing fields are simulation-derived, not the fixed params/notes.
    assert baseline["house"]["dem_prob"] != other["house"]["dem_prob"]
