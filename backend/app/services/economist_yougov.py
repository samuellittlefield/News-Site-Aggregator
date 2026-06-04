"""
Economist/YouGov crosstab service.

Source: the Wikipedia page "Opinion polling on the second Trump presidency"
links ~20+ Economist/YouGov tab-report PDFs (hosted on cloudfront). Each PDF is
a ~69-page weekly poll with full demographic crosstabs.

We pull the distinct PDF links off that page, download any we haven't seen,
parse a configured set of recurring question tables (approval, direction of
country, …) into demographic crosstabs, and store them. Question NUMBERS shift
week to week, so we locate tables by normalized title, never by page number.

ToS-clean: these are public PDFs the campaign/press cite directly. No login,
no scraping of yougov.com itself.
"""
import io
import logging
import re
from datetime import date, datetime, timezone
from typing import Optional

import httpx
import pdfplumber
from sqlalchemy.orm import Session

from app.models import EconYouGovCrosstab, EconYouGovReport

logger = logging.getLogger(__name__)

HEADERS = {"User-Agent": "SituationMonitor/1.0 (contact@samuellittlefield.com)"}

WIKI_API = "https://en.wikipedia.org/w/api.php"
WIKI_PAGE = "Opinion polling on the second Trump presidency"
PDF_LINK_RE = re.compile(r"https://d3nkl3psvxxpe9\.cloudfront\.net/documents/\S+?\.pdf")

# Recurring tables we track. key -> list of normalized title substrings to match.
# Titles in the PDF have spaces stripped ("PresidentTrumpJobApproval"), so we
# match against a space-stripped, lowercased version of the heading (see
# _norm_title, which also drops punctuation).
TRACKED_QUESTIONS: dict[str, list[str]] = {
    "trump_approval":       ["presidenttrumpjobapproval"],
    "direction_of_country": ["directionofcountry"],
    "issue_economy":        ["jobsandtheeconomy"],
    "issue_inflation":      ["inflationprices"],
    "issue_immigration":    ["issueapprovalimmigration"],   # avoid SupportDetainingImmigrants etc.
    "vance_approval":       ["jdvancejobapproval", "vancejobapproval"],
    "congress_approval":    ["approvalofuscongress"],
    "scotus_approval":      ["supremecourtoftheunitedstates"],
}

# Human-readable labels — single source of truth, exposed via /api/economist/questions.
QUESTION_LABELS: dict[str, str] = {
    "trump_approval":       "President Trump Job Approval",
    "direction_of_country": "Direction of Country",
    "issue_economy":        "Issue: Jobs & the Economy",
    "issue_inflation":      "Issue: Inflation / Prices",
    "issue_immigration":    "Issue: Immigration",
    "vance_approval":       "JD Vance Job Approval",
    "congress_approval":    "U.S. Congress Approval",
    "scotus_approval":      "Supreme Court Approval",
}

# Display ordering for the frontend switcher (Core questions first).
QUESTION_ORDER: list[str] = list(QUESTION_LABELS.keys())

PCT_RE = re.compile(r"-?\d+%")
HEADING_RE = re.compile(r"^(\d+[A-Z]?)\.\s*(\S.*)$")
MONTHS = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"], start=1)}

MAX_REPORTS_PER_RUN = 6   # cap downloads per refresh; back-catalog fills over time


# ── Wikipedia link discovery ──────────────────────────────────────────────────

async def fetch_pdf_links() -> list[str]:
    async with httpx.AsyncClient(headers=HEADERS, timeout=20.0) as client:
        resp = await client.get(WIKI_API, params={
            "action": "parse", "page": WIKI_PAGE,
            "prop": "wikitext", "format": "json",
        })
    wikitext = resp.json().get("parse", {}).get("wikitext", {}).get("*", "")
    links = PDF_LINK_RE.findall(wikitext)
    # dedupe, preserve order (page lists newest first)
    return list(dict.fromkeys(links))


# ── Header / date parsing ─────────────────────────────────────────────────────

def _parse_header(text: str) -> dict:
    """Parse 'July 4 - 7, 2025 - 1528 U.S. Adult Citizens' style header."""
    out: dict = {"title": None, "start_date": None, "end_date": None,
                 "sample_size": None, "sample_desc": None}
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if lines:
        out["title"] = lines[0][:120]
    # Find the date/sample line — contains a 4-digit year and "- <N> <words>"
    for line in lines[1:4]:
        m = re.search(r"([A-Z][a-z]+ \d{1,2}.*?\d{4})\s*[-–]\s*([\d,]+)\s+(.*)", line)
        if m:
            out.update(_parse_date_range(m.group(1)))
            out["sample_size"] = int(m.group(2).replace(",", ""))
            out["sample_desc"] = m.group(3).strip()[:80]
            break
    return out


def _parse_date_range(s: str) -> dict:
    """'July 4 - 7, 2025' / 'December 30, 2025 - January 2, 2026' -> start/end."""
    s = s.replace("–", "-")
    years = [int(y) for y in re.findall(r"\d{4}", s)]
    # End year = last year shown; start year = first year shown (may differ at
    # a Dec->Jan rollover where both appear, e.g. "..., 2025 - ..., 2026").
    end_year = years[-1] if years else None
    start_year = years[0] if years else None
    # Strip the 4-digit years first so their digits aren't read as days.
    s = re.sub(r"\d{4}", "", s)
    # Collect (month, day) pairs in order
    pairs = re.findall(r"([A-Z][a-z]+)?\s*(\d{1,2})", s)
    start_d = end_d = None
    month_seen = None
    parsed = []
    for mon, day in pairs:
        if mon and mon in MONTHS:
            month_seen = MONTHS[mon]
        if month_seen and day and int(day) <= 31:
            parsed.append((month_seen, int(day)))
    try:
        if len(parsed) >= 2 and end_year:
            (m1, d1), (m2, d2) = parsed[0], parsed[-1]
            # If only one year was printed but the range crosses Dec->Jan,
            # the start falls in the prior year.
            y1 = start_year if len(years) >= 2 else (end_year - 1 if m1 > m2 else end_year)
            start_d = date(y1, m1, d1)
            end_d = date(end_year, m2, d2)
        elif len(parsed) == 1 and end_year:
            m1, d1 = parsed[0]
            start_d = end_d = date(end_year, m1, d1)
    except ValueError:
        pass
    return {"start_date": start_d, "end_date": end_d}


# ── Crosstab block parsing ────────────────────────────────────────────────────

def _parse_block(lines: list[str]) -> Optional[dict]:
    """Parse one demographic block (group line + 'Total ...' header + rows)."""
    col_idx = next((i for i, l in enumerate(lines)
                    if l.strip().startswith("Total ")), None)
    if col_idx is None:
        return None
    columns = lines[col_idx].split()
    group_line = lines[col_idx - 1].strip() if col_idx > 0 else ""
    rows: dict[str, list[int]] = {}
    ns: dict[str, int] = {}
    for l in lines[col_idx + 1:]:
        s = l.strip()
        if s.startswith("UnweightedN"):
            nums = re.findall(r"\(([\d,]+)\)", s)
            ns = {columns[i]: int(n.replace(",", ""))
                  for i, n in enumerate(nums) if i < len(columns)}
            continue
        if s.startswith("Totals"):
            continue
        pcts = PCT_RE.findall(s)
        if not pcts:
            continue
        label = s[:s.find(pcts[0])].strip()
        if label:
            rows[label] = [int(p.rstrip("%")) for p in pcts]
    if not rows:
        return None
    return {"group_line": group_line, "columns": columns, "rows": rows, "ns": ns}


def _norm_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]", "", title.lower())


def _extract_questions(pdf) -> dict[str, dict]:
    """Walk pages, group lines under the current numbered heading, and return
    {question_key: {code, title, text, blocks}} for tracked questions only."""
    # Build a flat list of (page_lines) and track headings spanning pages.
    found: dict[str, dict] = {}
    current = None   # dict being accumulated

    def flush():
        nonlocal current
        if not current:
            return
        norm = _norm_title(current["title"])
        for key, needles in TRACKED_QUESTIONS.items():
            if key in found:
                continue
            if any(n in norm for n in needles):
                blocks = []
                lines = current["lines"]
                hdr_idxs = [i for i, l in enumerate(lines)
                            if l.strip().startswith("Total ")]
                for j, h in enumerate(hdr_idxs):
                    end = hdr_idxs[j + 1] - 1 if j + 1 < len(hdr_idxs) else len(lines)
                    blk = _parse_block(lines[h - 1:end])
                    if blk:
                        blocks.append(blk)
                if blocks:
                    found[key] = {
                        "code": current["code"],
                        "title": current["title"],
                        "text": current["text"],
                        "blocks": blocks,
                    }
                break
        current = None

    for page in pdf.pages:
        text = page.extract_text() or ""
        lines = text.split("\n")
        # Skip the two-line poll header repeated on every page
        body = lines[2:] if len(lines) > 2 else lines
        i = 0
        while i < len(body):
            line = body[i]
            m = HEADING_RE.match(line.strip())
            if m:
                flush()
                # question prompt = next non-empty line
                text_line = ""
                for nxt in body[i + 1:i + 3]:
                    if nxt.strip() and not nxt.strip().startswith("Total "):
                        text_line = nxt.strip()
                        break
                current = {"code": m.group(1), "title": m.group(2).strip(),
                           "text": text_line, "lines": []}
            elif current is not None:
                current["lines"].append(line)
            i += 1
    flush()
    return found


# ── Topline convenience ───────────────────────────────────────────────────────

def _topline(blocks: list[dict]) -> dict:
    """Pull the Total column (index 0) for each row from the first block."""
    if not blocks:
        return {}
    blk = blocks[0]
    return {label: vals[0] for label, vals in blk["rows"].items() if vals}


# ── Main refresh ──────────────────────────────────────────────────────────────

async def _process_report(url: str, db: Session) -> int:
    async with httpx.AsyncClient(headers=HEADERS, timeout=40.0) as client:
        resp = await client.get(url)
    if resp.status_code != 200:
        logger.warning("Econ/YouGov PDF %s -> HTTP %d", url, resp.status_code)
        return 0
    try:
        pdf = pdfplumber.open(io.BytesIO(resp.content))
    except Exception as e:
        logger.warning("Could not open PDF %s: %s", url, e)
        return 0

    header = _parse_header(pdf.pages[0].extract_text() or "")
    questions = _extract_questions(pdf)
    if not questions:
        logger.info("Econ/YouGov %s: no tracked questions found", url[-24:])
        return 0

    report = EconYouGovReport(
        source_url=url,
        title=header["title"],
        start_date=header["start_date"],
        end_date=header["end_date"],
        sample_size=header["sample_size"],
        sample_desc=header["sample_desc"],
    )
    db.add(report)
    db.flush()  # assign report.id

    for key, q in questions.items():
        db.add(EconYouGovCrosstab(
            report_id=report.id,
            question_code=q["code"],
            question_key=key,
            question_title=q["title"],
            question_text=q["text"],
            blocks=q["blocks"],
            topline=_topline(q["blocks"]),
        ))
    db.commit()
    logger.info("Econ/YouGov %s (%s): %d questions stored",
                header.get("end_date"), url[-20:], len(questions))
    return len(questions)


async def refresh_economist_yougov(db: Session) -> dict:
    """Discover PDF links, download/parse any new reports, store crosstabs."""
    try:
        links = await fetch_pdf_links()
    except Exception as e:
        logger.warning("Econ/YouGov link discovery failed: %s", e)
        return {"new_reports": 0, "questions": 0}

    existing = {r.source_url for r in db.query(EconYouGovReport.source_url).all()}
    new_links = [l for l in links if l not in existing][:MAX_REPORTS_PER_RUN]

    new_reports = 0
    total_q = 0
    for url in new_links:
        try:
            n = await _process_report(url, db)
            if n:
                new_reports += 1
                total_q += n
        except Exception as e:
            db.rollback()
            logger.warning("Econ/YouGov report failed %s: %s", url[-20:], e)

    logger.info("Econ/YouGov refresh: %d new reports, %d questions",
                new_reports, total_q)
    return {"new_reports": new_reports, "questions": total_q}
