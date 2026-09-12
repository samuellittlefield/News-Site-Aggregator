"""VoteHub district (us-representative) polls → HousePoll — candidate crosswalk fix.

Party is resolved by matching VoteHub candidate names against the Candidate
table, never from the poll's own `partisan` field (the sponsor's lean, AC-6/
AC-11 of district-poll-scraper-fix). Unresolvable names are skipped and
logged, never guessed (AC-5/AC-9). Rows are stored with source="votehub" and a
namespaced poll_id so they never collide with the Wikipedia stream. respx
mocks upstream; the `db` fixture rolls back.

The matcher (`_resolve_candidate` / `_match_candidate_party`) keys on a
structural comparison — FEC surname tokens as a contiguous suffix of the
VoteHub name's tokens, plus first-given-name agreement, diacritics folded —
rather than the old sorted-token exact-equality test. See
docs/features/votehub-candidate-crosswalk-fix/ for the full rationale.
"""
import inspect
import json
import logging
import pathlib
from collections import Counter

import httpx
import pytest

from app.elections.services import votehub
from app.models import Candidate, HousePoll

FIX = pathlib.Path(__file__).parent / "fixtures"
US_REP = json.loads((FIX / "votehub_us_representative.json").read_text())
FEC_FILED = json.loads((FIX / "fec_house_filed_2026.json").read_text())


def _seed_candidate(db, name, party, state, district):
    db.add(Candidate(name=name, party=party, state=state, district=district, office="H"))
    db.flush()


def _mock(respx_router, payload):
    respx_router.get(votehub.VOTEHUB_URL).mock(
        return_value=httpx.Response(200, json=payload)
    )


# ── Pure-function tests: _fold, _tokens, _fec_name_parts (AC-1, AC-2, AC-3) ─────

def test_fold_strips_diacritics_and_folds_punctuation():
    assert votehub._fold("María Elvira Salazar") == votehub._fold("Maria Elvira Salazar")


def test_tokens_drops_honorifics_and_suffixes():
    assert votehub._tokens("Pautsch, David Alfred Mr.") == ["pautsch", "david", "alfred"]
    assert votehub._tokens("Nick Begich III") == ["nick", "begich"]


def test_tokens_agree_on_reordered_name():
    assert set(votehub._tokens("Hurd, Jeffrey")) == set(votehub._tokens("Jeffrey Hurd"))


def test_fec_name_parts_splits_on_first_comma():
    assert votehub._fec_name_parts("Miller-Meeks, Mariannette Jane") == (
        ["miller", "meeks"], ["mariannette", "jane"],
    )
    assert votehub._fec_name_parts("De La Cruz, Monica") == (["de", "la", "cruz"], ["monica"])
    assert votehub._fec_name_parts("Van Orden, Derrick") == (["van", "orden"], ["derrick"])


def test_fec_name_parts_falls_back_to_last_token_with_no_comma():
    assert votehub._fec_name_parts("Nolastname") == (["nolastname"], [])


# ── AC-1: FEC `Last, First` still matches VoteHub `First Last` ─────────────────

def test_reordered_name_matches():
    assert votehub._match_candidate_party(
        "Jeffrey Hurd", [("Hurd, Jeffrey", "REP")]
    ) == "REP"


# ── AC-2: an extra middle name or initial on either side still matches ─────────

def test_extra_middle_token_on_fec_side_matches():
    assert votehub._match_candidate_party(
        "Mariannette Miller-Meeks", [("Miller-Meeks, Mariannette Jane", "REP")]
    ) == "REP"


def test_extra_middle_token_on_votehub_side_matches():
    assert votehub._match_candidate_party(
        "Mariannette Jane Miller-Meeks", [("Miller-Meeks, Mariannette", "REP")]
    ) == "REP"


# ── AC-2b: compound and particle surnames match via contiguous suffix ──────────

@pytest.mark.parametrize("fec_name,votehub_name", [
    ("De La Cruz, Monica", "Monica De La Cruz"),
    ("Van Orden, Derrick", "Derrick Van Orden"),
    ("Gluesenkamp Perez, Marie", "Marie Gluesenkamp Perez"),
    ("Miller-Meeks, Mariannette Jane", "Mariannette Miller-Meeks"),
    ("von Wilpert, Marni", "Marni von Wilpert"),
])
def test_compound_surname_matches_via_suffix_not_last_token(fec_name, votehub_name):
    assert votehub._match_candidate_party(votehub_name, [(fec_name, "DEM")]) == "DEM"
    # Regression guard: confirm these are genuinely multi-token surnames, so a
    # last-token implementation would provably fail them (AC-2b's defect).
    surname_tokens, _ = votehub._fec_name_parts(fec_name)
    assert len(surname_tokens) > 1


# ── AC-3: diacritics do not defeat a match; stored values are untouched ────────

async def test_diacritics_do_not_defeat_match_and_stored_name_is_untouched(db):
    _seed_candidate(db, "Salazar, Maria Elvira", "REP", "FL", 27)
    row = db.query(Candidate).filter(Candidate.state == "FL", Candidate.district == 27).one()

    assert votehub._match_candidate_party(
        "María Elvira Salazar", [(row.name, "REP")]
    ) == "REP"
    assert row.name == "Salazar, Maria Elvira"   # comparison-only folding, no mutation


# ── AC-4: a nickname resolves only via a unique surname ────────────────────────

async def test_nickname_resolves_via_unique_surname(db, respx_router):
    _seed_candidate(db, "Hurd, Jeffrey", "REP", "CO", 3)
    _seed_candidate(db, "Frisch, Adam", "DEM", "CO", 3)
    _mock(respx_router, US_REP)

    saved = await votehub.fetch_votehub_house_polls(db)
    assert saved >= 1

    row = db.query(HousePoll).filter(HousePoll.poll_id == "votehub-co03-cnn-2026-07").one()
    assert row.rep == 48.0   # Jeff -> Hurd, Jeffrey via unique surname
    assert row.dem == 44.0   # Adam Frisch via exact match


async def test_colliding_surname_never_falls_back_and_is_skipped(db, respx_router, caplog):
    # Two Garcias in the same district, VoteHub's given name matches neither —
    # the surname fallback must not guess between them (AC-4 negative case).
    _seed_candidate(db, "Garcia, Ana", "DEM", "TX", 28)
    _seed_candidate(db, "Garcia, Luis", "REP", "TX", 28)
    _seed_candidate(db, "Hernandez, Luis", "REP", "TX", 28)
    _mock(respx_router, US_REP)

    with caplog.at_level(logging.WARNING, logger="app.elections.services.votehub"):
        await votehub.fetch_votehub_house_polls(db)

    assert db.query(HousePoll).filter(HousePoll.poll_id == "votehub-tx28-uh-2026-07").count() == 0
    msgs = " ".join(r.getMessage() for r in caplog.records)
    assert "TX-28" in msgs and "Maria Garcia" in msgs


# ── AC-4b: the stored-unique / filed-ambiguous scope gap has zero occurrences ──

async def test_ac4b_stored_unique_surname_never_ambiguous_among_filed(db):
    """Committed-fixture regression tripwire (no live FEC call — respected by
    the autouse respx guard). If this ever fails, that is the signal to
    promote roadmap #19, not to loosen AC-4's surname-fallback scope."""
    stored = [
        ("Nick Begich III", "REP", "AK", 0),
        ("Matt Schultz", "DEM", "AK", 0),
        ("Hurd, Jeffrey", "REP", "CO", 3),
        ("Frisch, Adam", "DEM", "CO", 3),
        ("Van Orden, Derrick", "REP", "WI", 3),
        ("Cooke, Rebecca", "DEM", "WI", 3),
        ("Salazar, Maria Elvira", "REP", "FL", 27),
        ("Gonzalez, Kristen", "DEM", "FL", 27),
        ("Miller-Meeks, Mariannette Jane", "REP", "IA", 1),
        ("Bohannan, Christina", "DEM", "IA", 1),
        ("Smith, John Robert", "DEM", "OH", 15),
        ("Smith, John Michael", "REP", "OH", 15),
        ("Jones, Pat", "REP", "OH", 15),
        ("Garcia, Ana", "DEM", "TX", 28),
        ("Garcia, Luis", "REP", "TX", 28),
        ("Hernandez, Luis", "REP", "TX", 28),
        ("Smith, Alice", "REP", "NY", 21),
        ("Jones, Bob", "DEM", "NY", 21),
    ]
    for name, party, state, district in stored:
        _seed_candidate(db, name, party, state, district)

    polled_districts = {
        votehub._parse_seat(p["seat_name"])
        for p in US_REP
        if votehub._parse_seat(p["seat_name"])
    }
    assert len(polled_districts) >= 8   # sanity: the fixture actually covers several districts

    stored_by_district: dict = {}
    for name, _party, state, district in stored:
        stored_by_district.setdefault((state, district), []).append(name)

    filed_by_district: dict = {}
    for row in FEC_FILED:
        key = (row["state"], row["district_number"])
        filed_by_district.setdefault(key, []).append(row["name"])

    for key in polled_districts:
        stored_surnames = Counter(
            tuple(votehub._fec_name_parts(n)[0]) for n in stored_by_district.get(key, [])
        )
        filed_surnames = Counter(
            tuple(votehub._fec_name_parts(n)[0]) for n in filed_by_district.get(key, [])
        )
        unique_in_stored = {sur for sur, n in stored_surnames.items() if n == 1}
        ambiguous_in_filed = {sur for sur, n in filed_surnames.items() if n > 1}

        collisions = unique_in_stored & ambiguous_in_filed
        assert not collisions, (
            f"{key}: surname(s) {collisions} unique among stored candidates but "
            f"ambiguous among all FEC-filed candidates — this is the AC-4b tripwire; "
            f"promote roadmap #19 rather than loosening AC-4"
        )


# ── AC-5: ambiguity still loses, even across two exact matches ─────────────────

async def test_two_exact_matches_is_ambiguous_and_skipped(db, respx_router, caplog):
    _seed_candidate(db, "Smith, John Robert", "DEM", "OH", 15)
    _seed_candidate(db, "Smith, John Michael", "REP", "OH", 15)
    _seed_candidate(db, "Jones, Pat", "REP", "OH", 15)
    _mock(respx_router, US_REP)

    with caplog.at_level(logging.WARNING, logger="app.elections.services.votehub"):
        await votehub.fetch_votehub_house_polls(db)

    assert db.query(HousePoll).filter(HousePoll.poll_id == "votehub-oh15-baldwin-2026-08").count() == 0
    msgs = " ".join(r.getMessage() for r in caplog.records)
    assert "John Smith" in msgs


def test_match_candidate_party_zero_and_ambiguous():
    candidates = [
        ("Begich, Nick", "REP"),
        ("Smith, John Robert", "DEM"),
        ("Smith, John Michael", "REP"),
    ]
    assert votehub._match_candidate_party("Nick Begich III", candidates) == "REP"
    assert votehub._match_candidate_party("Jane Unknown", candidates) is None    # zero match
    assert votehub._match_candidate_party("John Smith", candidates) is None      # two exact matches


async def test_unmatched_name_is_skipped_and_logged(db, respx_router, caplog):
    # Only one AK candidate seeded → the Republican answer can't be resolved.
    _seed_candidate(db, "Matt Schultz", "DEM", "AK", 0)
    _mock(respx_router, US_REP)

    with caplog.at_level(logging.WARNING, logger="app.elections.services.votehub"):
        saved = await votehub.fetch_votehub_house_polls(db)

    assert db.query(HousePoll).filter(HousePoll.poll_id == "votehub-ak01-ppp-2026-06").count() == 0
    msgs = " ".join(r.getMessage() for r in caplog.records)
    assert "AK-01" in msgs and "Nick Begich III" in msgs


# ── AC-6 (AC-11 of district-poll-scraper-fix): `partisan` is never consulted ───

async def test_partisan_field_is_never_used_as_party(db, respx_router):
    # The fixture's partisan="DEM" is the sponsor's lean, but the first answer
    # (Begich) is REP. Party must come from the Candidate table, not `partisan`.
    _seed_candidate(db, "Nick Begich III", "REP", "AK", 0)
    _seed_candidate(db, "Matt Schultz", "DEM", "AK", 0)
    assert US_REP[0]["partisan"] == "DEM"
    _mock(respx_router, US_REP)

    await votehub.fetch_votehub_house_polls(db)

    row = db.query(HousePoll).filter(HousePoll.poll_id == "votehub-ak01-ppp-2026-06").one()
    assert row.rep == 46.0 and row.dem == 39.0   # from Candidate crosswalk, not partisan

    # Static guard: `partisan` is never read out of a poll in the implementation.
    src = inspect.getsource(votehub)
    assert 'partisan")' not in src     # no .get("partisan") / ("partisan")
    assert 'partisan"]' not in src     # no ["partisan"]


# ── AC-7: at-large seats resolve to district 0 ──────────────────────────────────

def test_parse_seat_at_large_states_always_resolve_to_district_zero():
    assert votehub._parse_seat("AK-01") == ("AK", 0)
    assert votehub._parse_seat("AK-AL") == ("AK", 0)
    assert votehub._parse_seat("PA-08") == ("PA", 8)


async def test_at_large_poll_stores_district_zero(db, respx_router):
    _seed_candidate(db, "Nick Begich III", "REP", "AK", 0)
    _seed_candidate(db, "Matt Schultz", "DEM", "AK", 0)
    _mock(respx_router, US_REP)

    await votehub.fetch_votehub_house_polls(db)

    row = db.query(HousePoll).filter(HousePoll.poll_id == "votehub-ak01-ppp-2026-06").one()
    assert row.state == "AK" and row.district == 0


# ── AC-8: generic party labels are skipped, and counted as their own cause ─────

async def test_generic_label_answers_are_skipped_as_their_own_cause(db, respx_router, caplog):
    _seed_candidate(db, "Smith, Alice", "REP", "NY", 21)
    _seed_candidate(db, "Jones, Bob", "DEM", "NY", 21)
    _mock(respx_router, US_REP)

    with caplog.at_level(logging.INFO, logger="app.elections.services.votehub"):
        await votehub.fetch_votehub_house_polls(db)

    assert db.query(HousePoll).filter(HousePoll.poll_id == "votehub-ny21-monmouth-2026-06").count() == 0
    summary = next(r.getMessage() for r in caplog.records if "summary" in r.getMessage())
    assert "skipped_generic_label=1" in summary


# ── AC-9: the skip rate is observable in one aggregate summary line ────────────

async def test_run_summary_reports_every_stage(db, respx_router, caplog):
    payload = [
        {"id": "bad-seat-1", "seat_name": None, "answers": [
            {"choice": "A", "pct": 1.0}, {"choice": "B", "pct": 2.0},
        ]},
        {"id": "too-few-1", "seat_name": "CO-03", "answers": [{"choice": "Jeff Hurd", "pct": 1.0}]},
        {"id": "resolves-1", "seat_name": "CO-03", "answers": [
            {"choice": "Jeff Hurd", "pct": 48.0}, {"choice": "Adam Frisch", "pct": 44.0},
        ]},
        {"id": "unresolved-1", "seat_name": "PA-08", "answers": [
            {"choice": "Rob Bresnahan", "pct": 46.0}, {"choice": "Paige Cognetti", "pct": 45.0},
        ]},
        {"id": "ambiguous-1", "seat_name": "OH-15", "answers": [
            {"choice": "John Smith", "pct": 45.0}, {"choice": "Pat Jones", "pct": 43.0},
        ]},
        {"id": "generic-1", "seat_name": "NY-21", "answers": [
            {"choice": "Rep", "pct": 48.0}, {"choice": "Dem", "pct": 45.0},
        ]},
    ]
    _seed_candidate(db, "Hurd, Jeffrey", "REP", "CO", 3)
    _seed_candidate(db, "Frisch, Adam", "DEM", "CO", 3)
    _seed_candidate(db, "Smith, John Robert", "DEM", "OH", 15)
    _seed_candidate(db, "Smith, John Michael", "REP", "OH", 15)
    _seed_candidate(db, "Jones, Pat", "REP", "OH", 15)
    _mock(respx_router, payload)

    with caplog.at_level(logging.INFO, logger="app.elections.services.votehub"):
        saved = await votehub.fetch_votehub_house_polls(db)
    assert saved == 1

    summary = next(r.getMessage() for r in caplog.records if "summary" in r.getMessage())
    assert "returned=6" in summary
    assert "bad_seat=1" in summary
    assert "too_few_answers=1" in summary
    assert "inserted=1" in summary
    assert "updated=0" in summary
    assert "skipped_unresolved=1" in summary
    assert "skipped_ambiguous=1" in summary
    assert "skipped_generic_label=1" in summary

    # Per-poll WARNINGs are additive, not replaced by the summary.
    warning_msgs = " ".join(
        r.getMessage() for r in caplog.records if r.levelno == logging.WARNING
    )
    assert "Rob Bresnahan" in warning_msgs

    # Second run: the resolvable poll updates in place rather than re-inserting.
    caplog.clear()
    with caplog.at_level(logging.INFO, logger="app.elections.services.votehub"):
        saved_again = await votehub.fetch_votehub_house_polls(db)
    assert saved_again == 0
    summary_again = next(r.getMessage() for r in caplog.records if "summary" in r.getMessage())
    assert "inserted=0" in summary_again
    assert "updated=1" in summary_again


# ── AC-10: null seat_name / <2 answers are still skipped, unrecovered ──────────

async def test_null_seat_name_and_too_few_answers_are_skipped(db, respx_router, caplog):
    payload = [
        {"id": "bad-seat-2", "seat_name": None, "answers": [
            {"choice": "A", "pct": 1.0}, {"choice": "B", "pct": 2.0},
        ]},
        {"id": "too-few-2", "seat_name": "CO-03", "answers": [{"choice": "Jeff Hurd", "pct": 1.0}]},
    ]
    _mock(respx_router, payload)

    with caplog.at_level(logging.WARNING, logger="app.elections.services.votehub"):
        saved = await votehub.fetch_votehub_house_polls(db)

    assert saved == 0
    assert db.query(HousePoll).count() == 0


# ── AC-11: re-runs are idempotent, including for newly-resolvable polls ────────

async def test_rerun_is_idempotent_including_newly_resolvable_polls(db, respx_router):
    _seed_candidate(db, "Van Orden, Derrick", "REP", "WI", 3)
    _seed_candidate(db, "Cooke, Rebecca", "DEM", "WI", 3)
    _mock(respx_router, US_REP)

    saved_1 = await votehub.fetch_votehub_house_polls(db)
    assert saved_1 >= 1
    row = db.query(HousePoll).filter(HousePoll.poll_id == "votehub-wi03-marquette-2026-07").one()
    assert row.rep == 50.0 and row.dem == 46.0

    saved_2 = await votehub.fetch_votehub_house_polls(db)
    assert saved_2 == 0   # no new inserts on the second run
    assert db.query(HousePoll).filter(
        HousePoll.poll_id == "votehub-wi03-marquette-2026-07"
    ).count() == 1


# ── AC-10 (district-poll-scraper-fix): VoteHub and Wikipedia rows coexist ──────

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


# ── AC-13: a total upstream failure on this path does not starve the other ─────

async def test_upstream_failure_does_not_block_approval_generic_ballot(db, respx_router):
    respx_router.get(votehub.VOTEHUB_URL, params={"poll_type": "us-representative"}).mock(
        return_value=httpx.Response(500)
    )
    respx_router.get(votehub.VOTEHUB_URL, params={
        "poll_type": "approval", "subject": "donald-trump",
    }).mock(return_value=httpx.Response(200, json=[{
        "id": "approval-1", "start_date": "2026-06-01", "end_date": "2026-06-03",
        "sample_size": 800, "answers": [
            {"choice": "approve", "pct": 42.0}, {"choice": "disapprove", "pct": 55.0},
        ],
    }]))
    respx_router.get(votehub.VOTEHUB_URL, params={"poll_type": "generic-ballot"}).mock(
        return_value=httpx.Response(200, json=[])
    )

    house_saved = await votehub.fetch_votehub_house_polls(db)
    counts = await votehub.fetch_votehub_polls(db)

    assert house_saved == 0
    assert counts["approval"] == 1
