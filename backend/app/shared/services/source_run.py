"""Per-source ingestion health recording (feature: ingestion-health).

Every `refresh_*` function registered in `scheduler.start_scheduler()` records the
outcome of each run into a single upserted `SourceRun` row (keyed by the same
`source_id` used in `scheduler.add_job(..., id=...)`). This is *current-state
only* — an upsert per source, not an append-only log (AC-4).

`SOURCE_CADENCE` is the single source of truth for the registered job ids, their
human-readable labels, and their expected cadence (mirroring each job's
`IntervalTrigger`). Both `scheduler.py` (when recording) and the
`/api/status/sources` route read from this map, so the two can't drift — and
`test_source_run.py::test_instrumentation_coverage` (TC-7) diffs the scheduler's
`add_job` ids against these keys to catch drift automatically.

Both recorders wrap their own DB write in a try/except that only logs: a DB blip
at record time must never propagate up and break the ingestion job it was trying
to record (AC-3). `record_breakout` is intentionally absent — `refresh_breakout`
is not registered via `add_job` today (on-demand only, via `/api/trends/breakout`).
"""
import logging
from datetime import datetime, timezone
from typing import Dict, NamedTuple, Optional

from sqlalchemy.orm import Session

from app.models import SourceRun

logger = logging.getLogger(__name__)


class SourceMeta(NamedTuple):
    label: str
    cadence_minutes: int


# source_id (== scheduler.add_job id) → (label, expected cadence in minutes).
# Keep in lockstep with the IntervalTrigger values in scheduler.start_scheduler();
# TC-7 fails if a registered job id is missing here or a key here is unregistered.
SOURCE_CADENCE: Dict[str, SourceMeta] = {
    "refresh_job":       SourceMeta("Google Trends", 60),
    "extended_job":      SourceMeta("Enrichment (Wikipedia + NYT + Reddit)", 60),
    "climate_job":       SourceMeta("Climate Events (EONET)", 360),
    "news_job":          SourceMeta("News Categories", 30),
    "weather_job":       SourceMeta("Regional Weather", 180),
    "status_job":        SourceMeta("Service Status", 15),
    "nws_alerts_job":    SourceMeta("NWS Alerts", 15),
    "house_polls_job":   SourceMeta("House Polls", 360),
    "candidates_job":    SourceMeta("FEC Candidates", 1440),
    "retirements_job":   SourceMeta("House Retirements", 1440),
    "issue_tagger_job":  SourceMeta("AI Issue Tagger", 10080),
    "economist_job":     SourceMeta("Economist/YouGov", 720),
    "votehub_job":       SourceMeta("VoteHub Polls", 60),
    "earthquakes_job":   SourceMeta("Earthquakes (USGS)", 5),
    "faa_job":           SourceMeta("FAA Airspace Status", 10),
    "markets_job":       SourceMeta("Prediction Markets (Polymarket)", 10),
    "kalshi_job":        SourceMeta("Kalshi Markets", 10),
}


def _get_or_create(db: Session, source_id: str) -> SourceRun:
    row = db.query(SourceRun).filter(SourceRun.source_id == source_id).first()
    if row is None:
        row = SourceRun(source_id=source_id)
        db.add(row)
    return row


def record_success(
    db: Session,
    source_id: str,
    label: str,
    cadence_minutes: int,
    item_count: Optional[int] = None,
) -> None:
    """Upsert the `SourceRun` row for `source_id` as a successful run.

    Sets both `last_run_at` and `last_success_at` to now. Never raises — a
    recording failure is swallowed and logged so it can't break the job (AC-3).
    """
    try:
        now = datetime.now(timezone.utc)
        row = _get_or_create(db, source_id)
        row.label = label
        row.cadence_minutes = cadence_minutes
        row.status = "success"
        row.last_run_at = now
        row.last_success_at = now
        row.item_count = item_count
        row.error_message = None
        db.commit()
    except Exception:
        logger.exception("SourceRun success recording failed for %s", source_id)
        try:
            db.rollback()
        except Exception:
            pass


def record_failure(
    db: Session,
    source_id: str,
    label: str,
    cadence_minutes: int,
    error: BaseException,
) -> None:
    """Upsert the `SourceRun` row for `source_id` as a failed run.

    Sets `last_run_at` to now and stores the error message, but preserves
    `last_success_at` (the last time the job actually produced data) so the UI
    can still show how stale the good data is. Never raises (AC-3).
    """
    try:
        now = datetime.now(timezone.utc)
        # Clear any poisoned transaction state left by the failing job before we
        # try to write (e.g. a mid-transaction DB error). Already-committed work
        # is unaffected; only uncommitted changes are discarded.
        try:
            db.rollback()
        except Exception:
            pass
        row = _get_or_create(db, source_id)
        row.label = label
        row.cadence_minutes = cadence_minutes
        row.status = "failure"
        row.last_run_at = now
        row.error_message = str(error) or error.__class__.__name__
        db.commit()
    except Exception:
        logger.exception("SourceRun failure recording failed for %s", source_id)
        try:
            db.rollback()
        except Exception:
            pass
