"""Auth on write endpoints (write-endpoint-auth). See docs/features/write-endpoint-auth/.

TC-1..TC-4, TC-10 cover the require_admin_key dependency on the two candidate
issue-tag write routes. TC-5..TC-7 cover /api/refresh staying public with an
in-memory cooldown instead. ADMIN_API_KEY is read at call time by the
dependency, so each test sets it via monkeypatch rather than relying on
process env.
"""
from datetime import timedelta, timezone
from datetime import datetime as dt

import app.main as main_module
from app.models import Candidate, CandidateIssueTag

ADMIN_KEY = "test-secret"


def _seed_candidate_and_tag(db):
    candidate = Candidate(name="Jane Doe", state="CA", office="H", district=12)
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    tag = CandidateIssueTag(
        candidate_id=candidate.id,
        issue_code="healthcare",
        ai_suggested=True,
        confirmed=False,
        rejected=False,
    )
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return candidate, tag


async def _noop_refresh():
    pass


def _reset_refresh_state(monkeypatch):
    """Prevent /api/refresh tests from tripping the real refresh jobs (which
    would hit the network and get blocked by the autouse respx guard) and from
    leaking cooldown state between tests."""
    monkeypatch.setattr(main_module, "_do_full_refresh", _noop_refresh)
    monkeypatch.setattr(main_module, "_last_refresh_at", None)


# ── TC-1: Missing key rejected on both write routes (AC-1) ──────────────────

def test_missing_key_rejected_on_post_issues(client, db, monkeypatch):
    monkeypatch.setenv("ADMIN_API_KEY", ADMIN_KEY)
    candidate, _tag = _seed_candidate_and_tag(db)

    resp = client.post(f"/api/candidates/{candidate.id}/issues", json={"issue_code": "climate"})
    assert resp.status_code == 401

    tags = db.query(CandidateIssueTag).filter(CandidateIssueTag.candidate_id == candidate.id).all()
    assert len(tags) == 1  # only the seeded tag — nothing new written


def test_missing_key_rejected_on_patch_issues(client, db, monkeypatch):
    monkeypatch.setenv("ADMIN_API_KEY", ADMIN_KEY)
    candidate, tag = _seed_candidate_and_tag(db)

    resp = client.patch(
        f"/api/candidates/{candidate.id}/issues/{tag.id}", json={"confirmed": True}
    )
    assert resp.status_code == 401

    db.refresh(tag)
    assert tag.confirmed is False  # unchanged


def test_empty_header_treated_as_wrong_key(client, db, monkeypatch):
    """Edge case called out in 04-test-cases.md: an empty header string must
    401 like a wrong key, not be treated as 'no header'."""
    monkeypatch.setenv("ADMIN_API_KEY", ADMIN_KEY)
    candidate, _tag = _seed_candidate_and_tag(db)

    resp = client.post(
        f"/api/candidates/{candidate.id}/issues",
        json={"issue_code": "climate"},
        headers={"X-Admin-Key": ""},
    )
    assert resp.status_code == 401


# ── TC-2: Wrong key rejected (AC-2) ──────────────────────────────────────────

def test_wrong_key_rejected_on_post_issues(client, db, monkeypatch):
    monkeypatch.setenv("ADMIN_API_KEY", ADMIN_KEY)
    candidate, _tag = _seed_candidate_and_tag(db)

    resp = client.post(
        f"/api/candidates/{candidate.id}/issues",
        json={"issue_code": "climate"},
        headers={"X-Admin-Key": "wrong-value"},
    )
    assert resp.status_code == 401
    tags = db.query(CandidateIssueTag).filter(CandidateIssueTag.candidate_id == candidate.id).all()
    assert len(tags) == 1


def test_wrong_key_rejected_on_patch_issues(client, db, monkeypatch):
    monkeypatch.setenv("ADMIN_API_KEY", ADMIN_KEY)
    candidate, tag = _seed_candidate_and_tag(db)

    resp = client.patch(
        f"/api/candidates/{candidate.id}/issues/{tag.id}",
        json={"confirmed": True},
        headers={"X-Admin-Key": "wrong-value"},
    )
    assert resp.status_code == 401
    db.refresh(tag)
    assert tag.confirmed is False


# ── TC-3: Correct key succeeds, response unchanged (AC-3) ────────────────────

def test_correct_key_succeeds_on_post_issues(client, db, monkeypatch):
    monkeypatch.setenv("ADMIN_API_KEY", ADMIN_KEY)
    candidate, _tag = _seed_candidate_and_tag(db)

    resp = client.post(
        f"/api/candidates/{candidate.id}/issues",
        json={"issue_code": "climate"},
        headers={"X-Admin-Key": ADMIN_KEY},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["issue_code"] == "climate"
    assert body["confirmed"] is True

    created = (
        db.query(CandidateIssueTag)
        .filter(CandidateIssueTag.candidate_id == candidate.id, CandidateIssueTag.issue_code == "climate")
        .first()
    )
    assert created is not None


def test_correct_key_succeeds_on_patch_issues(client, db, monkeypatch):
    monkeypatch.setenv("ADMIN_API_KEY", ADMIN_KEY)
    candidate, tag = _seed_candidate_and_tag(db)

    resp = client.patch(
        f"/api/candidates/{candidate.id}/issues/{tag.id}",
        json={"confirmed": True},
        headers={"X-Admin-Key": ADMIN_KEY},
    )
    assert resp.status_code == 200
    assert resp.json()["confirmed"] is True

    db.refresh(tag)
    assert tag.confirmed is True


# ── TC-4: Unset ADMIN_API_KEY fails closed (AC-4) ────────────────────────────

def test_unset_admin_key_fails_closed_no_header(client, db, monkeypatch):
    monkeypatch.delenv("ADMIN_API_KEY", raising=False)
    candidate, tag = _seed_candidate_and_tag(db)

    resp = client.post(f"/api/candidates/{candidate.id}/issues", json={"issue_code": "climate"})
    assert resp.status_code == 401

    resp2 = client.patch(f"/api/candidates/{candidate.id}/issues/{tag.id}", json={"confirmed": True})
    assert resp2.status_code == 401


def test_unset_admin_key_fails_closed_with_arbitrary_header(client, db, monkeypatch):
    monkeypatch.delenv("ADMIN_API_KEY", raising=False)
    candidate, tag = _seed_candidate_and_tag(db)

    resp = client.post(
        f"/api/candidates/{candidate.id}/issues",
        json={"issue_code": "climate"},
        headers={"X-Admin-Key": "anything-at-all"},
    )
    assert resp.status_code == 401

    resp2 = client.patch(
        f"/api/candidates/{candidate.id}/issues/{tag.id}",
        json={"confirmed": True},
        headers={"X-Admin-Key": "anything-at-all"},
    )
    assert resp2.status_code == 401


# ── TC-5: /api/refresh still requires no key (AC-5) ──────────────────────────

def test_refresh_requires_no_key(client, monkeypatch):
    _reset_refresh_state(monkeypatch)
    resp = client.post("/api/refresh")
    assert resp.status_code != 401


# ── TC-6: Rapid repeat /api/refresh calls hit the cooldown (AC-6) ────────────

def test_refresh_cooldown_blocks_rapid_repeat(client, monkeypatch):
    _reset_refresh_state(monkeypatch)
    calls = []

    async def counting_refresh():
        calls.append(1)

    monkeypatch.setattr(main_module, "_do_full_refresh", counting_refresh)

    resp1 = client.post("/api/refresh")
    assert resp1.status_code == 200

    resp2 = client.post("/api/refresh")
    assert resp2.status_code == 429

    assert len(calls) == 1  # second call never queued another refresh


# ── TC-7: Cooldown clears after the window (AC-7) ────────────────────────────

def test_refresh_cooldown_clears_after_window(client, monkeypatch):
    _reset_refresh_state(monkeypatch)

    resp1 = client.post("/api/refresh")
    assert resp1.status_code == 200

    # Simulate the cooldown window having fully elapsed.
    elapsed_time = dt.now(timezone.utc) - timedelta(seconds=main_module.REFRESH_COOLDOWN_SECONDS + 1)
    monkeypatch.setattr(main_module, "_last_refresh_at", elapsed_time)

    resp2 = client.post("/api/refresh")
    assert resp2.status_code == 200


# ── TC-10: Existing unauthenticated GET routes unaffected (regression) ──────

def test_get_routes_unaffected_by_admin_key(client, monkeypatch):
    monkeypatch.delenv("ADMIN_API_KEY", raising=False)  # even fully unset

    assert client.get("/api/candidates/issues/pending").status_code == 200
    assert client.get("/api/candidates/taxonomy").status_code == 200
    assert client.get("/api/debug/sources").status_code == 200
