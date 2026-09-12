"""
VoteHub polls service.

Pulls individual polls from the free VoteHub API (https://votehub.com/polls/api/)
for Trump approval and the 2026 generic ballot, and computes recency-windowed
averages. The API returns full history (~1k polls per type) with no pagination,
so each refresh fetches everything and upserts by VoteHub id.
"""
import logging
import math
import re
import unicodedata
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from app.models import Candidate, HousePoll, VoteHubPoll

logger = logging.getLogger(__name__)

HEADERS = {"User-Agent": "SituationMonitor/1.0 (contact@samuellittlefield.com)"}
VOTEHUB_URL = "https://api.votehub.com/polls"

# poll_type → query params
POLL_QUERIES = {
    "approval": {"poll_type": "approval", "subject": "donald-trump"},
    "generic-ballot": {"poll_type": "generic-ballot"},
}

# Per-district polls live under a separate poll type. Handled by
# fetch_votehub_house_polls (writes to HousePoll), not the VoteHubPoll loop
# above, so approval/generic-ballot ingestion is entirely unaffected.
US_REP_QUERY = {"poll_type": "us-representative"}


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


# ── VoteHub district (us-representative) polls → HousePoll ────────────────────
#
# VoteHub gives per-district polls a structured `seat_name` ("AK-01") and an
# `answers` list of candidate names. Party is resolved by matching those names
# against the Candidate table — never from the poll's own `partisan` field,
# which is the *sponsor's* lean, not a candidate's party (AC-11).

_SEAT_RE = re.compile(r"^([A-Z]{2})-(\d{1,2}|AL)$")
_NAME_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v", "mr", "mrs", "ms", "dr"}

# States with a single, at-large House seat. FEC stores these candidates at
# district_number 0; VoteHub sends either "-AL" or, as seen live, "-01" for the
# same seat. Both must resolve to the same district (AC-7).
AT_LARGE_STATES = frozenset({"AK", "DE", "ND", "SD", "VT", "WY"})

# VoteHub polls whose answer choices are generic party labels rather than
# candidate names (e.g. "Rep" / "Dem") can never be resolved by name matching —
# distinguished from a name-matching failure so the AC-9 summary doesn't
# conflate the two (AC-8).
_GENERIC_LABELS = {"rep", "dem", "republican", "democrat"}


def _parse_seat(seat: Optional[str]) -> Optional[tuple[str, int]]:
    """'AK-01' → ('AK', 1); at-large 'AK-AL' → ('AK', 0). A state in
    AT_LARGE_STATES always resolves to district 0, regardless of whether
    VoteHub sent '-AL' or a numbered district. None if malformed."""
    if not seat:
        return None
    m = _SEAT_RE.match(seat.strip().upper())
    if not m:
        return None
    state, dpart = m.group(1), m.group(2)
    if state in AT_LARGE_STATES:
        return state, 0
    return state, (0 if dpart == "AL" else int(dpart))


def _is_generic_ballot_poll(answers: list) -> bool:
    choices = [str(a.get("choice", "")).strip().lower() for a in answers]
    return bool(choices) and all(c in _GENERIC_LABELS for c in choices)


def _fold(s: str) -> str:
    """Unicode NFD, drop combining marks, lowercase, punctuation → space. Only
    used for comparison — neither stored value nor the VoteHub answer is
    mutated (AC-3)."""
    nfd = unicodedata.normalize("NFD", s)
    stripped = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", stripped.lower())


def _tokens(name: str) -> list[str]:
    """Fold a name and split into tokens, dropping suffixes/honorifics."""
    return [t for t in _fold(name).split() if t and t not in _NAME_SUFFIXES]


def _fec_name_parts(name: str) -> tuple[list[str], list[str]]:
    """FEC stores 'Last, First Middle' → (surname_tokens, given_tokens), split
    on the first comma — the surname may itself be several tokens (AC-2b:
    'De La Cruz', 'Van Orden', 'Miller-Meeks', 'von Wilpert', ...). No comma
    present → fall back to treating the last token as the surname."""
    if "," in name:
        surname, given = name.split(",", 1)
        return _tokens(surname), _tokens(given)
    tokens = _tokens(name)
    if not tokens:
        return [], []
    return tokens[-1:], tokens[:-1]


def _district_candidates(db: Session, state: str, district: int) -> list[tuple[str, str]]:
    """(name, party) for that district's stored House candidates with a known
    party. Structured names are needed for the suffix/given-name matching
    rules below, which a pre-flattened key would throw away."""
    rows = db.query(Candidate).filter(
        Candidate.office == "H",
        Candidate.state == state,
        Candidate.district == district,
    ).all()
    return [(c.name, c.party) for c in rows if c.party]


def _resolve_candidate(name: str, candidates: list[tuple[str, str]]) -> tuple[Optional[str], str]:
    """Resolve a VoteHub answer-choice name against a district's candidates.

    A candidate is a *surname candidate* when the FEC surname's tokens form a
    contiguous suffix of the VoteHub name's tokens — never derived from just
    the VoteHub name's last token, which breaks every multi-token surname
    (AC-2b). It is additionally an *exact candidate* when the first given
    names also agree and at least one token precedes the surname suffix
    (AC-1, AC-2, AC-3).

    Resolves to the single exact candidate's party; more than one exact
    candidate is ambiguous. With no exact candidate, falls back to the single
    surname candidate (AC-4); zero or more than one is also ambiguous. Never
    guesses (AC-5) and never reads `partisan` (AC-6).

    Returns (party_or_None, cause) where cause is one of "matched",
    "unresolved", "ambiguous" — the cause feeds the AC-9 run summary.
    """
    vt = _tokens(name)
    exact: list[str] = []
    surname_only: list[str] = []
    for cand_name, party in candidates:
        sur, giv = _fec_name_parts(cand_name)
        if not sur or len(vt) < len(sur) or vt[-len(sur):] != sur:
            continue
        surname_only.append(party)
        if giv and len(vt) > len(sur) and vt[0] == giv[0]:
            exact.append(party)

    if exact:
        return (exact[0], "matched") if len(exact) == 1 else (None, "ambiguous")
    if len(surname_only) == 1:
        return surname_only[0], "matched"
    if len(surname_only) > 1:
        return None, "ambiguous"
    return None, "unresolved"


def _match_candidate_party(name: str, candidates: list[tuple[str, str]]) -> Optional[str]:
    """Resolve a VoteHub answer-choice name to a party. Returns None (never a
    guess) on zero or ambiguous matches (AC-5); `partisan` is never consulted
    here (AC-6)."""
    return _resolve_candidate(name, candidates)[0]


def _to_float(val) -> Optional[float]:
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


async def fetch_votehub_house_polls(db: Session) -> int:
    """Fetch VoteHub `us-representative` polls and upsert into HousePoll with
    source='votehub'. Skips (and logs) any poll whose dem/rep candidates can't be
    unambiguously resolved via the Candidate crosswalk. Logs one aggregate
    outcome summary per run (AC-9) in addition to the existing per-poll
    WARNINGs, so a high skip rate is visible without reading logs line by line."""
    now = datetime.now(timezone.utc)
    outcomes: Counter = Counter()
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=30.0) as client:
            resp = await client.get(VOTEHUB_URL, params=US_REP_QUERY)
        resp.raise_for_status()
        polls = resp.json()
    except httpx.RequestError as e:
        logger.warning("VoteHub request failed (us-representative): %s", e)
        return 0
    except httpx.HTTPStatusError as e:
        logger.warning("VoteHub HTTP error %s (us-representative)", e.response.status_code)
        return 0
    except ValueError as e:
        logger.warning("VoteHub returned non-JSON body (us-representative): %s", e)
        return 0

    if not isinstance(polls, list):
        logger.warning("VoteHub unexpected payload shape for us-representative")
        return 0

    outcomes["returned"] = len(polls)
    crosswalks: dict[tuple[str, int], list[tuple[str, str]]] = {}
    saved = 0
    for p in polls:
        vid = p.get("id")
        if not vid:
            continue
        seat = p.get("seat_name")
        parsed = _parse_seat(seat)
        if not parsed:
            logger.warning("VoteHub us-rep poll %s has unparseable seat_name %r; skipping", vid, seat)
            outcomes["bad_seat"] += 1
            continue
        state, district = parsed
        answers = p.get("answers") or []
        if len(answers) < 2:
            logger.warning("VoteHub us-rep poll %s (%s) has <2 answers; skipping", vid, seat)
            outcomes["too_few_answers"] += 1
            continue

        if _is_generic_ballot_poll(answers):
            logger.warning(
                "VoteHub us-rep poll %s (%s): answers are generic party labels, not "
                "candidate names; skipping", vid, seat,
            )
            outcomes["skipped_generic_label"] += 1
            continue

        key = (state, district)
        if key not in crosswalks:
            crosswalks[key] = _district_candidates(db, state, district)
        candidates = crosswalks[key]

        dem_val = rep_val = None
        unresolved: list[str] = []
        skip_cause = "unresolved"
        for ans in answers:
            choice = str(ans.get("choice", ""))
            party, cause = _resolve_candidate(choice, candidates)
            if party is None:
                unresolved.append(choice)
                if cause == "ambiguous":
                    skip_cause = "ambiguous"
                continue
            pct = _to_float(ans.get("pct"))
            if party.upper().startswith("D"):
                dem_val = pct
            elif party.upper().startswith("R"):
                rep_val = pct

        if dem_val is None or rep_val is None:
            logger.warning(
                "VoteHub us-rep poll %s (%s): could not resolve dem/rep candidates "
                "(unmatched: %s); skipping", vid, seat, ", ".join(unresolved) or "none",
            )
            outcomes[f"skipped_{skip_cause}"] += 1
            continue

        poll_id = f"votehub-{vid}"
        population = p.get("population")
        fields = dict(
            pollster=p.get("pollster") or "Unknown",
            state=state,
            district=district,
            start_date=_parse_date(p.get("start_date")),
            end_date=_parse_date(p.get("end_date")),
            sample_size=p.get("sample_size"),
            population=population[:4] if population else None,
            dem=dem_val,
            rep=rep_val,
            source_url=p.get("url"),
            source="votehub",
            fetched_at=now,
        )
        existing = db.query(HousePoll).filter(HousePoll.poll_id == poll_id).first()
        if existing:
            for field, value in fields.items():
                setattr(existing, field, value)
            outcomes["updated"] += 1
        else:
            db.add(HousePoll(poll_id=poll_id, **fields))
            saved += 1
            outcomes["inserted"] += 1

    db.commit()
    logger.info(
        "VoteHub us-representative summary: returned=%d bad_seat=%d too_few_answers=%d "
        "inserted=%d updated=%d skipped_unresolved=%d skipped_ambiguous=%d "
        "skipped_generic_label=%d",
        outcomes["returned"], outcomes["bad_seat"], outcomes["too_few_answers"],
        outcomes["inserted"], outcomes["updated"], outcomes["skipped_unresolved"],
        outcomes["skipped_ambiguous"], outcomes["skipped_generic_label"],
    )
    return saved


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

    # Provenance (poll-staleness-labels): the newest/oldest fieldwork date actually
    # inside the window this run averaged, not the newest/oldest in the whole table.
    # Additive only — see that ticket for why this function otherwise never changes.
    end_dates = [p.end_date for p in polls if p.end_date is not None]
    newest_fieldwork_end = max(end_dates) if end_dates else None
    oldest_fieldwork_end = min(end_dates) if end_dates else None

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
            "newest_fieldwork_end": newest_fieldwork_end,
            "oldest_fieldwork_end": oldest_fieldwork_end,
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
        "newest_fieldwork_end": newest_fieldwork_end,
        "oldest_fieldwork_end": oldest_fieldwork_end,
    }
