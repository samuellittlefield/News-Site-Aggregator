"""District poll scraper (Wikipedia) — v1 (district-poll-scraper-fix) plus the
district-coverage-from-wikipedia rewrite that replaced `CompetitiveDistrict` as
the scrape work list with enumeration over each state's section tree.

Covers the state-page/section-tree discovery and candidate-name table parsing
that replaced the old (silently-broken) per-district page guessing. Fixtures are
trimmed from the real 2026 section lists captured 2026-07-07 (PA, NY) and
2026-09-12 (AK):
  - `pa_house_sections.json`  — District 8 general Polling = index 141 (TC-1)
  - `ny17_house_sections.json`— primary-only Polling, no general Polling (TC-7)
  - `pa8_polling_section.wikitext` — 3 real PA-8 polls + an independent col (TC-3)
  - `ak_house_sections.json` — at-large page: General election → Polling at
    toclevel 1 (index 26), plus a primary Polling (index 19) that must never
    be matched (district-coverage-from-wikipedia AC-4/AC-5)

respx (autouse guard in conftest) mocks Wikipedia; the `db` fixture rolls back.

TC-N references below without a file prefix are
`docs/features/district-coverage-from-wikipedia/04-test-cases.md`'s numbering;
"that file"/inline comments above referring to TC-1/TC-7 are this file's own
pre-existing (district-poll-scraper-fix) labels and are left as they were.
"""
import json
import logging
import pathlib
from typing import Optional

import httpx
import pytest

from app import scheduler
from app.elections.services import house_polls
from app.models import CompetitiveDistrict, GenericBallotAggregate, HousePoll, SourceRun

FIX = pathlib.Path(__file__).parent / "fixtures"
PA_SECTIONS = json.loads((FIX / "pa_house_sections.json").read_text())
NY17_SECTIONS = json.loads((FIX / "ny17_house_sections.json").read_text())
AK_SECTIONS = json.loads((FIX / "ak_house_sections.json").read_text())
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


def _multi_state_responder(
    sections_by_page_fragment: dict,
    wikitext_by_section: Optional[dict] = None,
    error_by_page_fragment: Optional[dict] = None,
):
    """Build a respx side_effect covering all 50 states: named page fragments
    (e.g. "Pennsylvania") get their real sections/wikitext fixtures; an
    unmatched state gets an empty (but well-formed) sections response, so
    enumeration yields nothing for it rather than erroring."""
    wikitext_by_section = wikitext_by_section or {}
    error_by_page_fragment = error_by_page_fragment or {}

    def responder(request):
        page = request.url.params.get("page", "")
        prop = request.url.params.get("prop")
        for frag, err in error_by_page_fragment.items():
            if frag in page:
                return httpx.Response(200, json={"error": err})
        for frag, sections_json in sections_by_page_fragment.items():
            if frag in page:
                if prop == "sections":
                    return httpx.Response(200, json=sections_json)
                section = request.url.params.get("section")
                return _wiki_response(wikitext_by_section.get(section, ""))
        if prop == "sections":
            return httpx.Response(200, json={"parse": {"sections": []}})
        return _wiki_response("")

    return responder


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
    with caplog.at_level(logging.WARNING, logger="app.elections.services.house_polls"):
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
    with caplog.at_level(logging.WARNING, logger="app.elections.services.house_polls"):
        async with httpx.AsyncClient() as client:
            sections = await house_polls._fetch_state_sections(client, "ZZ")
    assert sections == []
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any("ZZ" in m and "missingtitle" in m for m in warnings)


# ── TC-5: one state's failure doesn't block other states (AC-5) ────────────────

async def test_one_state_failure_does_not_block_others(db, respx_router, caplog):
    # No CompetitiveDistrict seeding needed — the work list now comes from
    # Wikipedia's section tree for all 50 states, not from that table.
    def responder(request):
        page = request.url.params.get("page", "")
        if "Ohio" in page:
            return httpx.Response(200, json={"error": {"code": "missingtitle"}})
        if "Pennsylvania" not in page:
            # The other 48 states: a normal page with no matching districts.
            if request.url.params.get("prop") == "sections":
                return httpx.Response(200, json={"parse": {"sections": []}})
            return _wiki_response("")
        if request.url.params.get("prop") == "sections":
            return httpx.Response(200, json=PA_SECTIONS)
        # PA has two resolvable districts (7 -> 111, 8 -> 141); only give
        # District 8 real poll data so the "3 polls, all PA-8" assertions hold.
        if request.url.params.get("section") == "141":
            return _wiki_response(PA8_WIKITEXT)
        return _wiki_response("")

    respx_router.get(house_polls.WIKI_API).mock(side_effect=responder)

    with caplog.at_level(logging.WARNING, logger="app.elections.services.house_polls"):
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
    # No CompetitiveDistrict seeding needed — coverage comes from the section
    # tree, not from that table, for all 50 states.
    holder = {"wikitext": PA8_WIKITEXT}

    def responder(request):
        page = request.url.params.get("page", "")
        if "Pennsylvania" not in page:
            if request.url.params.get("prop") == "sections":
                return httpx.Response(200, json={"parse": {"sections": []}})
            return _wiki_response("")
        if request.url.params.get("prop") == "sections":
            return httpx.Response(200, json=PA_SECTIONS)
        # PA has two resolvable districts (7 -> 111, 8 -> 141); only District 8
        # carries real poll data so counts stay tied to district 8 as before.
        if request.url.params.get("section") == "141":
            return _wiki_response(holder["wikitext"])
        return _wiki_response("")

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


# ═════════════════════════════════════════════════════════════════════════
# district-coverage-from-wikipedia: scrape list comes from the section tree,
# not from CompetitiveDistrict. TC-N below is
# docs/features/district-coverage-from-wikipedia/04-test-cases.md's numbering.
# ═════════════════════════════════════════════════════════════════════════

# ── TC-1: the work list is not built from CompetitiveDistrict (AC-1) ───────────

async def test_fetch_never_queries_competitive_district_for_work_list(db, respx_router):
    assert db.query(CompetitiveDistrict).count() == 0  # nothing seeded

    respx_router.get(house_polls.WIKI_API).mock(
        side_effect=_multi_state_responder(
            {"Pennsylvania": PA_SECTIONS},
            {"141": PA8_WIKITEXT},
        )
    )

    await house_polls.fetch_district_polls(db)

    pa8 = db.query(HousePoll).filter(HousePoll.state == "PA", HousePoll.district == 8).all()
    assert len(pa8) == 3


# ── TC-2: enumeration yields every district with general Polling, one pass (AC-2) ──

def test_iter_polling_sections_yields_all_resolvable_districts():
    result = dict(house_polls._iter_polling_sections(_sections(PA_SECTIONS)))
    assert result == {7: 111, 8: 141}  # District 9 (primary-only) is absent


# ── TC-3: enumeration doesn't skip a district absent from CompetitiveDistrict (AC-2) ──

async def test_district_absent_from_competitive_district_is_still_scraped(db, respx_router):
    _seed_district(db, "PA", 7)  # PA-8 deliberately not seeded

    respx_router.get(house_polls.WIKI_API).mock(
        side_effect=_multi_state_responder(
            {"Pennsylvania": PA_SECTIONS},
            {"141": PA8_WIKITEXT},
        )
    )

    await house_polls.fetch_district_polls(db)

    pa8 = db.query(HousePoll).filter(HousePoll.state == "PA", HousePoll.district == 8).all()
    assert len(pa8) == 3


# ── TC-4: primary-only Polling excluded under enumeration, not just lookup (AC-3) ──

def test_iter_polling_sections_excludes_primary_only_polling():
    result = dict(house_polls._iter_polling_sections(_sections(NY17_SECTIONS)))
    assert 17 not in result


# ── TC-5: general Polling after a primary Polling still wins under enumeration (AC-3) ──

def test_iter_polling_sections_prefers_general_over_primary_polling():
    sections = [
        {"toclevel": 1, "line": "District 5", "index": "10"},
        {"toclevel": 2, "line": "Democratic primary", "index": "11"},
        {"toclevel": 3, "line": "Polling", "index": "12"},          # primary
        {"toclevel": 2, "line": "General election", "index": "20"},
        {"toclevel": 3, "line": "Candidates", "index": "21"},
        {"toclevel": 3, "line": "Polling", "index": "22"},          # general (want)
    ]
    assert dict(house_polls._iter_polling_sections(sections)) == {5: 22}


# ── TC-6: at-large state pages resolve the singular title and return 200 (AC-4) ──

def test_at_large_states_use_singular_page_title():
    for state in house_polls.AT_LARGE_STATES:
        name = house_polls.STATE_NAMES[state]
        assert house_polls._state_wiki_page(state) == (
            f"2026_United_States_House_of_Representatives_election_in_{name}"
        )
    # Non-at-large states are unaffected — plural form, unchanged.
    assert house_polls._state_wiki_page("PA") == (
        "2026_United_States_House_of_Representatives_elections_in_Pennsylvania"
    )


async def test_at_large_page_fetch_succeeds_with_singular_title(respx_router, caplog):
    def responder(request):
        page = request.url.params.get("page", "")
        assert "election_in_Alaska" in page and "elections_in_Alaska" not in page
        return httpx.Response(200, json=AK_SECTIONS)

    respx_router.get(house_polls.WIKI_API).mock(side_effect=responder)

    with caplog.at_level(logging.WARNING, logger="app.elections.services.house_polls"):
        async with httpx.AsyncClient() as client:
            sections = await house_polls._fetch_state_sections(client, "AK")

    assert sections == _sections(AK_SECTIONS)
    assert not any("missingtitle" in r.getMessage() for r in caplog.records)


# ── TC-7: at-large enumeration yields district 0, ignoring the primary Polling (AC-5) ──

def test_at_large_enumeration_yields_district_zero():
    result = dict(house_polls._iter_polling_sections(_sections(AK_SECTIONS)))
    assert result == {0: 26}  # never 19, the primary's Polling index


# ── TC-8: the section list is fetched once per state, not once per district (AC-2) ──

async def test_sections_fetched_once_per_state_not_per_district(db, respx_router):
    respx_router.get(house_polls.WIKI_API).mock(
        side_effect=_multi_state_responder(
            {"Pennsylvania": PA_SECTIONS},
            {"111": PA8_WIKITEXT, "141": PA8_WIKITEXT},
        )
    )

    await house_polls.fetch_district_polls(db)

    sections_calls = [
        c for c in respx_router.calls
        if "Pennsylvania" in c.request.url.params.get("page", "")
        and c.request.url.params.get("prop") == "sections"
    ]
    assert len(sections_calls) == 1  # not once per district (7 and 8 both resolved)


# ── TC-9: all 50 states are attempted regardless of CompetitiveDistrict (AC-2) ──

async def test_all_fifty_states_are_attempted(db, respx_router):
    respx_router.get(house_polls.WIKI_API).mock(
        side_effect=_multi_state_responder({"Pennsylvania": PA_SECTIONS})
    )

    await house_polls.fetch_district_polls(db)

    sections_calls = {
        c.request.url.params.get("page", "")
        for c in respx_router.calls
        if c.request.url.params.get("prop") == "sections"
    }
    assert len(sections_calls) == 50


# ── TC-10: CompetitiveDistrict's other consumers are unaffected (AC-6) ─────────

def test_seed_districts_unaffected(db):
    count = house_polls.seed_districts(db)
    assert count == len(house_polls.COMPETITIVE_DISTRICTS)
    assert db.query(CompetitiveDistrict).count() == len(house_polls.COMPETITIVE_DISTRICTS)


def test_districts_endpoint_still_reads_competitive_district(client, db):
    house_polls.seed_districts(db)
    resp = client.get("/api/polls/house/districts")
    assert resp.status_code == 200
    assert len(resp.json()) > 0


# ── TC-11: a district with no general Polling descendant is a clean skip (AC-7) ──

async def test_district_with_no_general_polling_is_not_fetched(db, respx_router, caplog):
    respx_router.get(house_polls.WIKI_API).mock(
        side_effect=_multi_state_responder(
            {"Pennsylvania": PA_SECTIONS},
            {"111": PA8_WIKITEXT, "141": PA8_WIKITEXT},
        )
    )

    with caplog.at_level(logging.WARNING, logger="app.elections.services.house_polls"):
        await house_polls.fetch_district_polls(db)

    # District 9's own indexes (160-163) must never be requested.
    requested_sections = {
        c.request.url.params.get("section")
        for c in respx_router.calls
        if "Pennsylvania" in c.request.url.params.get("page", "")
    }
    assert "162" not in requested_sections
    assert not any("District 9" in r.getMessage() for r in caplog.records)


# ── TC-13: zero resolved sections across all 50 states raises (AC-9) ───────────

async def test_zero_coverage_across_all_states_raises(db, respx_router):
    respx_router.get(house_polls.WIKI_API).mock(
        return_value=httpx.Response(200, json={"parse": {"sections": [
            {"toclevel": 1, "line": "Overview", "index": "1"},
            {"toclevel": 1, "line": "See also", "index": "2"},
        ]}})
    )

    with pytest.raises(RuntimeError, match="zero districts"):
        await house_polls.fetch_district_polls(db)


# ── TC-14: zero coverage records a SourceRun failure via the scheduler (AC-9) ──

async def test_zero_coverage_records_sourcerun_failure(db, respx_router, monkeypatch):
    monkeypatch.setattr(scheduler, "SessionLocal", lambda: db)
    monkeypatch.setattr(db, "close", lambda: None)

    def responder(request):
        page = request.url.params.get("page", "")
        if page == house_polls.HOUSE_2026_PAGE:
            # Generic ballot succeeds independently of district-poll coverage.
            return _wiki_response(
                "{|\n|-\n! Source\n! Rep\n! Dem\n|-\n| Data Insights\n| 45%\n| 47%\n|}"
            )
        return httpx.Response(200, json={"parse": {"sections": [
            {"toclevel": 1, "line": "Overview", "index": "1"},
        ]}})

    respx_router.get(house_polls.WIKI_API).mock(side_effect=responder)

    await scheduler.refresh_house_polls()

    row = db.query(SourceRun).filter(SourceRun.source_id == "house_polls_job").one()
    assert row.status == "failure"
    assert row.item_count is None
    assert "zero districts" in (row.error_message or "")
    # The generic ballot's rows were still committed before district polls ran.
    assert db.query(GenericBallotAggregate).count() > 0


# ── TC-15: a partial run (some states fail/resolve nothing) is still a success (AC-10) ──

async def test_partial_coverage_is_a_success(db, respx_router, monkeypatch):
    monkeypatch.setattr(scheduler, "SessionLocal", lambda: db)
    monkeypatch.setattr(db, "close", lambda: None)

    respx_router.get(house_polls.WIKI_API).mock(
        side_effect=_multi_state_responder(
            {"Pennsylvania": PA_SECTIONS},
            {"141": PA8_WIKITEXT},
            error_by_page_fragment={"Ohio": {"code": "missingtitle"}},
        )
    )

    total = await house_polls.fetch_district_polls(db)
    assert total == 3  # no raise — PA resolved, that's enough

    await scheduler.refresh_house_polls()
    row = db.query(SourceRun).filter(SourceRun.source_id == "house_polls_job").one()
    assert row.status == "success"
