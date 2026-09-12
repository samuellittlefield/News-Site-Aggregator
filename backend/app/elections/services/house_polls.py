"""
2026 House Polling service.

Two data streams:
1. Generic ballot aggregators — parsed from Wikipedia's 2026 House elections page.
2. District-level polls — scanned from per-district Wikipedia pages as they appear.

Also seeds the CompetitiveDistrict table with Cook Political Report 2026 ratings,
2024 actual results, and district centroids on first run.

Pollster grades loaded from the vendored FiveThirtyEight pollster-ratings CSV
(frozen at 2025-02-25 — 538's live feeds are dead), with the GitHub archive as fallback.
"""
import csv
import hashlib
import io
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from app.models import CompetitiveDistrict, GenericBallotAggregate, HousePoll

logger = logging.getLogger(__name__)

HEADERS = {"User-Agent": "SituationMonitor/1.0 (contact@samuellittlefield.com)"}

# ── Cook 2026 competitive districts ──────────────────────────────────────────
# Source: Cook Political Report publicly reported ratings + Census centroids + 2024 results
# Cook ratings: Toss-up / Lean D / Lean R / Likely D / Likely R
# margin_2024 = dem% - rep% (negative = R won)

COMPETITIVE_DISTRICTS = [
    # (state, district, cook_rating, dem_2024, rep_2024, margin_2024, lat, lng, incumbent_party)
    # --- Toss-up ---
    ("ME", 2,  "Toss-up",  46.3, 52.6,  -6.3,  44.80, -69.78, "D"),
    ("PA", 8,  "Toss-up",  49.2, 49.0,   0.2,  41.41, -75.65, "D"),
    ("PA", 7,  "Toss-up",  52.4, 46.2,   6.2,  40.75, -75.21, "D"),
    ("NY", 17, "Toss-up",  49.6, 50.4,  -0.8,  41.15, -74.00, "R"),
    ("NY", 22, "Toss-up",  48.8, 50.5,  -1.7,  43.05, -76.15, "R"),
    ("NY", 18, "Toss-up",  52.1, 47.9,   4.2,  41.93, -74.00, "D"),
    ("NY", 4,  "Toss-up",  49.8, 50.2,  -0.4,  40.72, -73.59, "R"),
    ("NJ", 7,  "Toss-up",  47.3, 52.7,  -5.4,  40.56, -74.61, "R"),
    ("NJ", 8,  "Toss-up",  52.9, 47.1,   5.8,  40.83, -74.22, "D"),
    ("WA", 3,  "Toss-up",  51.6, 48.4,   3.2,  45.67, -122.67,"D"),
    ("CO", 8,  "Toss-up",  50.8, 49.2,   1.6,  40.42, -104.71,"D"),
    ("AZ", 6,  "Toss-up",  52.3, 47.7,   4.6,  33.45, -111.90,"D"),
    ("OR", 5,  "Toss-up",  52.2, 47.8,   4.4,  44.90, -123.02,"D"),
    ("NH", 2,  "Toss-up",  56.1, 43.9,  12.2,  43.20, -71.54, "D"),
    ("MI", 8,  "Toss-up",  51.2, 48.8,   2.4,  42.73, -84.56, "D"),
    ("WI", 3,  "Toss-up",  51.4, 48.6,   2.8,  43.80, -91.24, "D"),
    ("CA", 13, "Toss-up",  50.6, 49.4,   1.2,  37.39, -120.73,"D"),
    ("CA", 47, "Toss-up",  51.4, 48.6,   2.8,  33.65, -117.90,"D"),
    ("CA", 45, "Toss-up",  48.7, 51.3,  -2.6,  33.73, -117.82,"R"),
    ("VA", 7,  "Toss-up",  53.2, 46.8,   6.4,  38.77, -77.49, "O"),
    # --- Lean D ---
    ("IL", 17, "Lean D",   51.9, 48.1,   3.8,  41.88, -89.68, "D"),
    ("WA", 8,  "Lean D",   57.3, 42.7,  14.6,  47.54, -122.00,"D"),
    ("CT", 5,  "Lean D",   56.6, 43.4,  13.2,  41.55, -73.04, "D"),
    ("MI", 7,  "Lean D",   55.5, 44.5,  11.0,  42.33, -83.05, "O"),
    ("AZ", 1,  "Lean D",   55.8, 44.2,  11.6,  34.57, -111.60,"D"),
    ("OH", 9,  "Lean D",   52.8, 47.2,   5.6,  41.66, -83.56, "D"),
    ("NM", 2,  "Lean D",   54.1, 45.9,   8.2,  33.40, -107.35,"D"),
    ("TX", 28, "Lean D",   55.3, 44.7,  10.6,  26.50, -99.13, "D"),
    ("NV", 3,  "Lean D",   51.7, 48.3,   3.4,  36.04, -115.06,"D"),
    ("NV", 1,  "Lean D",   61.1, 38.9,  22.2,  36.17, -115.14,"D"),
    ("MN", 2,  "Lean D",   51.3, 48.7,   2.6,  44.85, -93.47, "D"),
    ("OR", 4,  "Lean D",   58.7, 41.3,  17.4,  44.05, -123.09,"D"),
    # --- Lean R ---
    ("NY", 1,  "Lean R",   44.5, 55.5,  -11.0, 40.95, -72.62, "R"),
    ("NY", 3,  "Lean R",   46.2, 53.8,  -7.6,  40.87, -73.64, "R"),
    ("TX", 34, "Lean R",   44.8, 55.2,  -10.4, 26.21, -98.23, "R"),
    ("CA", 22, "Lean R",   44.2, 55.8,  -11.6, 36.33, -119.32,"R"),
    ("CA", 27, "Lean R",   45.9, 54.1,  -8.2,  34.50, -118.23,"R"),
    ("NE", 2,  "Lean R",   48.8, 51.2,  -2.4,  41.24, -96.03, "R"),
    ("IA", 3,  "Lean R",   45.1, 54.9,  -9.8,  41.59, -93.62, "R"),
    ("MT", 1,  "Lean R",   45.5, 54.5,  -9.0,  47.04, -114.04,"R"),
    ("AK", 1,  "Lean R",   43.2, 56.8,  -13.6, 64.20, -153.00,"R"),
    ("OH", 1,  "Lean R",   46.5, 53.5,  -7.0,  39.10, -84.51, "R"),
    # --- Likely D ---
    ("VA", 10, "Likely D", 57.7, 42.3,  15.4,  38.97, -77.47, "D"),
    ("VA", 2,  "Likely D", 54.6, 45.4,   9.2,  36.85, -76.29, "D"),
    ("FL", 9,  "Likely D", 60.2, 39.8,  20.4,  28.29, -81.44, "D"),
    ("FL", 10, "Likely D", 74.1, 25.9,  48.2,  28.56, -81.38, "D"),
    ("GA", 7,  "Likely D", 58.3, 41.7,  16.6,  33.87, -84.09, "D"),
    ("TX", 7,  "Likely D", 57.4, 42.6,  14.8,  29.75, -95.47, "D"),
    ("KS", 3,  "Likely D", 57.5, 42.5,  15.0,  38.88, -94.82, "D"),
    ("PA", 5,  "Likely D", 62.5, 37.5,  25.0,  39.95, -75.17, "D"),
    ("SC", 1,  "Likely D", 46.8, 53.2,  -6.4,  32.78, -79.94, "R"),
    # --- Likely R ---
    ("TX", 15, "Likely R", 44.7, 55.3,  -10.6, 26.50, -98.50, "R"),
    ("FL", 13, "Likely R", 44.2, 55.8,  -11.6, 27.97, -82.46, "R"),
    ("FL", 27, "Likely R", 44.9, 55.1,  -10.2, 25.70, -80.44, "R"),
    ("NC", 13, "Likely R", 47.2, 52.8,  -5.6,  35.92, -78.86, "R"),
    ("NC", 6,  "Likely R", 46.5, 53.5,  -7.0,  35.50, -80.85, "R"),
    ("NC", 1,  "Likely R", 45.8, 54.2,  -8.4,  36.12, -77.44, "R"),
    ("GA", 6,  "Likely R", 45.1, 54.9,  -9.8,  33.98, -84.52, "R"),
    ("IN", 1,  "Likely R", 47.7, 52.3,  -4.6,  41.59, -87.34, "R"),
    ("MI", 10, "Likely R", 45.6, 54.4,  -8.8,  42.97, -82.84, "R"),
]

# ── Pollster grade cache ──────────────────────────────────────────────────────
_POLLSTER_GRADES: dict[str, str] = {}
_GRADES_LOADED = False

GRADE_URL = "https://raw.githubusercontent.com/fivethirtyeight/data/master/pollster-ratings/pollster-ratings-combined.csv"
GRADE_CSV_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "pollster_ratings.csv"

NUMERIC_TO_LETTER = {
    3.0: "A+", 2.9: "A+", 2.8: "A", 2.7: "A", 2.6: "A-",
    2.5: "A-", 2.4: "B+", 2.3: "B+", 2.2: "B", 2.1: "B",
    2.0: "B-", 1.9: "B-", 1.8: "C+", 1.7: "C+", 1.6: "C",
    1.5: "C", 1.4: "C-", 1.3: "C-", 1.2: "D", 1.1: "D", 1.0: "D",
}


def _numeric_to_letter(score: float) -> str:
    rounded = round(score * 2) / 2
    return NUMERIC_TO_LETTER.get(rounded, "C")


def _parse_grades_csv(text: str) -> int:
    reader = csv.DictReader(io.StringIO(text))
    count = 0
    for row in reader:
        name = row.get("pollster", "").strip()
        score_str = row.get("numeric_grade", "")
        if name and score_str:
            try:
                _POLLSTER_GRADES[name.lower()] = _numeric_to_letter(float(score_str))
                count += 1
            except ValueError:
                pass
    return count


async def _load_pollster_grades() -> None:
    global _GRADES_LOADED
    if _GRADES_LOADED:
        return
    try:
        if GRADE_CSV_PATH.exists():
            _parse_grades_csv(GRADE_CSV_PATH.read_text())
            _GRADES_LOADED = True
            logger.info("Pollster grades loaded from vendored CSV: %d entries", len(_POLLSTER_GRADES))
            return
        async with httpx.AsyncClient(headers=HEADERS, timeout=10.0) as client:
            resp = await client.get(GRADE_URL)
        if resp.status_code != 200:
            return
        _parse_grades_csv(resp.text)
        _GRADES_LOADED = True
        logger.info("Pollster grades loaded from GitHub fallback: %d entries", len(_POLLSTER_GRADES))
    except Exception as e:
        logger.warning("Could not load pollster grades: %s", e)


def get_grade(pollster: str) -> Optional[str]:
    return _POLLSTER_GRADES.get(pollster.lower())


# ── District seeding ──────────────────────────────────────────────────────────

def seed_districts(db: Session) -> int:
    """Insert/update competitive districts from hardcoded Cook 2026 data."""
    count = 0
    for row in COMPETITIVE_DISTRICTS:
        state, district, cook, dem24, rep24, margin24, lat, lng, inc = row
        existing = db.query(CompetitiveDistrict).filter(
            CompetitiveDistrict.state == state,
            CompetitiveDistrict.district == district,
        ).first()
        if existing:
            existing.cook_rating = cook
            existing.dem_2024 = dem24
            existing.rep_2024 = rep24
            existing.margin_2024 = margin24
            existing.lat = lat
            existing.lng = lng
            existing.incumbent_party = inc
        else:
            db.add(CompetitiveDistrict(
                state=state, district=district, cook_rating=cook,
                dem_2024=dem24, rep_2024=rep24, margin_2024=margin24,
                lat=lat, lng=lng, incumbent_party=inc,
            ))
            count += 1
    db.commit()
    logger.info("District seed: %d new districts added", count)
    return count


# ── Generic ballot from Wikipedia ────────────────────────────────────────────

WIKI_API = "https://en.wikipedia.org/w/api.php"
HOUSE_2026_PAGE = "2026_United_States_House_of_Representatives_elections"


def _parse_pct(s: str) -> Optional[float]:
    s = s.strip().rstrip("%").replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def _parse_wiki_table(wikitext: str) -> list[dict]:
    """Parse a simple wikitable into list of row dicts."""
    rows = []
    headers: list[str] = []
    in_table = False
    for line in wikitext.split("\n"):
        line = line.strip()
        if line.startswith("{|"):
            in_table = True
            headers = []
            continue
        if line.startswith("|}"):
            in_table = False
            continue
        if not in_table:
            continue
        if line.startswith("!"):
            # Header row
            cells = re.split(r"!!|\|", line.lstrip("!"))
            headers = [re.sub(r"\{\{[^}]+\}\}|<[^>]+>|\[\[|\]\]", "", c).strip() for c in cells]
        elif line.startswith("|-"):
            rows.append({})
        elif line.startswith("|") and rows:
            cells = re.split(r"\|\|", line.lstrip("|"))
            for i, cell in enumerate(cells):
                cell_clean = re.sub(r"\{\{[^}]+\}\}|<[^>]+>|\[\[|\]\]|\|[^|]+=", "", cell).strip()
                if i < len(headers):
                    rows[-1][headers[i]] = cell_clean
    return [r for r in rows if r]


async def fetch_generic_ballot(db: Session) -> list[dict]:
    """Fetch generic ballot aggregator averages from Wikipedia."""
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=12.0) as client:
            resp = await client.get(WIKI_API, params={
                "action": "parse", "page": HOUSE_2026_PAGE,
                "section": "9", "prop": "wikitext", "format": "json",
            })
        data = resp.json()
        wikitext = data.get("parse", {}).get("wikitext", {}).get("*", "")
    except Exception as e:
        logger.warning("Wikipedia generic ballot fetch failed: %s", e)
        return []

    # The wikitext has one cell per line within each row (|-separated blocks).
    # Group lines between |- markers into rows, then extract source + percentages.
    results = []
    current_row: list[str] = []

    def _clean(s: str) -> str:
        s = re.sub(r"<ref[^>]*>.*?</ref>", "", s, flags=re.DOTALL)
        s = re.sub(r"\{\{[^}]+\}\}", "", s)   # remove templates {{...}}
        # In wikitext, a single | inside a cell separates attributes from content
        # e.g. "{{party shading/Democratic}} |'''48.4%'''" → keep only what's after |
        if "|" in s:
            s = s.split("|")[-1]
        s = re.sub(r"<[^>]+>", "", s)          # remove HTML tags
        s = re.sub(r"\[\[([^\]|]+\|)?([^\]]+)\]\]", r"\2", s)  # [[Link|Text]] -> Text
        s = re.sub(r"'''?|''+", "", s)          # remove bold/italic
        return s.strip()

    def _process_row(cells: list[str]) -> None:
        cleaned = [_clean(c) for c in cells]
        cleaned = [c for c in cleaned if c]
        if len(cleaned) < 3:
            return
        # Skip header, average, and total rows
        first = cleaned[0].lower()
        if any(x in first for x in ["source", "average", "colspan", "poll"]):
            return
        # Find % values
        pcts = []
        for c in cleaned:
            v = _parse_pct(c)
            if v is not None and 5 < v < 80:
                pcts.append(v)
        if len(pcts) < 2:
            return
        source = cleaned[0][:60]
        # pcts[0]=R%, pcts[1]=D% (column order in the table)
        results.append({"source": source, "rep": pcts[0], "dem": pcts[1]})

    for line in wikitext.split("\n"):
        line = line.strip()
        if line.startswith("{|") or line.startswith("|}") or line.startswith("!"):
            continue
        if line.startswith("|-"):
            if current_row:
                _process_row(current_row)
            current_row = []
        elif line.startswith("|"):
            # Each | starts a new cell; handle || inline splits too
            for cell in re.split(r"\|\|", line.lstrip("|")):
                current_row.append(cell)
    if current_row:
        _process_row(current_row)

    logger.info("Generic ballot: parsed %d aggregator rows", len(results))
    return results


# ── District polls from Wikipedia ────────────────────────────────────────────
#
# 2026 has no standalone per-district articles. Each state's races live on one
# consolidated page ("2026 United States House of Representatives elections in
# <State>") with a `District N → General election → Polling` subsection tree.
# We resolve that subsection by walking the page's section list and fetch only
# that subsection's wikitext. Critically, some districts (e.g. NY-17, NE-2) have
# a `Polling` subsection nested under a *primary* section instead — that's
# primary horse-race polling, not general-election data — so the lookup requires
# `Polling` to be a descendant of `General election` (AC-2b).

STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New_Hampshire", "NJ": "New_Jersey", "NM": "New_Mexico", "NY": "New_York",
    "NC": "North_Carolina", "ND": "North_Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode_Island", "SC": "South_Carolina",
    "SD": "South_Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West_Virginia",
    "WI": "Wisconsin", "WY": "Wyoming",
}

_PARTY_SUFFIX_RE = re.compile(r"\(([RDI])\)\s*$")

# The six single-district states. Their 2026 House page uses the singular
# "election" (not "elections") in its title — verified live 2026-09-12. This is
# deliberately an explicit set rather than a retry-on-404 fallback, so a genuine
# 404 on a multi-district state still surfaces as a warning (AC-8) instead of
# being masked by a second attempt. MT is *not* in this set: Montana regained a
# second seat in 2022 and MT-1 is a normal multi-district entry.
AT_LARGE_STATES = frozenset({"AK", "DE", "ND", "SD", "VT", "WY"})


def _state_wiki_page(state: str) -> str:
    """State abbreviation → the consolidated 2026 House elections page title."""
    state_name = STATE_NAMES.get(state, state)
    noun = "election" if state in AT_LARGE_STATES else "elections"
    return f"2026_United_States_House_of_Representatives_{noun}_in_{state_name}"


def _expand_templates(s: str) -> str:
    """Collapse {{template|...|value}} to its last parameter (or ''). Keeps the
    displayed value of wrappers like {{highlight|45%}} / {{nowrap|...}} while
    discarding styling templates like {{party color cell|Republican}} down to a
    harmless token."""
    prev = None
    while prev != s:
        prev = s
        s = re.sub(
            r"\{\{([^{}]*)\}\}",
            lambda m: m.group(1).split("|")[-1] if "|" in m.group(1) else "",
            s,
        )
    return s


def _clean_wiki(s: str) -> str:
    s = re.sub(r"<ref[^>]*>.*?</ref>", "", s, flags=re.DOTALL)
    s = re.sub(r"<ref[^>]*/?>", "", s)
    s = _expand_templates(s)
    s = re.sub(r"<br\s*/?>", " ", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"\[\[([^\]|]+\|)?([^\]]+)\]\]", r"\2", s)  # [[Link|Text]] -> Text
    s = re.sub(r"'''+|''", "", s)                          # bold / italic
    return s


def _cell_content(cell: str) -> str:
    """Clean a single table cell and drop any leading `attr | content` style
    prefix (a single `|` separates HTML attributes from cell content)."""
    s = _clean_wiki(cell)
    if "|" in s:
        s = s.rsplit("|", 1)[-1]
    return s.strip()


def _clean_heading(line: str) -> str:
    """Section `line` values from the API are HTML — strip to plain text."""
    return _clean_wiki(line).strip()


async def _fetch_state_sections(client: httpx.AsyncClient, state: str) -> list[dict]:
    """Fetch a state page's section list via action=parse&prop=sections.

    Returns [] and logs a warning on a non-200 status or a MediaWiki `error`
    body (e.g. missingtitle) — the exact failure the old code swallowed silently
    (AC-4)."""
    page = _state_wiki_page(state)
    try:
        resp = await client.get(WIKI_API, params={
            "action": "parse", "page": page,
            "prop": "sections", "format": "json",
        })
    except Exception as e:
        logger.warning("District polls: sections fetch failed for %s (%s): %s", state, page, e)
        return []
    if resp.status_code != 200:
        logger.warning("District polls: sections fetch for %s returned HTTP %s", state, resp.status_code)
        return []
    try:
        data = resp.json()
    except ValueError as e:
        logger.warning("District polls: non-JSON sections body for %s: %s", state, e)
        return []
    if "error" in data:
        code = data.get("error", {}).get("code", "unknown")
        logger.warning("District polls: Wikipedia error for %s (%s): %s", state, page, code)
        return []
    return data.get("parse", {}).get("sections", [])


_DISTRICT_RE = re.compile(r"^District\s+(\d+)\b", re.IGNORECASE)
_GENERAL_ELECTION_RE = re.compile(r"^General election\b", re.IGNORECASE)
_POLLING_RE = re.compile(r"^Polling\b", re.IGNORECASE)


def _general_election_polling_index(sections: list[dict], block_start: int, block_end: int) -> Optional[int]:
    """Within `sections[block_start:block_end]`, find a `General election →
    Polling` descendant and return its section index. This is the AC-2b guard:
    `Polling` must be a descendant of `General election`, not of a sibling
    primary section — so a primary's own Polling child (which can appear
    earlier in the document) is never returned."""
    n = len(sections)

    # Find `General election` within the block.
    ge_i = ge_level = None
    for i in range(block_start, block_end):
        if _GENERAL_ELECTION_RE.match(_clean_heading(sections[i].get("line", ""))):
            ge_i = i
            ge_level = sections[i].get("toclevel", 2)
            break
    if ge_i is None:
        return None

    # General-election descendants = up to the next heading at its level or
    # higher (this is what excludes a primary section's own Polling child).
    ge_end = block_end
    for i in range(ge_i + 1, block_end):
        if sections[i].get("toclevel", 1) <= ge_level:
            ge_end = i
            break

    # Find `Polling` strictly within General election's descendants.
    for i in range(ge_i + 1, ge_end):
        if _POLLING_RE.match(_clean_heading(sections[i].get("line", ""))):
            try:
                return int(sections[i].get("index"))
            except (TypeError, ValueError):
                return None
    return None


def _iter_polling_sections(sections: list[dict]):
    """Yield `(district, section_index)` for every `District N` heading whose
    block contains a `General election → Polling` descendant (AC-2, AC-2b/AC-3).

    If the page has no `District N` heading at all (an at-large state), look
    for a top-level `General election → Polling` and yield `(0, index)` instead
    (AC-5) — matching the at-large convention already used by `_cand_district`
    in `polls.py:30-32`.
    """
    n = len(sections)
    dist_positions: list[tuple[int, int, int]] = []  # (start_i, level, district)
    for i, sec in enumerate(sections):
        m = _DISTRICT_RE.match(_clean_heading(sec.get("line", "")))
        if m:
            dist_positions.append((i, sec.get("toclevel", 1), int(m.group(1))))

    if not dist_positions:
        # At-large page: no District N wrapper, so General election sits at
        # top level directly.
        idx = _general_election_polling_index(sections, 0, n)
        if idx is not None:
            yield (0, idx)
        return

    for pos, (dist_i, dist_level, district) in enumerate(dist_positions):
        block_end = n
        for i in range(dist_i + 1, n):
            if sections[i].get("toclevel", 1) <= dist_level:
                block_end = i
                break
        idx = _general_election_polling_index(sections, dist_i + 1, block_end)
        if idx is not None:
            yield (district, idx)


def _find_polling_section(sections: list[dict], district: int) -> Optional[int]:
    """Resolve `District {district} → General election → Polling` to a section
    index. Thin wrapper over `_iter_polling_sections` so this lookup and the
    enumeration can never disagree.

    Returns None (a normal skip, AC-7) if the district has no general-election
    Polling subsection yet — including the AC-2b case where only a *primary*
    section has a Polling child. Never returns a primary Polling section's index.
    """
    return dict(_iter_polling_sections(sections)).get(district)


async def _fetch_section_wikitext(client: httpx.AsyncClient, page: str, section_idx: int) -> str:
    """Fetch just one section's wikitext by index. Logs a warning on failure."""
    try:
        resp = await client.get(WIKI_API, params={
            "action": "parse", "page": page,
            "section": str(section_idx), "prop": "wikitext", "format": "json",
        })
        if resp.status_code != 200:
            logger.warning("District polls: section %s of %s returned HTTP %s", section_idx, page, resp.status_code)
            return ""
        data = resp.json()
        if "error" in data:
            logger.warning("District polls: Wikipedia error fetching section %s of %s", section_idx, page)
            return ""
        return data.get("parse", {}).get("wikitext", {}).get("*", "")
    except Exception as e:
        logger.warning("District polls: section %s fetch failed for %s: %s", section_idx, page, e)
        return ""


def _parse_section_table(wikitext: str) -> tuple[list[str], list[list[str]]]:
    """Parse the first wikitable in a section into (headers, rows-of-cells)."""
    headers: list[str] = []
    rows: list[list[str]] = []
    current: Optional[list[str]] = None
    in_table = False
    for raw in wikitext.split("\n"):
        line = raw.strip()
        if line.startswith("{|"):
            in_table = True
            continue
        if not in_table:
            continue
        if line.startswith("|}"):
            break  # end of first table
        if line.startswith("!"):
            for cell in re.split(r"!!|\|\|", line.lstrip("!")):
                headers.append(_cell_content(cell))
            continue
        if line.startswith("|-"):
            if current is not None:
                rows.append(current)
            current = []
            continue
        if line.startswith("|"):
            if current is None:
                current = []
            for cell in re.split(r"\|\|", line.lstrip("|")):
                current.append(_cell_content(cell))
            continue
    if current:
        rows.append(current)
    return headers, [r for r in rows if any(c for c in r)]


def _extract_polls_from_polling_section(wikitext: str, state: str, district: int) -> list[dict]:
    """Extract poll rows from a `Polling` subsection's wikitable.

    Candidate columns are keyed off a trailing `(R)`/`(D)`/`(I)` party suffix in
    the header cell (e.g. `Rob Bresnahan (R)`), not by substring-matching
    "democrat"/"republican" — real 2026 tables label columns with candidate
    names, which the old approach never matched."""
    polls: list[dict] = []
    headers, rows = _parse_section_table(wikitext)
    if not headers:
        return polls

    party_cols: dict[int, str] = {}
    pollster_col: Optional[int] = None
    date_col: Optional[int] = None
    for idx, h in enumerate(headers):
        m = _PARTY_SUFFIX_RE.search(h)
        if m:
            party_cols[idx] = m.group(1)
            continue
        hl = h.lower()
        if pollster_col is None and ("poll" in hl or "source" in hl or "firm" in hl):
            pollster_col = idx
        elif date_col is None and "date" in hl:
            date_col = idx
    if not party_cols:
        return polls
    if pollster_col is None:
        pollster_col = 0

    now = datetime.now(timezone.utc)
    for cells in rows:
        pollster = cells[pollster_col].strip() if pollster_col < len(cells) else ""
        if not pollster:
            continue
        dem_val = rep_val = ind_val = None
        for col, party in party_cols.items():
            if col >= len(cells):
                continue
            val = _parse_pct(cells[col])
            if val is None:
                continue
            if party == "D":
                dem_val = val
            elif party == "R":
                rep_val = val
            else:  # (I) — captured so the suffix approach generalizes; not stored on HousePoll
                ind_val = val
        if dem_val is None and rep_val is None:
            continue
        dates = cells[date_col].strip() if date_col is not None and date_col < len(cells) else ""
        uid = hashlib.md5(f"{state}{district}{pollster}{dates}{dem_val}{rep_val}".encode()).hexdigest()[:16]
        polls.append({
            "poll_id": f"wiki-{state}-{district}-{uid}",
            "pollster": pollster[:80],
            "grade": get_grade(pollster),
            "state": state,
            "district": district,
            "dem": dem_val,
            "rep": rep_val,
            "ind": ind_val,
            "end_date": _parse_wiki_date(dates) or now,
            "fetched_at": now,
        })
    return polls


_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}


def _parse_wiki_date(s: str) -> Optional[datetime]:
    """Best-effort end-date parse from strings like 'June 15–18, 2026'. Returns
    the last day mentioned; None if it can't be parsed (poll_id stays stable off
    the raw string, so this only affects the stored end_date)."""
    if not s:
        return None
    year_m = re.search(r"(20\d{2})", s)
    month_m = re.findall(r"[A-Za-z]+", s)
    day_m = re.findall(r"\d{1,2}", s)
    if not year_m or not day_m:
        return None
    months = [_MONTHS[w.lower()] for w in month_m if w.lower() in _MONTHS]
    if not months:
        return None
    year = int(year_m.group(1))
    # Days excluding the year digits; take the largest (end of a range).
    days = [int(d) for d in day_m if 1 <= int(d) <= 31 and d != str(year)]
    if not days:
        return None
    try:
        return datetime(year, months[-1], max(days), tzinfo=timezone.utc)
    except ValueError:
        return None


def _housepoll_from_extract(p: dict) -> HousePoll:
    """Build a HousePoll from an extracted poll dict, dropping non-column keys."""
    return HousePoll(
        poll_id=p["poll_id"],
        pollster=p["pollster"],
        grade=p.get("grade"),
        state=p["state"],
        district=p["district"],
        dem=p.get("dem"),
        rep=p.get("rep"),
        end_date=p.get("end_date"),
        source="wikipedia",
        fetched_at=p["fetched_at"],
    )


async def fetch_district_polls(db: Session) -> int:
    """Fetch district polls from each state's consolidated 2026 House page.

    The scrape list is derived from Wikipedia's own section tree, not from
    `CompetitiveDistrict` (AC-1): all 50 states are attempted, one sections call
    per state, and every district whose section tree has a `General election →
    Polling` descendant is scraped (AC-2). Each state is isolated: one state's
    failure never blocks the others (AC-8). If zero districts resolve a polling
    section across all 50 states, that's an upstream change, not a quiet
    success — raise so the scheduler records a SourceRun failure instead of
    success/item_count:0 (AC-9)."""
    await _load_pollster_grades()

    total = 0
    resolved = 0
    async with httpx.AsyncClient(headers=HEADERS, timeout=12.0) as client:
        for state in STATE_NAMES:
            try:
                sections = await _fetch_state_sections(client, state)
                if not sections:
                    continue
                page = _state_wiki_page(state)
                for district, section_idx in _iter_polling_sections(sections):
                    resolved += 1
                    wikitext = await _fetch_section_wikitext(client, page, section_idx)
                    if not wikitext:
                        continue
                    for p in _extract_polls_from_polling_section(wikitext, state, district):
                        existing = db.query(HousePoll).filter(HousePoll.poll_id == p["poll_id"]).first()
                        if not existing:
                            db.add(_housepoll_from_extract(p))
                            total += 1
            except Exception as e:
                logger.warning("District poll fetch failed for state %s: %s", state, e)

    db.commit()
    if resolved == 0:
        raise RuntimeError(
            "District polls: zero districts resolved a General election → Polling "
            "section across all 50 states — likely a Wikipedia heading-vocabulary "
            "change upstream"
        )
    logger.info("District polls: %d new polls added", total)
    return total


def _persist_generic_ballot(db: Session, rows: list[dict]) -> None:
    """Upsert aggregator rows into `GenericBallotAggregate` by `source`, giving
    the forecast model a DB-only fallback read path (forecast-model-swing-
    fallback-fix)."""
    for row in rows:
        if row.get("rep") is None or row.get("dem") is None:
            continue
        existing = (
            db.query(GenericBallotAggregate)
            .filter(GenericBallotAggregate.source == row["source"])
            .first()
        )
        if existing:
            existing.rep = row["rep"]
            existing.dem = row["dem"]
            existing.fetched_at = datetime.now(timezone.utc)
        else:
            db.add(GenericBallotAggregate(
                source=row["source"], rep=row["rep"], dem=row["dem"],
                fetched_at=datetime.now(timezone.utc),
            ))
    db.commit()


async def refresh_house_polls(db: Session) -> dict:
    """Full refresh: seed districts, fetch generic ballot, scan district polls."""
    seed_districts(db)
    generic = await fetch_generic_ballot(db)
    # Isolated in its own try/except so a persistence hiccup can't break the
    # district-poll refresh happening in the same job.
    try:
        _persist_generic_ballot(db, generic)
    except Exception:
        db.rollback()
        logger.exception("Generic ballot aggregate persistence failed")
    district_count = await fetch_district_polls(db)
    return {"generic_ballot": generic, "new_polls": district_count}
