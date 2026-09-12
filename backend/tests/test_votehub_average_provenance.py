"""Provenance fields on `compute_average` (poll-staleness-labels).

`compute_average` gains `newest_fieldwork_end` / `oldest_fieldwork_end` —
additive only, computed from the polls actually inside the window (not the
whole table). See docs/features/poll-staleness-labels/.

TC-2 and TC-3 (the existing-fields-unchanged and forecast-unchanged hard gate)
live in test_staleness_regression.py against a captured pre-change fixture;
this file covers TC-1, TC-6, TC-7, TC-12.
"""
from datetime import datetime, timedelta, timezone

from app.elections.services.votehub import compute_average
from app.models import VoteHubPoll


def _seed(db, poll_type, rows):
    for vid, days_old, extra in rows:
        db.add(VoteHubPoll(
            votehub_id=vid, poll_type=poll_type, sample_size=1000,
            end_date=datetime.now(timezone.utc) - timedelta(days=days_old),
            sponsors=[], answers=[], **extra,
        ))
    db.commit()


# ── TC-1: provenance reflects the window, not the whole table (AC-1) ───────

def test_provenance_reflects_only_polls_actually_averaged(db):
    now = datetime.now(timezone.utc)
    db.add(VoteHubPoll(
        votehub_id="p-in-1", poll_type="approval", sample_size=1000,
        end_date=now - timedelta(days=2), approve=40.0, disapprove=55.0,
        sponsors=[], answers=[],
    ))
    db.add(VoteHubPoll(
        votehub_id="p-in-2", poll_type="approval", sample_size=1000,
        end_date=now - timedelta(days=10), approve=38.0, disapprove=57.0,
        sponsors=[], answers=[],
    ))
    db.add(VoteHubPoll(
        # Outside the 21-day window — must not influence n_polls or the bounds.
        votehub_id="p-out", poll_type="approval", sample_size=1000,
        end_date=now - timedelta(days=30), approve=20.0, disapprove=70.0,
        sponsors=[], answers=[],
    ))
    db.commit()

    avg = compute_average(db, "approval")

    assert avg["n_polls"] == 2
    assert avg["newest_fieldwork_end"] == now - timedelta(days=2)
    assert avg["oldest_fieldwork_end"] == now - timedelta(days=10)


# ── TC-6: None on an empty window, unchanged (AC-7 precondition) ───────────

def test_none_when_all_polls_older_than_window(db):
    _seed(db, "approval", [
        ("old-1", 25, {"approve": 40.0, "disapprove": 55.0}),
        ("old-2", 40, {"approve": 38.0, "disapprove": 57.0}),
    ])

    assert compute_average(db, "approval") is None


# ── TC-7: genuinely empty table, no fabricated date (AC-8 precondition) ────

def test_none_on_genuinely_empty_table(db):
    assert compute_average(db, "approval") is None
    assert compute_average(db, "generic-ballot") is None


# ── TC-12: both poll types behave identically (AC-9) ───────────────────────

def test_generic_ballot_gets_the_same_provenance_fields(db):
    now = datetime.now(timezone.utc)
    db.add(VoteHubPoll(
        votehub_id="gb-1", poll_type="generic-ballot", sample_size=1000,
        end_date=now - timedelta(days=1), dem=48.0, rep=44.0,
        sponsors=[], answers=[],
    ))
    db.add(VoteHubPoll(
        votehub_id="gb-2", poll_type="generic-ballot", sample_size=1000,
        end_date=now - timedelta(days=15), dem=46.0, rep=45.0,
        sponsors=[], answers=[],
    ))
    db.commit()

    avg = compute_average(db, "generic-ballot")

    assert avg["n_polls"] == 2
    assert avg["newest_fieldwork_end"] == now - timedelta(days=1)
    assert avg["oldest_fieldwork_end"] == now - timedelta(days=15)

    # And the same drain behaviour as approval.
    assert compute_average(db, "generic-ballot", window_days=0) is None
