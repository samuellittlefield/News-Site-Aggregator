"""
VoteHub polls service.

Pulls individual polls from the free VoteHub API (https://votehub.com/polls/api/)
for Trump approval and the 2026 generic ballot, and computes recency-windowed
averages. The API returns full history (~1k polls per type) with no pagination,
so each refresh fetches everything and upserts by VoteHub id.
"""
import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from app.models import VoteHubPoll

logger = logging.getLogger(__name__)

HEADERS = {"User-Agent": "SituationMonitor/1.0 (contact@samuellittlefield.com)"}
VOTEHUB_URL = "https://api.votehub.com/polls"

# poll_type → query params
POLL_QUERIES = {
    "approval": {"poll_type": "approval", "subject": "donald-trump"},
    "generic-ballot": {"poll_type": "generic-ballot"},
}


def _parse_date(val: Optional[str]) -> Optional[datetime]:
    if not val:
        return None
    try:
        return datetime.fromisoformat(val).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _answer_pct(answers: list, *choices: str) -> Optional[float]:
    for ans in answers:
        if str(ans.get("choice", "")).lower() in choices:
            try:
                return float(ans.get("pct"))
            except (TypeError, ValueError):
                continue
    return None


async def fetch_votehub_polls(db: Session) -> dict:
    """Fetch all approval + generic-ballot polls and upsert. Returns counts per type."""
    now = datetime.now(timezone.utc)
    counts: dict[str, int] = {}

    for poll_type, params in POLL_QUERIES.items():
        try:
            async with httpx.AsyncClient(headers=HEADERS, timeout=30.0) as client:
                resp = await client.get(VOTEHUB_URL, params=params)
            resp.raise_for_status()
            polls = resp.json()
        except httpx.RequestError as e:
            logger.warning("VoteHub request failed (%s): %s", poll_type, e)
            continue
        except httpx.HTTPStatusError as e:
            logger.warning("VoteHub HTTP error %s (%s)", e.response.status_code, poll_type)
            continue
        except ValueError as e:
            logger.warning("VoteHub returned non-JSON body (%s): %s", poll_type, e)
            continue

        if not isinstance(polls, list):
            logger.warning("VoteHub unexpected payload shape for %s", poll_type)
            continue

        existing_ids = {
            row[0] for row in
            db.query(VoteHubPoll.votehub_id).filter(VoteHubPoll.poll_type == poll_type).all()
        }
        saved = 0
        for p in polls:
            vid = p.get("id")
            if not vid:
                continue
            answers = p.get("answers") or []
            fields = dict(
                poll_type=poll_type,
                subject=p.get("subject"),
                pollster=p.get("pollster"),
                sponsors=p.get("sponsors") or [],
                start_date=_parse_date(p.get("start_date")),
                end_date=_parse_date(p.get("end_date")),
                sample_size=p.get("sample_size"),
                population=p.get("population"),
                answers=answers,
                approve=_answer_pct(answers, "approve"),
                disapprove=_answer_pct(answers, "disapprove"),
                dem=_answer_pct(answers, "dem", "democrat"),
                rep=_answer_pct(answers, "rep", "republican"),
                url=p.get("url"),
                fetched_at=now,
            )
            if vid in existing_ids:
                db.query(VoteHubPoll).filter(VoteHubPoll.votehub_id == vid).update(fields)
            else:
                db.add(VoteHubPoll(votehub_id=vid, **fields))
            saved += 1
        db.commit()
        counts[poll_type] = saved
        logger.info("VoteHub %s: %d polls upserted", poll_type, saved)

    return counts


def compute_average(db: Session, poll_type: str, window_days: int = 21) -> Optional[dict]:
    """Sample-size-weighted mean over polls ending within the window."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    polls = (
        db.query(VoteHubPoll)
        .filter(VoteHubPoll.poll_type == poll_type, VoteHubPoll.end_date >= cutoff)
        .all()
    )
    if not polls:
        return None

    def weighted(field: str) -> Optional[float]:
        num, den = 0.0, 0.0
        for p in polls:
            val = getattr(p, field)
            if val is None:
                continue
            w = math.sqrt(p.sample_size) if p.sample_size else 1.0
            num += val * w
            den += w
        return round(num / den, 1) if den else None

    if poll_type == "approval":
        approve, disapprove = weighted("approve"), weighted("disapprove")
        if approve is None or disapprove is None:
            return None
        return {
            "approve": approve,
            "disapprove": disapprove,
            "net": round(approve - disapprove, 1),
            "n_polls": len(polls),
            "window_days": window_days,
        }

    dem, rep = weighted("dem"), weighted("rep")
    if dem is None or rep is None:
        return None
    return {
        "dem": dem,
        "rep": rep,
        "margin": round(dem - rep, 1),
        "n_polls": len(polls),
        "window_days": window_days,
    }
