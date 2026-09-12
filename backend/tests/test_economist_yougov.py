"""Economist/YouGov report discovery (economist-discovery-fix).

Reproduces the 2026-09-11 incident: `fetch_pdf_links` was parsing Wikipedia's
"Opinion polling on the second Trump presidency" page correctly the whole
time — the regex/table logic wasn't broken like the district scraper's was
(PR #8). The page's citation tables had simply gone stale (46 days with no new
Economist/YouGov row added, confirmed live: the July 2026 monthly table is the
newest one on the page, with no August/September section at all), while YouGov
kept publishing to the same CloudFront host. `economist_yougov_approval_page.wikitext`
is a trimmed real capture of that stale structure.

The fix adds VoteHub — which ingests Economist/YouGov polls independently —
as a second discovery source (mirroring PR #8's VoteHub-as-second-source
pattern), and makes "discovery found nothing at all" a loud SourceRun failure
instead of a silent success with item_count: 0.

respx (autouse guard in conftest) mocks Wikipedia; the `db` fixture rolls back.
"""
import pathlib
from datetime import datetime, timezone

import httpx
import pytest

from app import scheduler
from app.models import EconYouGovCrosstab, EconYouGovReport, SourceRun, VoteHubPoll
from app.elections.services import economist_yougov

FIX = pathlib.Path(__file__).parent / "fixtures"
APPROVAL_PAGE = (FIX / "economist_yougov_approval_page.wikitext").read_text()

CLOUDFRONT = "https://d3nkl3psvxxpe9.cloudfront.net/documents/"


def _wiki_response(wikitext: str) -> httpx.Response:
    return httpx.Response(200, json={"parse": {"wikitext": {"*": wikitext}}})


def _seed_votehub(db, votehub_id, pollster, url, end_date):
    db.add(VoteHubPoll(
        votehub_id=votehub_id, poll_type="generic-ballot", pollster=pollster,
        sponsors=["The Economist"], answers=[], url=url, end_date=end_date,
    ))
    db.flush()


# ── Parse against the current (stale) page structure ────────────────────────

async def test_fetch_pdf_links_parses_current_page_structure(respx_router):
    """The Wikipedia-side regex still works correctly against today's real
    markup: three distinct cloudfront reports, newest first, fragment suffixes
    (`#page=22`) stripped, duplicate citations deduped, and non-cloudfront
    Economist/YouGov links (documentcloud, yougov.net) correctly excluded since
    they aren't reports our parser knows how to fetch from this host."""
    respx_router.get(economist_yougov.WIKI_API).mock(return_value=_wiki_response(APPROVAL_PAGE))

    links = await economist_yougov.fetch_pdf_links()

    assert links == [
        CLOUDFRONT + "econTabReport_0t0YpHo.pdf",
        CLOUDFRONT + "econTabReport_AvLU7vY.pdf",
        CLOUDFRONT + "econTabReport_i4K4elJ.pdf",
    ]


# ── VoteHub as a second discovery source ────────────────────────────────────

def test_votehub_pdf_links_filters_pollster_and_strips_fragment(db):
    """Only YouGov-pollster rows count (case-insensitive), non-cloudfront urls
    (a different YouGov CDN) are excluded since discovery only knows how to
    fetch from this host, and results come back newest-fieldwork-first."""
    _seed_votehub(db, "v1", "YouGov", CLOUDFRONT + "econTabReport_SlcWdVd.pdf",
                  datetime(2026, 9, 8, tzinfo=timezone.utc))
    _seed_votehub(db, "v2", "yougov", CLOUDFRONT + "econTabReport_Older.pdf#page=4",
                  datetime(2026, 6, 1, tzinfo=timezone.utc))
    _seed_votehub(db, "v3", "YouGov",
                  "https://ygo-assets-websites-editorial-emea.yougov.net/documents/other.pdf",
                  datetime(2026, 8, 1, tzinfo=timezone.utc))
    _seed_votehub(db, "v4", "Ipsos", CLOUDFRONT + "econTabReport_NotYouGov.pdf",
                  datetime(2026, 9, 1, tzinfo=timezone.utc))

    links = economist_yougov._votehub_pdf_links(db)

    assert links == [
        CLOUDFRONT + "econTabReport_SlcWdVd.pdf",   # newest, fragment n/a
        CLOUDFRONT + "econTabReport_Older.pdf",       # fragment stripped
    ]


async def test_refresh_discovers_report_only_known_to_votehub(db, respx_router, monkeypatch):
    """Reproduces the actual incident: Wikipedia only cites the old July report
    (already stored), so its own discovery contributes zero new candidates —
    but VoteHub already carries the September report on the same CloudFront
    host, and the merged discovery step finds and processes it."""
    old_url = CLOUDFRONT + "econTabReport_0t0YpHo.pdf"
    old = EconYouGovReport(source_url=old_url, title="Old report")
    db.add(old)
    db.flush()
    db.add(EconYouGovCrosstab(
        report_id=old.id, question_code="23", question_key="trump_approval",
        question_title="President Trump Job Approval", question_text="Do you approve",
        blocks=[], topline={},
    ))
    db.flush()

    respx_router.get(economist_yougov.WIKI_API).mock(return_value=_wiki_response(
        f"| [{old_url} The Economist/YouGov]\n| July 25-27"
    ))

    new_url = CLOUDFRONT + "econTabReport_SlcWdVd.pdf"
    _seed_votehub(db, "v1", "YouGov", new_url, datetime(2026, 9, 8, tzinfo=timezone.utc))

    processed = []

    async def _fake_process_report(url, _db):
        processed.append(url)
        return 3

    monkeypatch.setattr(economist_yougov, "_process_report", _fake_process_report)

    result = await economist_yougov.refresh_economist_yougov(db)

    assert processed == [new_url]
    assert result["new_reports"] == 1


# ── Zero candidates is a loud failure, not success/item_count:0 ────────────

async def test_refresh_raises_when_both_sources_return_nothing(db, respx_router):
    """If Wikipedia and VoteHub both come up empty, discovery itself is broken
    (not just a quiet week between reports), so the service must raise rather
    than return a hollow {"new_reports": 0, ...} the caller would record as
    success."""
    respx_router.get(economist_yougov.WIKI_API).mock(
        return_value=_wiki_response("no polling tables on this page revision")
    )
    # No VoteHubPoll rows seeded: the second discovery source is empty too.

    with pytest.raises(RuntimeError, match="zero candidate report URLs"):
        await economist_yougov.refresh_economist_yougov(db)


async def test_zero_discovery_records_sourcerun_failure_not_success(db, respx_router, monkeypatch):
    """End-to-end through the scheduler wrapper: zero candidates must land as a
    `failure` SourceRun row, never `success` with item_count 0 — that's the
    exact masking that let this go undetected for 46 days in prod."""
    monkeypatch.setattr(scheduler, "SessionLocal", lambda: db)
    monkeypatch.setattr(db, "close", lambda: None)
    respx_router.get(economist_yougov.WIKI_API).mock(
        return_value=_wiki_response("no polling tables on this page revision")
    )

    await scheduler.refresh_economist()

    row = db.query(SourceRun).filter(SourceRun.source_id == "economist_job").one()
    assert row.status == "failure"
    assert row.item_count is None
    assert "zero candidate report URLs" in (row.error_message or "")
