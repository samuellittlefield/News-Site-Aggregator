"""
Hybrid issue tagger — uses Groq to suggest policy positions for candidates
based on their news mentions, stores them as unconfirmed for admin review.
"""
import logging
import os
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session

from app.models import Candidate, CandidateIssueTag, NewsArticle, Summary, Trend

logger = logging.getLogger(__name__)

ISSUE_TAXONOMY = {
    "healthcare":      "Healthcare / ACA",
    "medicare_all":    "Medicare for All",
    "immigration":     "Immigration & Border",
    "economy":         "Economy & Inflation",
    "climate":         "Climate & Environment",
    "guns":            "Gun Policy",
    "abortion":        "Abortion & Reproductive Rights",
    "education":       "Education",
    "housing":         "Housing & Cost of Living",
    "foreign_policy":  "Foreign Policy",
    "trade":           "Trade & Tariffs",
    "democracy":       "Democracy & Voting Rights",
    "taxes":           "Tax Policy",
    "social_security": "Social Security & Medicare",
    "tech_ai":         "Tech & AI Regulation",
}

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.1-8b-instant"


def _collect_mentions(candidate: Candidate, db: Session) -> list[str]:
    """Find news text mentioning this candidate."""
    name_lower = candidate.name.lower()
    # Last name is usually sufficient for matching
    last_name = name_lower.split()[-1] if name_lower.split() else name_lower
    if len(last_name) < 4:  # Too short — use full name
        last_name = name_lower

    mentions = []

    # Scan trend summaries
    summaries = db.query(Summary).all()
    for s in summaries:
        if last_name in s.body.lower():
            mentions.append(s.body[:300])

    # Scan news articles
    articles = db.query(NewsArticle).filter(
        NewsArticle.description.isnot(None)
    ).all()
    for a in articles:
        text = f"{a.title} {a.description or ''}"
        if last_name in text.lower():
            mentions.append(text[:300])

    return mentions[:10]  # Cap at 10 mentions


async def _suggest_issues(candidate: Candidate, mentions: list[str]) -> list[dict]:
    """Ask Groq to suggest issue tags based on mentions."""
    groq_key = os.getenv("GROQ_API_KEY")
    if not groq_key or not mentions:
        return []

    taxonomy_str = "\n".join(f"- {code}: {label}" for code, label in ISSUE_TAXONOMY.items())
    mentions_str = "\n\n".join(f"[{i+1}] {m}" for i, m in enumerate(mentions))

    prompt = f"""You are analyzing news mentions about a political candidate to identify their policy positions.

Candidate: {candidate.name} ({candidate.party}, {candidate.state}, Office: {candidate.office})

News mentions:
{mentions_str}

From this fixed taxonomy, identify which policy positions this candidate appears to advocate based ONLY on the text above:
{taxonomy_str}

Rules:
- Only include positions with clear textual evidence
- Do not infer positions not mentioned in the text
- For each match, respond on one line: issue_code|confidence_0_to_1|exact_quote_from_text
- If no clear positions found, respond: NONE

Format strictly as: issue_code|0.85|"quoted evidence" """

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                GROQ_URL,
                headers={"Authorization": f"Bearer {groq_key}"},
                json={
                    "model": GROQ_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 400,
                    "temperature": 0.1,
                },
            )
        if resp.status_code != 200:
            return []
        content = resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.warning("Groq issue tagging failed for %s: %s", candidate.name, e)
        return []

    if content.strip().upper() == "NONE":
        return []

    suggestions = []
    for line in content.split("\n"):
        line = line.strip()
        if not line or "|" not in line:
            continue
        parts = line.split("|", 2)
        if len(parts) < 2:
            continue
        code = parts[0].strip().lower().strip('"')
        if code not in ISSUE_TAXONOMY:
            continue
        try:
            confidence = float(parts[1].strip())
        except ValueError:
            confidence = 0.5
        quote = parts[2].strip().strip('"') if len(parts) > 2 else ""
        suggestions.append({"code": code, "confidence": confidence, "quote": quote[:500]})

    return suggestions


async def tag_candidates(db: Session, limit: int = 50) -> int:
    """Run AI issue tagging for candidates without confirmed tags. Returns count tagged."""
    candidates = (
        db.query(Candidate)
        .filter(Candidate.name.notlike("TBD%"))
        .limit(limit)
        .all()
    )

    now = datetime.now(timezone.utc)
    tagged_count = 0

    for candidate in candidates:
        mentions = _collect_mentions(candidate, db)
        if not mentions:
            continue

        suggestions = await _suggest_issues(candidate, mentions)

        for s in suggestions:
            # Skip if already has a tag for this issue (confirmed or pending)
            existing = db.query(CandidateIssueTag).filter(
                CandidateIssueTag.candidate_id == candidate.id,
                CandidateIssueTag.issue_code == s["code"],
            ).first()
            if existing:
                continue

            tag = CandidateIssueTag(
                candidate_id=candidate.id,
                issue_code=s["code"],
                ai_suggested=True,
                confirmed=False,
                rejected=False,
                confidence=s["confidence"],
                supporting_text=s["quote"],
                created_at=now,
                updated_at=now,
            )
            db.add(tag)
            tagged_count += 1

    db.commit()
    logger.info("Issue tagger: added %d suggestions for %d candidates", tagged_count, len(candidates))
    return tagged_count
