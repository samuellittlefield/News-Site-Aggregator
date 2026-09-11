import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Trend, TrendSnapshot

logger = logging.getLogger(__name__)


def parse_traffic(s: Optional[str]) -> int:
    """Convert '2000+', '10K+', '1.5M+' to integers."""
    if not s:
        return 0
    s = s.strip().rstrip("+").upper()
    try:
        if s.endswith("M"):
            return int(float(s[:-1]) * 1_000_000)
        if s.endswith("K"):
            return int(float(s[:-1]) * 1_000)
        return int(s)
    except (ValueError, IndexError):
        return 0


def compute_velocity(trend: Trend, db: Session) -> None:
    """
    Compute velocity signals from the last two snapshots:

    - rank_velocity: how many positions the topic moved UP in the RSS feed
      (positive = rising, e.g. moved from rank 8 to rank 3 → rank_velocity = 5)
    - velocity_abs: raw traffic bucket delta (often 0 due to coarse bucketing)
    - velocity_pct: percentage change in traffic bucket

    The rank_velocity is the primary signal for "rising fast" — the RSS orders
    topics by momentum, so rank movement is the most meaningful change indicator.
    Caller must commit after this call.
    """
    from datetime import timedelta
    from sqlalchemy import func

    # "Current" = most recent snapshot
    current = (
        db.query(TrendSnapshot)
        .filter(TrendSnapshot.trend_id == trend.id)
        .order_by(TrendSnapshot.captured_at.desc())
        .first()
    )
    if current is None:
        trend.velocity_abs = 0
        trend.velocity_pct = 0
        trend.rank_velocity = 0
        return

    # "Previous" = most recent snapshot that is at least 2 hours older than current.
    # This makes velocity meaningful across real refresh cycles and ignores
    # rapid manual refreshes that produce no real change.
    cutoff = current.captured_at - timedelta(hours=2)
    previous = (
        db.query(TrendSnapshot)
        .filter(
            TrendSnapshot.trend_id == trend.id,
            TrendSnapshot.captured_at <= cutoff,
        )
        .order_by(TrendSnapshot.captured_at.desc())
        .first()
    )

    if previous is None:
        trend.velocity_abs = 0
        trend.velocity_pct = 0
        trend.rank_velocity = 0
        return

    # Rank velocity: positive means moved UP (lower rank number = higher position)
    if current.rank is not None and previous.rank is not None:
        trend.rank_velocity = previous.rank - current.rank
    else:
        trend.rank_velocity = 0

    # Traffic bucket delta (secondary signal)
    cur_traffic = parse_traffic(current.traffic_volume)
    prev_traffic = parse_traffic(previous.traffic_volume)
    trend.velocity_abs = cur_traffic - prev_traffic
    trend.velocity_pct = (
        int(((cur_traffic - prev_traffic) / prev_traffic) * 100)
        if prev_traffic > 0 else 0
    )

    if trend.rank_velocity != 0 or trend.velocity_abs != 0:
        logger.info(
            "Velocity for '%s': rank %+d, traffic %+d (%+d%%)",
            trend.title, trend.rank_velocity, trend.velocity_abs, trend.velocity_pct,
        )
