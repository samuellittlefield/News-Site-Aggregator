"""Generic-ballot aggregator persistence inside `refresh_house_polls`
(forecast-model-swing-fallback-fix).

TC-8: upserts by `source`, no duplicates across repeated runs (idempotency,
mirrors `test_kalshi_upsert.py`). TC-9: a persistence failure is isolated so it
can't break the district-poll refresh happening in the same job.
"""
import httpx

from app.models import GenericBallotAggregate
from app.services import house_polls

WIKITEXT = (
    "{|\n"
    "!Source\n!colspan=2|—\n"
    "|-\n"
    "| Aggregator A\n| {{party shading/Republican}} |'''44%'''\n"
    "| {{party shading/Democratic}} |'''48%'''\n"
    "|-\n"
    "| Aggregator B\n| {{party shading/Republican}} |'''45%'''\n"
    "| {{party shading/Democratic}} |'''50%'''\n"
    "|}"
)


def _mock_wiki(respx_router, wikitext=WIKITEXT):
    respx_router.get(house_polls.WIKI_API).mock(
        return_value=httpx.Response(200, json={"parse": {"wikitext": {"*": wikitext}}})
    )


# ── TC-8: upsert by source, no duplicates across repeated runs ─────────────

async def test_refresh_house_polls_persists_and_upserts_aggregate_rows(db, respx_router, monkeypatch):
    _mock_wiki(respx_router)
    # Keep this test focused on generic-ballot persistence: skip the (unrelated,
    # separately-tested) district-poll scan.
    monkeypatch.setattr(house_polls, "fetch_district_polls", _noop_district_polls)

    await house_polls.refresh_house_polls(db)
    rows = db.query(GenericBallotAggregate).order_by(GenericBallotAggregate.source).all()
    assert [r.source for r in rows] == ["Aggregator A", "Aggregator B"]
    assert rows[0].dem == 48.0 and rows[0].rep == 44.0

    # Re-run with the same upstream data → still exactly one row per source.
    await house_polls.refresh_house_polls(db)
    assert db.query(GenericBallotAggregate).count() == 2

    # Re-run with a changed value → row is overwritten, not duplicated.
    changed = WIKITEXT.replace("'''48%'''", "'''52%'''")
    _mock_wiki(respx_router, changed)
    await house_polls.refresh_house_polls(db)
    rows = db.query(GenericBallotAggregate).order_by(GenericBallotAggregate.source).all()
    assert [r.source for r in rows] == ["Aggregator A", "Aggregator B"]
    assert rows[0].dem == 52.0


# ── TC-9: persistence failure doesn't break district-poll refresh ──────────

async def test_persistence_failure_does_not_break_district_refresh(db, monkeypatch, caplog):
    import logging

    async def fake_generic_ballot(_db):
        return [{"source": "FakeAgg", "rep": 45.0, "dem": 50.0}]

    calls = {"district_polls_ran": False}

    async def fake_district_polls(_db):
        calls["district_polls_ran"] = True
        return 7

    def raising_persist(_db, _rows):
        raise RuntimeError("boom")

    monkeypatch.setattr(house_polls, "fetch_generic_ballot", fake_generic_ballot)
    monkeypatch.setattr(house_polls, "fetch_district_polls", fake_district_polls)
    monkeypatch.setattr(house_polls, "_persist_generic_ballot", raising_persist)

    with caplog.at_level(logging.ERROR, logger="app.services.house_polls"):
        result = await house_polls.refresh_house_polls(db)

    assert calls["district_polls_ran"] is True
    assert result["new_polls"] == 7
    assert result["generic_ballot"] == [{"source": "FakeAgg", "rep": 45.0, "dem": 50.0}]
    assert db.query(GenericBallotAggregate).count() == 0
    assert any("persist" in r.getMessage().lower() for r in caplog.records)


async def _noop_district_polls(_db):
    return 0
