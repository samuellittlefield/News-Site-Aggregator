"""Three-tier `_current_env()` fallback (forecast-model-swing-fallback-fix).

Covers TC-1, TC-2, TC-3 (which tier fires + `swing_source` is exposed), TC-4
(market-consensus fields are unaffected by the environment tier), TC-5
(`/api/forecasts/model` uses the same tier logic as `/congress`), TC-7 (a
present-but-unparseable VoteHub poll falls through to the aggregator tier, not
treated as a VoteHub success), and TC-10 (`/api/polls/generic-ballot` is
unchanged by this fix). respx (autouse guard in conftest) means any
accidental live Wikipedia call raises instead of hitting the network.
"""
from datetime import datetime, timedelta, timezone

from app.models import GenericBallotAggregate, PredictionMarket, VoteHubPoll
from app.services import forecast_constants as C

BASELINE = C.NATIONAL_PRES_MARGIN_2024_D  # -1.65


def _seed_votehub_poll(db, *, dem, rep, votehub_id="vh-1", days_old=3):
    db.add(VoteHubPoll(
        votehub_id=votehub_id,
        poll_type="generic-ballot",
        end_date=datetime.now(timezone.utc) - timedelta(days=days_old),
        sample_size=1000,
        dem=dem,
        rep=rep,
    ))
    db.commit()


def _seed_aggregate_rows(db, rows):
    for source, dem, rep in rows:
        db.add(GenericBallotAggregate(source=source, dem=dem, rep=rep))
    db.commit()


def _seed_kalshi_control(db):
    """Minimal Kalshi control markets so the market-consensus fields are populated."""
    for chamber_prefix in ("CONTROLH-2026", "CONTROLS-2026"):
        db.add(PredictionMarket(
            platform="kalshi", market_id=f"{chamber_prefix}-D",
            question="Will Democrats win?", yes_price=0.55, active=True,
        ))
        db.add(PredictionMarket(
            platform="kalshi", market_id=f"{chamber_prefix}-R",
            question="Will Republicans win?", yes_price=0.45, active=True,
        ))
    db.commit()


# ── TC-1: VoteHub tier wins when healthy (AC-1, AC-4) ───────────────────────

def test_votehub_tier_wins_when_healthy(client, db):
    _seed_votehub_poll(db, dem=50.0, rep=45.0)  # margin = 5.0

    resp = client.get("/api/forecasts/congress")
    assert resp.status_code == 200
    house = next(c for c in resp.json()["chambers"] if c["chamber"] == "house")

    assert house["model"]["swing_source"] == "votehub"
    expected_swing = round(5.0 - BASELINE, 1)
    assert house["model"]["swing_d"] == expected_swing
    assert house["model"]["swing_d"] != 0


# ── TC-2: Aggregator tier fires when VoteHub is empty (AC-2, AC-4) ──────────

def test_aggregator_tier_fires_when_votehub_empty(client, db):
    _seed_aggregate_rows(db, [
        ("Aggregator A", 48.0, 44.0),
        ("Aggregator B", 50.0, 46.0),
    ])

    resp = client.get("/api/forecasts/congress")
    house = next(c for c in resp.json()["chambers"] if c["chamber"] == "house")

    assert house["model"]["swing_source"] == "aggregator"
    mean_dem = (48.0 + 50.0) / 2
    mean_rep = (44.0 + 46.0) / 2
    expected_margin = round(mean_dem - mean_rep, 1)
    expected_swing = round(expected_margin - BASELINE, 1)
    assert house["model"]["swing_d"] == expected_swing
    assert house["model"]["swing_d"] != 0


# ── TC-3: Static baseline only when both tiers are empty (AC-3, AC-4) ───────

def test_static_baseline_when_both_tiers_empty(client, db):
    resp = client.get("/api/forecasts/congress")
    house = next(c for c in resp.json()["chambers"] if c["chamber"] == "house")

    assert house["model"]["swing_source"] == "fallback"
    assert house["model"]["swing_d"] == 0


# ── TC-4: Market-consensus fields unaffected (AC-6) ─────────────────────────

def test_market_consensus_unaffected_by_swing_tier(client, db):
    _seed_kalshi_control(db)

    resp = client.get("/api/forecasts/congress")
    baseline_chambers = resp.json()["chambers"]

    # Move to the VoteHub tier — market-consensus fields must not change.
    _seed_votehub_poll(db, dem=50.0, rep=45.0)
    resp_votehub = client.get("/api/forecasts/congress")
    votehub_chambers = resp_votehub.json()["chambers"]

    # Move to the aggregator tier (delete the VoteHub poll, add aggregate rows).
    db.query(VoteHubPoll).delete()
    db.commit()
    _seed_aggregate_rows(db, [("Aggregator A", 48.0, 44.0)])
    resp_agg = client.get("/api/forecasts/congress")
    agg_chambers = resp_agg.json()["chambers"]

    for scenario_chambers, tag in ((votehub_chambers, "votehub"), (agg_chambers, "aggregator")):
        for base, scenario in zip(baseline_chambers, scenario_chambers):
            assert base["chamber"] == scenario["chamber"]
            assert base["dem_prob"] == scenario["dem_prob"], tag
            assert base["rep_prob"] == scenario["rep_prob"], tag
            assert base["sources"] == scenario["sources"], tag


# ── TC-5: `/api/forecasts/model` matches `/congress`'s tier logic (AC-7) ────

def _swing_source_for(client, path):
    resp = client.get(path)
    assert resp.status_code == 200
    body = resp.json()
    if path == "/api/forecasts/congress":
        house = next(c for c in body["chambers"] if c["chamber"] == "house")
        return house["model"]["swing_source"]
    return body["house"]["swing_source"]


def test_model_sim_reflects_votehub_tier(client, db):
    _seed_votehub_poll(db, dem=50.0, rep=45.0)
    assert _swing_source_for(client, "/api/forecasts/congress") == "votehub"
    assert _swing_source_for(client, "/api/forecasts/model") == "votehub"


def test_model_sim_reflects_aggregator_tier(client, db):
    _seed_aggregate_rows(db, [("Aggregator A", 48.0, 44.0)])
    assert _swing_source_for(client, "/api/forecasts/congress") == "aggregator"
    assert _swing_source_for(client, "/api/forecasts/model") == "aggregator"


def test_model_sim_reflects_fallback_tier(client, db):
    assert _swing_source_for(client, "/api/forecasts/congress") == "fallback"
    assert _swing_source_for(client, "/api/forecasts/model") == "fallback"


# ── TC-7: Partial VoteHub data is treated as no signal (edge case) ──────────

def test_partial_votehub_data_falls_through_to_aggregator(client, db):
    # In-window VoteHub poll, but dem/rep are unparsed (None).
    _seed_votehub_poll(db, dem=None, rep=None)
    _seed_aggregate_rows(db, [("Aggregator A", 48.0, 44.0)])

    resp = client.get("/api/forecasts/congress")
    house = next(c for c in resp.json()["chambers"] if c["chamber"] == "house")

    assert house["model"]["swing_source"] == "aggregator"


# ── TC-10: `/api/polls/generic-ballot` is unchanged by this fix (regression) ─

def test_generic_ballot_route_unchanged(client, db, respx_router):
    import httpx
    from app.services.house_polls import WIKI_API

    respx_router.get(WIKI_API).mock(
        return_value=httpx.Response(200, json={"parse": {"wikitext": {"*": ""}}})
    )
    _seed_votehub_poll(db, dem=50.0, rep=45.0, votehub_id="vh-genball")

    resp = client.get("/api/polls/generic-ballot")
    assert resp.status_code == 200
    body = resp.json()
    # Route still returns only VoteHub's live average (no aggregator rows were
    # seeded via Wikipedia here) — untouched by the model's new DB-only tier.
    assert body == [{"source": "VoteHub (live average)", "rep": 45.0, "dem": 50.0}]
