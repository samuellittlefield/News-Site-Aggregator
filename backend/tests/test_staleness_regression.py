"""The hard gate: existing values are byte-identical after poll-staleness-labels
(AC-2 / TC-2, AC-3 / TC-3).

`fixtures/staleness_baseline.json` was captured 2026-09-11 from the
*unmodified* pre-ticket `compute_average` (see the fixture's own `_note`),
against the exact fixed relative-day seed below — seeded via `days_old`
offsets from `datetime.now()` at test time, never absolute dates, so the
comparison stays valid regardless of when the suite runs (the whole point of
this ticket is not to let wall-clock drift silently change a number).

TC-2: `/api/votehub/approval` and `/api/votehub/generic-ballot`'s `average`
object, with the two new provenance keys excluded, matches the baseline
exactly. TC-3: `/api/forecasts/congress`'s `swing_d`, `swing_source`,
`dem_prob`, `rep_prob`, `median_dem_seats` — the values `_current_env()`'s
tier-1 path feeds into the model — are unchanged for both chambers. If either
of these ever fails, per the ticket: stop and report, do not edit the
fixture to match.
"""
import json
import pathlib
from datetime import datetime, timedelta, timezone

from app.models import VoteHubPoll

FIX = pathlib.Path(__file__).parent / "fixtures"
BASELINE = json.loads((FIX / "staleness_baseline.json").read_text())

# Exactly the seed used to capture the baseline (see that fixture's _note).
SEED_APPROVAL = [
    ("bl-ap-1", 2, "YouGov", 1500, 37.0, 58.0),
    ("bl-ap-2", 3, "Ipsos", 1600, 36.0, 59.0),
    ("bl-ap-3", 6, "YouGov", 1400, 35.0, 60.0),
    ("bl-ap-4", 8, "Ipsos", 1300, 34.0, 61.0),
    ("bl-ap-5", 19, "TIPP Insights", 1000, 38.0, 52.0),
]
SEED_GENERIC_BALLOT = [
    ("bl-gb-1", 1, "YouGov", 1500, 48.0, 44.0),
    ("bl-gb-2", 3, "Ipsos", 1600, 47.0, 45.0),
    ("bl-gb-3", 4, "Morning Consult", 1400, 46.0, 44.0),
]


def _seed_baseline_data(db):
    now = datetime.now(timezone.utc)
    for vid, days_old, pollster, n, approve, disapprove in SEED_APPROVAL:
        db.add(VoteHubPoll(
            votehub_id=vid, poll_type="approval", pollster=pollster,
            sponsors=[], answers=[], sample_size=n,
            end_date=now - timedelta(days=days_old),
            approve=approve, disapprove=disapprove,
        ))
    for vid, days_old, pollster, n, dem, rep in SEED_GENERIC_BALLOT:
        db.add(VoteHubPoll(
            votehub_id=vid, poll_type="generic-ballot", pollster=pollster,
            sponsors=[], answers=[], sample_size=n,
            end_date=now - timedelta(days=days_old),
            dem=dem, rep=rep,
        ))
    db.commit()


# ── TC-2: existing average fields are byte-identical (AC-2) ────────────────

def test_approval_average_unchanged_apart_from_new_provenance_keys(client, db):
    _seed_baseline_data(db)

    resp = client.get("/api/votehub/approval")
    assert resp.status_code == 200
    avg = resp.json()["average"]

    new_keys = {"newest_fieldwork_end", "oldest_fieldwork_end"}
    assert new_keys <= avg.keys()
    old_fields = {k: v for k, v in avg.items() if k not in new_keys}
    assert old_fields == BASELINE["approval_average"]


def test_generic_ballot_average_unchanged_apart_from_new_provenance_keys(client, db):
    _seed_baseline_data(db)

    resp = client.get("/api/votehub/generic-ballot")
    assert resp.status_code == 200
    avg = resp.json()["average"]

    new_keys = {"newest_fieldwork_end", "oldest_fieldwork_end"}
    assert new_keys <= avg.keys()
    old_fields = {k: v for k, v in avg.items() if k not in new_keys}
    assert old_fields == BASELINE["generic_ballot_average"]


# ── TC-3: the forecast model's hard gate (AC-3) ─────────────────────────────

def test_forecast_congress_unchanged_for_both_chambers(client, db):
    """The one that matters most: this ticket must not move a chamber forecast.
    forecast_model.py reads only gb["margin"] from compute_average's return —
    additive keys are invisible to it — but this proves that directly against
    the fixed seed rather than assuming it from reading the code."""
    _seed_baseline_data(db)

    resp = client.get("/api/forecasts/congress")
    assert resp.status_code == 200
    body = resp.json()

    fields = ("swing_d", "swing_source", "dem_prob", "rep_prob", "median_dem_seats")
    for chamber in ("house", "senate"):
        model = next(c for c in body["chambers"] if c["chamber"] == chamber)["model"]
        actual = {f: model[f] for f in fields}
        assert actual == BASELINE["forecast_model"][chamber], (
            f"{chamber} forecast changed — poll-staleness-labels must not move "
            f"chamber forecasts (AC-3 hard gate)"
        )
