"""VoteHub district (us-representative) polls → HousePoll — v2 of the fix.

Party is resolved by matching VoteHub candidate names against the Candidate
table, never from the poll's own `partisan` field (the sponsor's lean, AC-11).
Unresolvable names are skipped and logged, never guessed (AC-9). Rows are stored
with source="votehub" and a namespaced poll_id so they never collide with the
Wikipedia stream (AC-10). respx mocks upstream; the `db` fixture rolls back.
"""
import inspect
import json
import logging
import pathlib

import httpx
import pytest

from app.services import votehub
from app.models import Candidate, HousePoll

FIX = pathlib.Path(__file__).parent / "fixtures"
US_REP = json.loads((FIX / "votehub_us_representative.json").read_text())


def _seed_candidate(db, name, party, state, district):
    db.add(Candidate(name=name, party=party, state=state, district=district, office="H"))
    db.flush()


def _mock(respx_router, payload):
    respx_router.get(votehub.VOTEHUB_URL).mock(
        return_value=httpx.Response(200, json=payload)
    )


# ── TC-8: VoteHub us-representative polls are fetched and parsed (AC-8) ─────────

async def test_votehub_house_poll_is_fetched_and_parsed(db, respx_router):
    _seed_candidate(db, "Nick Begich III", "REP", "AK", 1)
    _seed_candidate(db, "Matt Schultz", "DEM", "AK", 1)
    _mock(respx_router, US_REP)

    saved = await votehub.fetch_votehub_house_polls(db)
    assert saved == 1

    row = db.query(HousePoll).filter(HousePoll.poll_id == "votehub-ak01-ppp-2026-06").one()
    assert row.state == "AK" and row.district == 1
    assert row.source == "votehub"
    assert row.rep == 46.0   # Begich (REP), not swapped
    assert row.dem == 39.0   # Schultz (DEM)


# ── TC-9: unmatched / ambiguous names are skipped and logged, not guessed ───────

def test_match_candidate_party_zero_and_ambiguous():
    crosswalk = {"begich nick": ["REP"], "smith john": ["DEM", "REP"]}
    assert votehub._match_candidate_party("Nick Begich III", crosswalk) == "REP"
    assert votehub._match_candidate_party("Jane Unknown", crosswalk) is None   # zero match
    assert votehub._match_candidate_party("John Smith", crosswalk) is None     # ambiguous


async def test_unmatched_name_is_skipped_and_logged(db, respx_router, caplog):
    # Only one candidate seeded → the Republican answer can't be resolved.
    _seed_candidate(db, "Matt Schultz", "DEM", "AK", 1)
    _mock(respx_router, US_REP)

    with caplog.at_level(logging.WARNING, logger="app.services.votehub"):
        saved = await votehub.fetch_votehub_house_polls(db)

    assert saved == 0
    assert db.query(HousePoll).count() == 0
    msgs = " ".join(r.getMessage() for r in caplog.records)
    assert "AK-01" in msgs and "Nick Begich III" in msgs


async def test_ambiguous_name_is_skipped_and_logged(db, respx_router, caplog):
    # Two DEM candidates with the same normalized name → ambiguous, never guessed.
    _seed_candidate(db, "Nick Begich III", "REP", "AK", 1)
    _seed_candidate(db, "Matt Schultz", "DEM", "AK", 1)
    _seed_candidate(db, "Schultz, Matt", "DEM", "AK", 1)  # collides on normalized name
    _mock(respx_router, US_REP)

    with caplog.at_level(logging.WARNING, logger="app.services.votehub"):
        saved = await votehub.fetch_votehub_house_polls(db)

    assert saved == 0
    assert db.query(HousePoll).count() == 0
    assert any("Matt Schultz" in r.getMessage() for r in caplog.records)


# ── TC-10: VoteHub and Wikipedia rows are distinguishable and don't collide ─────

async def test_votehub_and_wikipedia_rows_coexist(db, respx_router):
    # A Wikipedia-sourced PA-8 row already exists.
    db.add(HousePoll(
        poll_id="wiki-PA-8-deadbeef", pollster="Lake Research Partners",
        state="PA", district=8, dem=45.0, rep=47.0, source="wikipedia",
    ))
    db.flush()

    _seed_candidate(db, "Rob Bresnahan", "REP", "PA", 8)
    _seed_candidate(db, "Paige Cognetti", "DEM", "PA", 8)
    payload = [{
        "id": "pa08-impact-2026-06", "seat_name": "PA-08",
        "pollster": "Impact Research", "partisan": "REP",
        "start_date": "2026-06-03", "end_date": "2026-06-06", "sample_size": 600,
        "answers": [
            {"choice": "Rob Bresnahan", "pct": 46.0},
            {"choice": "Paige Cognetti", "pct": 45.0},
        ],
    }]
    _mock(respx_router, payload)

    await votehub.fetch_votehub_house_polls(db)

    pa8 = db.query(HousePoll).filter(HousePoll.state == "PA", HousePoll.district == 8).all()
    assert len(pa8) == 2
    sources = {p.source for p in pa8}
    assert sources == {"wikipedia", "votehub"}
    ids = {p.poll_id for p in pa8}
    assert ids == {"wiki-PA-8-deadbeef", "votehub-pa08-impact-2026-06"}


# ── TC-11: the `partisan` field is never used as candidate party (AC-11) ────────

async def test_partisan_field_is_never_used_as_party(db, respx_router):
    # The fixture's partisan="DEM" is the sponsor's lean, but the first answer
    # (Begich) is REP. Party must come from the Candidate table, not `partisan`.
    _seed_candidate(db, "Nick Begich III", "REP", "AK", 1)
    _seed_candidate(db, "Matt Schultz", "DEM", "AK", 1)
    assert US_REP[0]["partisan"] == "DEM"
    _mock(respx_router, US_REP)

    await votehub.fetch_votehub_house_polls(db)

    row = db.query(HousePoll).filter(HousePoll.poll_id == "votehub-ak01-ppp-2026-06").one()
    assert row.rep == 46.0 and row.dem == 39.0   # from Candidate crosswalk, not partisan

    # Static guard: `partisan` is never read out of a poll in the implementation.
    src = inspect.getsource(votehub)
    assert 'partisan")' not in src     # no .get("partisan") / ("partisan")
    assert 'partisan"]' not in src     # no ["partisan"]
