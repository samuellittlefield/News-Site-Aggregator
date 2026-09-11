"""`GET /api/status/sources` integration (feature: ingestion-health).

  - TC-5 (AC-5): with rows seeded, one entry per registered source, each carrying
    status/timestamps/error/count/cadence
  - TC-6 (AC-6): against an empty table, every source appears as `never_run` with
    null timestamps — no 500, none omitted

Mirrors the empty-DB smoke pattern in `test_routers_smoke.py`; the `client`
fixture routes `get_db` to the transactional test session, so rows seeded via
`db` are visible to the route.
"""
from datetime import datetime, timezone

from app.models import SourceRun
from app.shared.services.source_run import SOURCE_CADENCE

EXPECTED_FIELDS = {
    "source_id", "label", "status", "last_run_at",
    "last_success_at", "error_message", "item_count", "cadence_minutes",
}


# ── TC-6 (empty DB) ─────────────────────────────────────────────────────────
def test_sources_empty_db_all_never_run(client):
    """TC-6 / AC-6: empty source_runs table → 200, every registered source present
    as never_run with null timestamps, none omitted."""
    resp = client.get("/api/status/sources")
    assert resp.status_code == 200

    body = resp.json()
    assert len(body) == len(SOURCE_CADENCE)
    assert {e["source_id"] for e in body} == set(SOURCE_CADENCE.keys())
    for entry in body:
        assert entry["status"] == "never_run"
        assert entry["last_run_at"] is None
        assert entry["last_success_at"] is None
        assert entry["error_message"] is None
        assert entry["item_count"] is None
        # cadence always comes from SOURCE_CADENCE even for never-run sources.
        assert entry["cadence_minutes"] == SOURCE_CADENCE[entry["source_id"]].cadence_minutes


# ── TC-5 (seeded rows) ──────────────────────────────────────────────────────
def test_sources_returns_one_entry_per_source_with_cadence(client, db):
    """TC-5 / AC-5: seed a mix of success/failure; the route returns exactly one
    entry per SOURCE_CADENCE id (seeded rows + synthesised never_run) with the
    full field set and per-source cadence."""
    now = datetime.now(timezone.utc)
    db.add(SourceRun(
        source_id="kalshi_job", label="Kalshi", status="success",
        last_run_at=now, last_success_at=now, item_count=4,
        cadence_minutes=SOURCE_CADENCE["kalshi_job"].cadence_minutes,
    ))
    db.add(SourceRun(
        source_id="votehub_job", label="VoteHub Polls", status="failure",
        last_run_at=now, last_success_at=None, error_message="upstream 503",
        cadence_minutes=SOURCE_CADENCE["votehub_job"].cadence_minutes,
    ))
    db.flush()

    resp = client.get("/api/status/sources")
    assert resp.status_code == 200
    body = resp.json()

    # One entry per registered source, no dupes, none omitted.
    assert len(body) == len(SOURCE_CADENCE)
    assert {e["source_id"] for e in body} == set(SOURCE_CADENCE.keys())
    for entry in body:
        assert EXPECTED_FIELDS <= set(entry.keys())

    by_id = {e["source_id"]: e for e in body}
    assert by_id["kalshi_job"]["status"] == "success"
    assert by_id["kalshi_job"]["item_count"] == 4
    assert by_id["kalshi_job"]["cadence_minutes"] == 10

    assert by_id["votehub_job"]["status"] == "failure"
    assert by_id["votehub_job"]["error_message"] == "upstream 503"
    assert by_id["votehub_job"]["last_success_at"] is None

    # A source with no seeded row is still present as never_run.
    assert by_id["faa_job"]["status"] == "never_run"
    assert by_id["faa_job"]["last_run_at"] is None
