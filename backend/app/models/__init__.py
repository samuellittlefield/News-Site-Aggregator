"""Model package shim: re-exports `Base` and every model class so
`from app.models import HousePoll` (and `from app.models import Base`, which
`alembic/env.py` depends on for `target_metadata`) keep resolving unchanged
after the elections/monitor/shared split. See docs/features/elections-seam/.
"""
from app.models.base import Base

from app.models.elections import (
    Candidate,
    CandidateIssueTag,
    HousePoll,
    CompetitiveDistrict,
    HouseRetirement,
    EconYouGovReport,
    EconYouGovCrosstab,
    VoteHubPoll,
    PredictionMarket,
    MarketSnapshot,
    GenericBallotAggregate,
)
from app.models.monitor import (
    TrendCluster,
    Trend,
    Article,
    Summary,
    TrendSnapshot,
    WikiPage,
    WikiPageView,
    NewsArticle,
    RegionalWeather,
    Earthquake,
    NWSAlert,
    ClimateEvent,
)
from app.models.shared import (
    ServiceStatus,
    SourceRun,
)

__all__ = [
    "Base",
    # elections
    "Candidate",
    "CandidateIssueTag",
    "HousePoll",
    "CompetitiveDistrict",
    "HouseRetirement",
    "EconYouGovReport",
    "EconYouGovCrosstab",
    "VoteHubPoll",
    "PredictionMarket",
    "MarketSnapshot",
    "GenericBallotAggregate",
    # monitor
    "TrendCluster",
    "Trend",
    "Article",
    "Summary",
    "TrendSnapshot",
    "WikiPage",
    "WikiPageView",
    "NewsArticle",
    "RegionalWeather",
    "Earthquake",
    "NWSAlert",
    "ClimateEvent",
    # shared
    "ServiceStatus",
    "SourceRun",
]
