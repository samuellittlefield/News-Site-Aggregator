"""Model package split (elections-seam T1, AC-3 / TC-4, TC-5; AC-4 / TC-6, TC-7).

TC-5 is the ticket's most likely failure mode: three modules each calling
`declarative_base()` independently would still pass TC-4 (right classes, right
counts) and only fail here, at the "is it actually the same object" check. One
`Base` means one `MetaData`, which is what Alembic diffs against the database.

TC-7 guards the other landmine: `alembic/env.py` does
`from app.models import Base` to build `target_metadata`. If `__init__.py`'s
re-export forgot `Base` while still re-exporting all 25 classes, TC-6 would
stay green and every migration would break — a one-line failure `models`-only
tests wouldn't catch.
"""
from app.models import base, elections, monitor, shared
import app.models as models_pkg

ELECTIONS_CLASSES = [
    "Candidate", "CandidateIssueTag", "HousePoll", "CompetitiveDistrict",
    "HouseRetirement", "EconYouGovReport", "EconYouGovCrosstab", "VoteHubPoll",
    "PredictionMarket", "MarketSnapshot", "GenericBallotAggregate",
]
MONITOR_CLASSES = [
    "TrendCluster", "Trend", "Article", "Summary", "TrendSnapshot", "WikiPage",
    "WikiPageView", "NewsArticle", "RegionalWeather", "Earthquake", "NWSAlert",
    "ClimateEvent",
]
SHARED_CLASSES = ["ServiceStatus", "SourceRun"]


# ── TC-4 ─────────────────────────────────────────────────────────────────────

def test_classes_distributed_correctly():
    assert len(ELECTIONS_CLASSES) == 11
    assert len(MONITOR_CLASSES) == 12
    assert len(SHARED_CLASSES) == 2
    assert len(ELECTIONS_CLASSES) + len(MONITOR_CLASSES) + len(SHARED_CLASSES) == 25

    for name in ELECTIONS_CLASSES:
        assert hasattr(elections, name), f"{name} missing from app.models.elections"
    for name in MONITOR_CLASSES:
        assert hasattr(monitor, name), f"{name} missing from app.models.monitor"
    for name in SHARED_CLASSES:
        assert hasattr(shared, name), f"{name} missing from app.models.shared"


# ── TC-5 ─────────────────────────────────────────────────────────────────────

def test_exactly_one_base():
    assert elections.Base is monitor.Base is shared.Base is base.Base
    assert len(base.Base.metadata.tables) == 25


# ── TC-6 ─────────────────────────────────────────────────────────────────────

def test_model_imports_resolve_from_package():
    for name in ELECTIONS_CLASSES:
        assert getattr(models_pkg, name) is getattr(elections, name)
    for name in MONITOR_CLASSES:
        assert getattr(models_pkg, name) is getattr(monitor, name)
    for name in SHARED_CLASSES:
        assert getattr(models_pkg, name) is getattr(shared, name)


# ── TC-7 ─────────────────────────────────────────────────────────────────────

def test_base_resolves_from_package():
    from app.models import Base
    assert Base is base.Base
