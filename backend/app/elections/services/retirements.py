"""
House retirements service — 2026 cycle.

Scrapes the "Retirements" section of the Wikipedia "2026 United States House of
Representatives elections" article: a curated, structured list of every sitting
member NOT seeking re-election (retiring, or running for another office).

This is the signal FEC can't give us. FEC keeps a withdrawn member flagged as an
active candidate with the money they'd already raised (e.g. NY-21's Elise
Stefanik shows $4.96M and active_through=2026 despite not being on the ballot),
so the FEC "incumbent" flag can't tell us who's actually running. The retirements
list does — it's ~60 members, refreshed on a schedule.

Wikitext format (mirrors the governor-scan approach in fec_candidates.py — regex
over wikitext, no extra HTML-parsing deps):
    ===Republican===
    #{{ushr|NY|21|X}}: [[Elise Stefanik]] is retiring (previously ran for governor).
"""
import logging
import re

import httpx
from sqlalchemy.orm import Session

from app.models import HouseRetirement

logger = logging.getLogger(__name__)

WIKI_API = "https://en.wikipedia.org/w/api.php"
WIKI_PAGE = "2026 United States House of Representatives elections"
HEADERS = {"User-Agent": "SituationMonitor/1.0 (slittlefield8@gmail.com)"}

# #{{ushr|<ST>|<DIST>|...}}: [[<Member>(|display)]] <reason...>
_ROW = re.compile(r"\{\{ushr\|([A-Z]{2})\|([A-Za-z0-9]+)\|[^}]*\}\}\s*:\s*"
                  r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]\s*(.*)")


def _district_int(d: str) -> int:
    """At-large / delegate seats use 'AL' on Wikipedia; we key those as 0
    (matching how FEC/poll tables store at-large districts)."""
    return 0 if d.upper() == "AL" else int(d)


def _clean_reason(raw: str) -> str:
    """Trim to the human reason: cut at the first citation, then strip wiki markup."""
    raw = re.split(r"<ref|\{\{(?:cite|sfn|efn)", raw)[0]
    raw = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", raw)  # [[target|display]] -> display
    raw = re.sub(r"\[\[([^\]]+)\]\]", r"\1", raw)             # [[x]] -> x
    raw = raw.replace("''", "").strip().rstrip(".").strip()
    return raw


def parse_retirements(wikitext: str) -> list:
    """Parse the Retirements section into [{state, district, party, name, reason}]."""
    start = wikitext.find("==Retirements==")
    if start < 0:
        logger.warning("Retirements section not found in wikitext")
        return []
    rest = wikitext[start + 3:]
    end = re.search(r"\n==[^=]", rest)          # next top-level section
    section = rest[:end.start()] if end else rest

    party = None
    rows = []
    for line in section.splitlines():
        if re.match(r"===\s*Democratic", line):
            party = "D"
            continue
        if re.match(r"===\s*Republican", line):
            party = "R"
            continue
        m = _ROW.search(line)
        if not m:
            continue
        st, dist, name, reason = m.groups()
        try:
            district = _district_int(dist)
        except ValueError:
            continue
        rows.append({
            "state": st, "district": district, "party": party,
            "name": name.strip(), "reason": _clean_reason(reason),
        })
    return rows


async def fetch_retirements(client: httpx.AsyncClient) -> list:
    resp = await client.get(WIKI_API, params={
        "action": "parse", "page": WIKI_PAGE, "prop": "wikitext", "format": "json",
    })
    if resp.status_code != 200:
        logger.warning("Wikipedia parse failed: %s", resp.status_code)
        return []
    wikitext = resp.json().get("parse", {}).get("wikitext", {}).get("*", "")
    return parse_retirements(wikitext)


async def refresh_retirements(db: Session) -> int:
    """Replace the retirements table with the current Wikipedia list."""
    async with httpx.AsyncClient(headers=HEADERS, timeout=30.0, follow_redirects=True) as client:
        rows = await fetch_retirements(client)

    if not rows:
        logger.warning("No retirements parsed; leaving existing rows untouched")
        return 0

    # Full replace — the upstream list is the source of truth and small (~60 rows).
    db.query(HouseRetirement).delete()
    for r in rows:
        db.add(HouseRetirement(
            state=r["state"], district=r["district"], party=r["party"],
            member_name=r["name"], reason=r["reason"],
        ))
    db.commit()
    logger.info("Retirements: stored %d members not seeking re-election", len(rows))
    return len(rows)
