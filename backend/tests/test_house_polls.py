"""District poll scraper (Wikipedia) — v1 of district-poll-scraper-fix.

Covers the state-page/section-tree discovery and candidate-name table parsing
that replaced the old (silently-broken) per-district page guessing. Fixtures are
trimmed from the real 2026 section lists captured 2026-07-07:
  - `pa_house_sections.json`  — District 8 general Polling = index 141 (TC-1)
  - `ny17_house_sections.json`— primary-only Polling, no general Polling (TC-7)
  - `pa8_polling_section.wikitext` — 3 real PA-8 polls + an independent col (TC-3)

respx (autouse guard in conftest) mocks Wikipedia; the `db` fixture rolls back.
"""
import json
import logging
import pathlib

import httpx
import pytest

from app.services import house_polls
from app.models import CompetitiveDistrict, HousePoll

FIX = pathlib.Path(__file__).parent / "fixtures"
PA_SECTIONS = json.loads((FIX / "pa_house_sections.json").read_text())
NY17_SECTIONS = json.loads((FIX / "ny17_house_sections.json").read_text())
PA8_WIKITEXT = (FIX / "pa8_polling_section.wikitext").read_text()


def _sections(fixture: dict) -> list[dict]:
    return fixture["parse"]["sections"]


def _seed_district(db, state, district):
    db.add(CompetitiveDistrict(
        state=state, district=district, cook_rating="Toss-up",
        dem_2024=49.0, rep_2024=49.0, margin_2024=0.0, lat=41.0, lng=-75.0,
        incumbent_party="D",
    ))
    db.flush()


def _wiki_response(wikitext: str) -> httpx.Response:
    return httpx.Response(200, json={"parse": {"wikitext": {"*": wikitext}}})


# ── TC-1: section discovery resolves the right Polling subsection (AC-1, AC-2) ──

async def test_find_polling_section_resolves_correct_index(respx_router):
    respx_router.get(house_polls.WIKI_API).mock(
        return_value=httpx.Response(200, json=PA_SECTIONS)
    )
    async with httpx.AsyncClient() as client:
        sections = await house_polls._fetch_state_sections(client, "PA")

    # District 8's general-election Polling is index 141; District 7 has its own.
    assert house_polls._find_polling_section(sections, 8) == 141
    assert house_polls._find_polling_section(sections, 7) == 111


# ── TC-2: district with no Polling subsection yet is a clean skip (AC-7) ────────

def test_district_without_polling_is_skipped_not_errored(caplog):
    # District 9 is still mid-primary: a primary Polling exists but no General
    # election section at all → None, and (being a plain return) no warning.
    with caplog.at_level(logging.WARNING, logger="app.services.house_polls"):
        result = house_polls._find_polling_section(_sections(PA_SECTIONS), 9)
    assert result is None
    assert caplog.records == []


# ── TC-7: primary-only Polling is never mistaken for general polling (AC-2b) ────

def test_primary_only_polling_is_not_returned():
    # NY-17: Democratic primary has a Polling child (earlier in the doc);
    # General election has none → must resolve to None, not the primary index.
    assert house_polls._find_polling_section(_sections(NY17_SECTIONS), 17) is None


def test_general_polling_after_primary_polling_is_returned():
    # Companion case: both a primary Polling and a general Polling exist; the
    # general-election one (a descendant of General election) must win.
    sections = [
        {"toclevel": 1, "line": "District 5", "index": "10"},
        {"toclevel": 2, "line": "Democratic primary", "index": "11"},
        {"toclevel": 3, "line": "Polling", "index": "12"},          # primary
        {"toclevel": 2, "line": "General election", "index": "20"},
        {"toclevel": 3, "line": "Candidates", "index": "21"},
        {"toclevel": 3, "line": "Polling", "index": "22"},          # general (want)
    ]
    assert house_polls._find_polling_section(sections, 5) == 22


# ── TC-3: candidate-named header parsing extracts correct dem/rep values (AC-3) ─

def test_extract_polls_from_polling_section():
    polls = house_polls._extract_polls_from_polling_section(PA8_WIKITEXT, "PA", 8)
    assert len(polls) == 3

    by_pollster = {p["pollster"]: p for p in polls}
    # (R) column first, (D) column second — must not be swapped.
    assert by_pollster["Lake Research Partners"]["rep"] == 47.0
    assert by_pollster["Lake Research Partners"]["dem"] == 45.0
    assert by_pollster["Impact Research"]["rep"] == 46.0
    assert by_pollster["Impact Research"]["dem"] == 45.0
    assert by_pollster["Public Policy Polling"]["rep"] == 45.0
    assert by_pollster["Public Policy Polling"]["dem"] == 43.0

    for p in polls:
        assert p["state"] == "PA" and p["district"] == 8
        # The trailing "Undecided" column (no party suffix) is never mistaken for
        # a candidate: dem/rep stay in the 40s, not the single-digit undecided %.
        assert p["dem"] > 30 and p["rep"] > 30
        # The (I) independent column is captured, not dropped.
        assert p["ind"] is not None
    assert by_pollster["Lake Research Partners"]["ind"] == 3.0


# ── TC-4: missing-page / error state fetch is logged, not swallowed (AC-4) ──────

async def test_missing_page_is_logged(respx_router, caplog):
    respx_router.get(house_polls.WIKI_API).mock(
        return_value=httpx.Response(200, json={"error": {"code": "missingtitle", "info": "no page"}})
    )
    with caplog.at_level(logging.WARNING, logger="app.services.house_polls"):
        async with httpx.AsyncClient() as client:
            sections = await house_polls._fetch_state_sections(client, "ZZ")
    assert sections == []
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any("ZZ" in m and "missingtitle" in m for m in warnings)


# ── TC-5: one state's failure doesn't block other states (AC-5) ────────────────

async def test_one_state_failure_does_not_block_others(db, respx_router, caplog):
    _seed_district(db, "PA", 8)
    _seed_district(db, "OH", 1)  # OH page will error out

    def responder(request):
        page = request.url.params.get("page", "")
        if "Ohio" in page:
            return httpx.Response(200, json={"error": {"code": "missingtitle"}})
        if request.url.params.get("prop") == "sections":
            return httpx.Response(200, json=PA_SECTIONS)
        return _wiki_response(PA8_WIKITEXT)

    respx_router.get(house_polls.WIKI_API).mock(side_effect=responder)

    with caplog.at_level(logging.WARNING, logger="app.services.house_polls"):
        total = await house_polls.fetch_district_polls(db)

    pa = db.query(HousePoll).filter(HousePoll.state == "PA", HousePoll.district == 8).all()
    oh = db.query(HousePoll).filter(HousePoll.state == "OH").all()
    assert len(pa) == 3            # healthy state still ingested
    assert len(oh) == 0            # failing state contributed nothing
    assert total == 3
    assert all(p.source == "wikipedia" for p in pa)
    assert any("OH" in r.getMessage() for r in caplog.records)


# ── TC-6: re-run is idempotent; new upstream data adds only the new row (AC-6) ──

async def test_rerun_is_idempotent_and_additive(db, respx_router):
    _seed_district(db, "PA", 8)
    holder = {"wikitext": PA8_WIKITEXT}

    def responder(request):
        if request.url.params.get("prop") == "sections":
            return httpx.Response(200, json=PA_SECTIONS)
        return _wiki_response(holder["wikitext"])

    respx_router.get(house_polls.WIKI_API).mock(side_effect=responder)

    # Run 1 → 3 rows.
    await house_polls.fetch_district_polls(db)
    assert db.query(HousePoll).filter(HousePoll.district == 8).count() == 3
    first_ids = {p.poll_id for p in db.query(HousePoll).all()}

    # Run 2, identical upstream → still 3, no duplicates.
    await house_polls.fetch_district_polls(db)
    assert db.query(HousePoll).filter(HousePoll.district == 8).count() == 3
    assert {p.poll_id for p in db.query(HousePoll).all()} == first_ids

    # Run 3, a 4th poll appears upstream → 4 rows, original 3 unchanged.
    fourth = (
        "|-\n| [[Data for Progress]]\n| June 25–27, 2026\n| 700 (LV)\n| ± 3.7%\n"
        "| 44%\n| 46%\n| 3%\n| 7%\n"
    )
    holder["wikitext"] = PA8_WIKITEXT.replace("|}", fourth + "|}")
    await house_polls.fetch_district_polls(db)
    assert db.query(HousePoll).filter(HousePoll.district == 8).count() == 4
    assert first_ids.issubset({p.poll_id for p in db.query(HousePoll).all()})
