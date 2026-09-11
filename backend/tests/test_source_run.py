"""Per-source ingestion health recording (feature: ingestion-health).

Covers the service layer and scheduler instrumentation:
  - TC-1 (AC-1): a successful run upserts a `success` SourceRun row
  - TC-2 (AC-2): a failing job records `failure` without starving another job
  - TC-3 (AC-3): a DB error *during recording* is swallowed, never propagates
  - TC-4 (AC-4): re-running upserts one row, never duplicates
  - TC-7 (coverage): scheduler-registered job ids == SOURCE_CADENCE keys

Follows `test_kalshi_upsert.py`'s style: `db`/`respx_router` fixtures, async
tests, docstrings citing AC/TC ids. TC-2 rebinds `scheduler.SessionLocal` to the
transactional test session so the real `refresh_*` wrappers (which normally open
their own `SessionLocal`) write into the rolled-back test transaction and stay
isolated.
"""
import logging

import pytest

from app import scheduler
from app.models import SourceRun
from app.shared.services.source_run import record_success, record_failure, SOURCE_CADENCE


def _rows(db, source_id):
    return db.query(SourceRun).filter(SourceRun.source_id == source_id)


# ── TC-1 ────────────────────────────────────────────────────────────────────
def test_record_success_upserts_success_row(db):
    """TC-1 / AC-1: record_success writes exactly one success row with counts +
    timestamps set and no error message."""
    record_success(db, source_id="kalshi_job", label="Kalshi", cadence_minutes=10, item_count=4)

    assert _rows(db, "kalshi_job").count() == 1
    row = _rows(db, "kalshi_job").one()
    assert row.status == "success"
    assert row.item_count == 4
    assert row.error_message is None
    assert row.last_run_at is not None
    assert row.last_success_at is not None
    # A success sets last_run_at == last_success_at on this run.
    assert row.last_success_at == row.last_run_at
    assert row.cadence_minutes == 10


# ── TC-2 ────────────────────────────────────────────────────────────────────
@pytest.fixture
def scheduler_uses_test_db(db, monkeypatch):
    """Make the real scheduler `refresh_*` wrappers use the transactional test
    session instead of opening their own `SessionLocal`, and neuter the
    `db.close()` they call in `finally` so the fixture session survives for
    assertions. Both patches are auto-undone after the test."""
    monkeypatch.setattr(scheduler, "SessionLocal", lambda: db)
    monkeypatch.setattr(db, "close", lambda: None)
    return db


async def test_failure_recorded_without_starving_other_job(db, scheduler_uses_test_db, monkeypatch):
    """TC-2 / AC-2: when votehub's upstream raises, its wrapper records a failure
    row — and an unrelated job (earthquakes) run right after still completes and
    records its own success. Isolation is intact."""
    async def _boom(_db):
        raise RuntimeError("votehub upstream 503")

    async def _ok_quakes(_db):
        return 7

    monkeypatch.setattr(scheduler.votehub_service, "fetch_votehub_polls", _boom)
    monkeypatch.setattr(scheduler.earthquakes_service, "fetch_earthquakes", _ok_quakes)

    # The failing job — its outer try/except catches, then records failure.
    await scheduler.refresh_votehub()
    # The unrelated job, run afterwards, is unaffected.
    await scheduler.refresh_earthquakes()

    vh = _rows(db, "votehub_job").one()
    assert vh.status == "failure"
    assert vh.error_message and "votehub upstream 503" in vh.error_message
    assert vh.last_success_at is None  # never succeeded → no good-data timestamp

    eq = _rows(db, "earthquakes_job").one()
    assert eq.status == "success"
    assert eq.item_count == 7


# ── TC-3 ────────────────────────────────────────────────────────────────────
class _ExplodingDB:
    """Stand-in session whose every write path raises, simulating a DB blip at
    record time."""
    def query(self, *a, **k):
        raise RuntimeError("db connectivity blip")

    def add(self, *a, **k):
        raise RuntimeError("db connectivity blip")

    def commit(self):
        raise RuntimeError("db connectivity blip")

    def rollback(self):
        pass


def test_recording_error_never_propagates(caplog):
    """TC-3 / AC-3: a DB failure inside record_success/record_failure is swallowed
    and logged, never raised out to the ingestion job."""
    with caplog.at_level(logging.ERROR, logger="app.shared.services.source_run"):
        # Must not raise despite the exploding session.
        record_success(_ExplodingDB(), "kalshi_job", "Kalshi", 10, item_count=1)
        record_failure(_ExplodingDB(), "kalshi_job", "Kalshi", 10, RuntimeError("x"))

    messages = [r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR]
    assert any("recording failed for kalshi_job" in m for m in messages)
    # Both paths should have logged.
    assert sum("kalshi_job" in m for m in messages) >= 2


# ── TC-4 ────────────────────────────────────────────────────────────────────
def test_rerun_upserts_does_not_duplicate(db):
    """TC-4 / AC-4: two successive records for the same source_id update one row
    in place; the second call's item_count wins."""
    record_success(db, "earthquakes_job", "Earthquakes (USGS)", 5, item_count=3)
    record_success(db, "earthquakes_job", "Earthquakes (USGS)", 5, item_count=9)

    assert _rows(db, "earthquakes_job").count() == 1
    assert _rows(db, "earthquakes_job").one().item_count == 9


def test_failure_preserves_last_success_at(db):
    """AC-4 companion: a failure after a success keeps the prior last_success_at
    (so the UI can show how stale the last good data is) while flipping status."""
    record_success(db, "kalshi_job", "Kalshi", 10, item_count=4)
    good_ts = _rows(db, "kalshi_job").one().last_success_at

    record_failure(db, "kalshi_job", "Kalshi", 10, RuntimeError("boom"))
    row = _rows(db, "kalshi_job").one()
    assert row.status == "failure"
    assert row.error_message == "boom"
    assert row.last_success_at == good_ts   # preserved
    assert row.last_run_at >= good_ts       # bumped to the failed run


# ── TC-7 ────────────────────────────────────────────────────────────────────
def test_instrumentation_coverage_matches_registered_jobs(monkeypatch):
    """TC-7: the set of ids passed to scheduler.add_job(...) must exactly equal
    the keys of SOURCE_CADENCE — catches a new scheduler job that forgot health
    instrumentation, or a stale SOURCE_CADENCE entry for a removed job. Also
    asserts refresh_breakout is deliberately in neither (not registered today)."""
    registered = []
    monkeypatch.setattr(
        scheduler.scheduler, "add_job",
        lambda func, trigger, id, **kw: registered.append(id),
    )
    monkeypatch.setattr(scheduler.scheduler, "start", lambda: None)

    scheduler.start_scheduler()

    assert set(registered) == set(SOURCE_CADENCE.keys())
    # refresh_breakout is on-demand only (via /api/trends/breakout), not scheduled.
    assert "breakout_job" not in registered
    assert "breakout_job" not in SOURCE_CADENCE
