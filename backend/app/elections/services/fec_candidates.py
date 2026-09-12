"""
FEC Candidates Service — 2026 cycle.

Fetches House and Senate candidates from the FEC API, primary election
dates, and seeds Governor races from a hardcoded list with Wikipedia scanning.

Requires FEC_API_KEY in .env (free at https://api.data.gov/signup/).
Falls back to DEMO_KEY (rate-limited to 40/hr) if not set.
"""
import asyncio
import logging
import os
import re
from datetime import date, datetime, timezone
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from app.models import Candidate, CompetitiveDistrict

logger = logging.getLogger(__name__)

FEC_BASE = "https://api.open.fec.gov/v1"
WIKI_API = "https://en.wikipedia.org/w/api.php"
HEADERS = {"User-Agent": "SituationMonitor/1.0 (contact@samuellittlefield.com)"}


def _fec_key() -> str:
    return os.getenv("FEC_API_KEY", "DEMO_KEY")


# ── 2026 Governor races (state-level, not in FEC) ─────────────────────────────
# Source: NCSL / Ballotpedia publicly reported list
GOVERNOR_STATES_2026 = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "FL", "GA", "HI",
    "ID", "IL", "IA", "KS", "ME", "MD", "MA", "MI", "MN", "NE",
    "NV", "NH", "NJ", "NM", "NY", "OH", "OK", "OR", "PA", "RI",
    "SC", "SD", "TN", "TX", "VT", "WI",
]

# Primary dates for governor races by state (2026)
GOVERNOR_PRIMARY_DATES: dict[str, str] = {
    "AL": "2026-06-02", "AK": "2026-08-25", "AZ": "2026-08-04",
    "AR": "2026-03-03", "CA": "2026-06-02", "CO": "2026-06-30",
    "CT": "2026-08-11", "FL": "2026-08-18", "GA": "2026-05-19",
    "HI": "2026-08-08", "ID": "2026-05-19", "IL": "2026-03-17",
    "IA": "2026-06-02", "KS": "2026-08-04", "ME": "2026-06-09",
    "MD": "2026-07-21", "MA": "2026-09-15", "MI": "2026-08-04",
    "MN": "2026-08-11", "NE": "2026-05-12", "NV": "2026-06-09",
    "NH": "2026-09-08", "NJ": "2026-06-02", "NM": "2026-06-02",
    "NY": "2026-06-23", "OH": "2026-05-05", "OK": "2026-06-23",
    "OR": "2026-05-19", "PA": "2026-05-19", "RI": "2026-09-08",
    "SC": "2026-06-09", "SD": "2026-06-02", "TN": "2026-08-06",
    "TX": "2026-03-03", "VT": "2026-08-11", "WI": "2026-08-04",
}


# ── FEC API helpers ───────────────────────────────────────────────────────────

async def _fec_paginate(client: httpx.AsyncClient, endpoint: str, params: dict,
                        max_retries: int = 4) -> list[dict]:
    """Paginate through FEC API results, resilient to transient failures.

    The /totals/ endpoint is slow and intermittently times out from cloud hosts;
    a single hiccup must NOT abandon the remaining pages (that previously left
    fundraising almost entirely unpopulated). Each page is retried with backoff;
    only a hard error (e.g. an invalid key → 4xx) stops the whole fetch."""
    results: list = []
    page = 1
    params = {**params, "api_key": _fec_key(), "per_page": 100, "page": page}
    while True:
        data = None
        for attempt in range(1, max_retries + 1):
            try:
                resp = await client.get(f"{FEC_BASE}{endpoint}", params=params)
                if resp.status_code == 429:
                    logger.warning("FEC rate limit (429) on page %d, attempt %d/%d",
                                   page, attempt, max_retries)
                    await asyncio.sleep(2 * attempt)
                    continue
                if resp.status_code != 200:
                    # Hard error (bad key, bad request) — retrying won't help.
                    logger.warning("FEC API error %s on page %d: %s",
                                   resp.status_code, page, resp.text[:200])
                    return results
                data = resp.json()
                break
            except Exception as e:  # noqa: BLE001 — timeouts etc.; %r so empty-message excs still show
                logger.warning("FEC request failed on page %d, attempt %d/%d: %r",
                               page, attempt, max_retries, e)
                await asyncio.sleep(1.5 * attempt)
        if data is None:
            logger.warning("FEC: giving up on page %d after %d attempts (%d rows so far)",
                           page, max_retries, len(results))
            break
        results.extend(data.get("results", []))
        pagination = data.get("pagination", {})
        if page >= pagination.get("pages", 1):
            break
        page += 1
        params["page"] = page
    return results


async def fetch_candidate_totals(client: httpx.AsyncClient, office: str) -> dict:
    """{candidate_id: total receipts} for the 2026 cycle (full-election aggregate).
    Used to populate candidate fundraising — a viability/quality signal."""
    # Sort by receipts desc so that if pagination is ever cut short (rate limit,
    # timeout), we still capture the highest-funded candidates — the ones that
    # drive the matchup — rather than an arbitrary slice. (Previously unsorted,
    # which silently dropped multi-million-dollar frontrunners onto lost pages.)
    rows = await _fec_paginate(client, "/candidates/totals/", {
        "cycle": 2026, "office": office, "election_full": "true", "min_receipts": 1,
        "sort": "-receipts",
    })
    out: dict[str, float] = {}
    for r in rows:
        cid = r.get("candidate_id")
        if cid:
            out[cid] = float(r.get("receipts") or 0.0)
    return out


def _party_short(party_full: Optional[str]) -> str:
    if not party_full:
        return "OTH"
    mapping = {"DEMOCRATIC PARTY": "DEM", "REPUBLICAN PARTY": "REP",
               "INDEPENDENT": "IND", "LIBERTARIAN PARTY": "LIB",
               "GREEN PARTY": "GRN", "NO PARTY PREFERENCE": "NPP"}
    return mapping.get(party_full.upper(), party_full[:3].upper())


def _upsert_candidate(db: Session, fec_id: str, name: str, party: str, state: str,
                       district: Optional[int], office: str, incumbent: Optional[str],
                       primary_date: Optional[date], fundraising: Optional[float],
                       cook_rating: Optional[str] = None) -> Candidate:
    existing = db.query(Candidate).filter(Candidate.fec_id == fec_id).first() if fec_id else None
    if not existing and not fec_id:
        # For governors: match by name+state+office
        existing = db.query(Candidate).filter(
            Candidate.name == name,
            Candidate.state == state,
            Candidate.office == office,
        ).first()

    if existing:
        existing.name = name
        existing.party = party
        existing.fundraising_total = fundraising
        existing.fetched_at = datetime.now(timezone.utc)
        if primary_date:
            existing.primary_date = primary_date
        if cook_rating:
            existing.cook_rating = cook_rating
        return existing
    else:
        cand = Candidate(
            fec_id=fec_id or None,
            name=name.title(),
            party=party,
            state=state,
            district=district,
            office=office,
            incumbent_challenge=incumbent,
            primary_date=primary_date,
            primary_status="upcoming" if primary_date and primary_date >= date.today() else None,
            fundraising_total=fundraising,
            cook_rating=cook_rating,
        )
        db.add(cand)
        return cand


# ── Primary dates ─────────────────────────────────────────────────────────────

async def fetch_primary_dates(client: httpx.AsyncClient) -> dict[tuple, date]:
    """Returns {(state, office): primary_date} mapping."""
    rows = await _fec_paginate(client, "/election-dates/", {
        "election_year": 2026, "election_type_id": "P",
    })
    result: dict[tuple, date] = {}
    for r in rows:
        state = r.get("election_state", "").strip()
        office = r.get("office_sought", "").strip()
        dt_str = r.get("election_date", "")
        if state and office and dt_str:
            try:
                result[(state, office)] = date.fromisoformat(dt_str)
            except ValueError:
                pass
    return result


# ── House candidates ──────────────────────────────────────────────────────────

async def fetch_house_candidates(db: Session) -> int:
    competitive_keys = {
        (d.state, d.district)
        for d in db.query(CompetitiveDistrict).all()
    }

    async with httpx.AsyncClient(headers=HEADERS, timeout=60.0) as client:
        primary_map = await fetch_primary_dates(client)
        rows = await _fec_paginate(client, "/candidates/", {
            "election_year": 2026, "office": "H",
        })
        totals = await fetch_candidate_totals(client, "H")

    count = 0
    for row in rows:
        state = row.get("state", "")
        district_num = row.get("district_number")
        incumbent = row.get("incumbent_challenge", "")
        has_funds = row.get("has_raised_funds", False)

        # Filter: incumbents, competitive district, or raised funds
        if not (incumbent == "I" or (state, district_num) in competitive_keys or has_funds):
            continue

        primary_dt = primary_map.get((state, "H"))
        party = _party_short(row.get("party_full", row.get("party", "")))

        # Look up cook rating from CompetitiveDistrict
        cook = None
        dist = db.query(CompetitiveDistrict).filter(
            CompetitiveDistrict.state == state,
            CompetitiveDistrict.district == district_num,
        ).first()
        if dist:
            cook = dist.cook_rating

        _upsert_candidate(
            db,
            fec_id=row.get("candidate_id", ""),
            name=row.get("name", "").title(),
            party=party,
            state=state,
            district=district_num,
            office="H",
            incumbent=incumbent,
            primary_date=primary_dt,
            fundraising=totals.get(row.get("candidate_id")),
            cook_rating=cook,
        )
        count += 1

    db.commit()
    logger.info("FEC House: upserted %d candidates", count)
    return count


# ── Senate candidates ─────────────────────────────────────────────────────────

async def fetch_senate_candidates(db: Session) -> int:
    async with httpx.AsyncClient(headers=HEADERS, timeout=60.0) as client:
        primary_map = await fetch_primary_dates(client)
        rows = await _fec_paginate(client, "/candidates/", {
            "election_year": 2026, "office": "S",
        })
        totals = await fetch_candidate_totals(client, "S")

    count = 0
    for row in rows:
        if not row.get("has_raised_funds") and row.get("incumbent_challenge") != "I":
            continue
        state = row.get("state", "")
        primary_dt = primary_map.get((state, "S"))
        party = _party_short(row.get("party_full", row.get("party", "")))

        _upsert_candidate(
            db,
            fec_id=row.get("candidate_id", ""),
            name=row.get("name", "").title(),
            party=party,
            state=state,
            district=None,
            office="S",
            incumbent=row.get("incumbent_challenge"),
            primary_date=primary_dt,
            fundraising=totals.get(row.get("candidate_id")),
        )
        count += 1

    db.commit()
    logger.info("FEC Senate: upserted %d candidates", count)
    return count


# ── Governor races ────────────────────────────────────────────────────────────

async def seed_governor_races(db: Session) -> int:
    """Seed governor candidates from Wikipedia pages."""
    count = 0
    async with httpx.AsyncClient(headers=HEADERS, timeout=45.0) as client:
        for state in GOVERNOR_STATES_2026:
            primary_date_str = GOVERNOR_PRIMARY_DATES.get(state)
            primary_dt = date.fromisoformat(primary_date_str) if primary_date_str else None

            # Check Wikipedia for candidates
            page = f"2026_{state}_gubernatorial_election"
            try:
                resp = await client.get(WIKI_API, params={
                    "action": "parse", "page": page,
                    "prop": "wikitext", "format": "json",
                })
                wikitext = resp.json().get("parse", {}).get("wikitext", {}).get("*", "")
            except Exception:
                wikitext = ""

            # Extract candidate names from wikitext (look for party + name patterns)
            dem_names = re.findall(r"\{\{(?:Party stripe|color)\|Democratic[^}]*\}\}[^\|]*\[\[([^\]|]+)", wikitext)
            rep_names = re.findall(r"\{\{(?:Party stripe|color)\|Republican[^}]*\}\}[^\|]*\[\[([^\]|]+)", wikitext)

            # If no structured data, just seed the race as "TBD"
            added_any = False
            for name in dem_names[:3]:
                _upsert_candidate(db, fec_id=None, name=name.strip(), party="DEM",
                                   state=state, district=None, office="G", incumbent=None,
                                   primary_date=primary_dt, fundraising=None)
                count += 1
                added_any = True

            for name in rep_names[:3]:
                _upsert_candidate(db, fec_id=None, name=name.strip(), party="REP",
                                   state=state, district=None, office="G", incumbent=None,
                                   primary_date=primary_dt, fundraising=None)
                count += 1
                added_any = True

            if not added_any:
                # Placeholder — marks that a governor race exists in this state
                _upsert_candidate(db, fec_id=None, name=f"TBD ({state} Governor)", party="",
                                   state=state, district=None, office="G", incumbent=None,
                                   primary_date=primary_dt, fundraising=None)
                count += 1

    db.commit()
    logger.info("Governor races seeded: %d entries across %d states", count, len(GOVERNOR_STATES_2026))
    return count


# ── Main refresh ──────────────────────────────────────────────────────────────

async def refresh_candidates(db: Session) -> dict:
    if _fec_key() == "DEMO_KEY":
        logger.warning("Using FEC DEMO_KEY — rate limited to 40/hr. Add FEC_API_KEY to .env.")

    house = await fetch_house_candidates(db)
    senate = await fetch_senate_candidates(db)
    gov = await seed_governor_races(db)
    return {"house": house, "senate": senate, "governors": gov}
