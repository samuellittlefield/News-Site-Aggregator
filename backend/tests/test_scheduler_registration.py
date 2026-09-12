"""Scheduler registration is unchanged by the elections-seam move
(elections-seam T1, AC-9 / TC-13).

Only import paths changed in `scheduler.py`; this pins the actual runtime
registration so that claim is checked, not assumed. Job-id-set coverage
against `SOURCE_CADENCE` already exists as
`test_instrumentation_coverage_matches_registered_jobs` in
`test_source_run.py` — this adds the cadence dimension that test doesn't
cover, so a copy/paste mistake during the import edit (e.g. an
`IntervalTrigger` value dropped or duplicated across two jobs) would be
caught here.
"""
from app import scheduler

EXPECTED_INTERVAL_SECONDS = {
    "refresh_job": 3600,
    "extended_job": 3600,
    "climate_job": 6 * 3600,
    "news_job": 30 * 60,
    "weather_job": 3 * 3600,
    "status_job": 15 * 60,
    "nws_alerts_job": 15 * 60,
    "house_polls_job": 6 * 3600,
    "candidates_job": 24 * 3600,
    "retirements_job": 24 * 3600,
    "issue_tagger_job": 7 * 24 * 3600,
    "economist_job": 12 * 3600,
    "votehub_job": 3600,
    "earthquakes_job": 5 * 60,
    "faa_job": 10 * 60,
    "markets_job": 10 * 60,
    "kalshi_job": 10 * 60,
}


def test_registered_jobs_match_expected_ids_and_cadences(monkeypatch):
    registered = {}

    def fake_add_job(func, trigger, id, **kw):
        registered[id] = trigger.interval.total_seconds()

    monkeypatch.setattr(scheduler.scheduler, "add_job", fake_add_job)
    monkeypatch.setattr(scheduler.scheduler, "start", lambda: None)

    scheduler.start_scheduler()

    assert len(registered) == 17
    assert registered == EXPECTED_INTERVAL_SECONDS
