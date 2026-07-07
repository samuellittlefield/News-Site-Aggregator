"""Router smoke tests (AC-5 / TC-6) plus harness guards (AC-2 / TC-2, TC-3)."""
import httpx
import pytest
from respx.models import AllMockedAssertionError

from app.scheduler import scheduler


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "healthy"}


def test_congress_forecast_empty_db(client):
    """Runs the in-house model (seeded) with no market rows — must not 500."""
    resp = client.get("/api/forecasts/congress")
    assert resp.status_code == 200
    body = resp.json()
    assert "chambers" in body and "references" in body
    assert [c["chamber"] for c in body["chambers"]] == ["house", "senate"]


def test_list_trends_empty_db(client):
    resp = client.get("/api/trends")
    assert resp.status_code == 200
    assert resp.json() == []  # empty table → empty list, no 500


def test_scheduler_does_not_run_under_testclient(client):
    """AC-2 / TC-2: lifespan gates the scheduler off (DISABLE_SCHEDULER=1)."""
    assert scheduler.running is False
    assert scheduler.get_jobs() == []


def test_unmocked_http_raises(respx_router):
    """AC-2 / TC-3: the autouse guard makes any unmocked outbound call fail loudly
    instead of reaching the live network."""
    with pytest.raises(AllMockedAssertionError):
        httpx.get("https://external-api.example.com/should-not-be-reached")
