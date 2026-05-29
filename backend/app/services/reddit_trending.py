"""
Reddit Trending Service.
Fetches hot posts from r/all (no auth needed for public JSON endpoint).
Creates Trend records for high-signal posts not already in the feed.
"""
import logging
import os
import re
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session

from app.models import Summary, Trend

logger = logging.getLogger(__name__)

REDDIT_URL = "https://www.reddit.com/r/all/hot.json?limit=50"
HEADERS = {"User-Agent": "TrendingNewsSite/1.0 (educational project)"}

# Subreddits that tend to be noise for a news context
SKIP_SUBREDDITS = {
    "memes", "dankmemes", "funny", "askreddit", "tifu", "aww", "pics",
    "gifs", "gaming", "leagueoflegends", "minecraft", "pokemon",
    "wholesomememes", "me_irl", "showerthoughts", "jokes", "riddles",
}

MIN_SCORE = 3_000   # minimum upvotes to be considered
MIN_COMMENTS = 100  # minimum engagement


def _clean_title(title: str) -> str:
    """Strip common Reddit noise from titles."""
    title = re.sub(r"\[.*?\]|\(.*?\)", "", title).strip()
    title = re.sub(r"\s+", " ", title)
    # Truncate to a readable length
    return title[:120].strip()


def _reddit_signal(score: int, comments: int) -> float:
    base = min(score / 1000, 200.0)
    comment_boost = min(comments / 100, 50.0)
    return base + comment_boost


async def fetch_reddit_trending(db: Session) -> list:
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=12.0) as client:
            resp = await client.get(REDDIT_URL)
        if resp.status_code != 200 or not resp.text.strip():
            logger.info("Reddit: blocked or empty response (status=%s) — skipping (datacenter IPs often blocked)", resp.status_code)
            return []
        resp.raise_for_status()
    except Exception as e:
        logger.info("Reddit fetch skipped: %s", e)
        return []

    posts = resp.json().get("data", {}).get("children", [])
    active_titles = {t.title.lower(): t for t in db.query(Trend).filter(Trend.is_active == True).all()}  # noqa
    groq_key = os.getenv("GROQ_API_KEY")
    now = datetime.now(timezone.utc)
    new_trends = []

    for child in posts:
        post = child.get("data", {})
        if post.get("subreddit", "").lower() in SKIP_SUBREDDITS:
            continue
        if post.get("is_self") and not post.get("selftext"):
            continue

        score = post.get("score", 0)
        comments = post.get("num_comments", 0)
        if score < MIN_SCORE or comments < MIN_COMMENTS:
            continue

        raw_title = post.get("title", "")
        title = _clean_title(raw_title)
        if not title or len(title) < 10:
            continue

        # Check against existing active trends
        title_lower = title.lower()
        title_words = set(title_lower.split())
        reddit_sig = _reddit_signal(score, comments)
        matched_existing = None
        for existing_title, existing_trend in active_titles.items():
            overlap = len(title_words & set(existing_title.split())) / max(len(title_words), 1)
            if overlap >= 0.5:
                matched_existing = existing_trend
                break

        if matched_existing:
            # Absorb Reddit signal into the existing entry rather than creating a duplicate
            matched_existing.signal_score = matched_existing.signal_score + reddit_sig * 0.5
            continue

        signal = _reddit_signal(score, comments)
        subreddit = post.get("subreddit", "")
        url = f"https://reddit.com{post.get('permalink', '')}"

        # Groq summary
        summary_text = None
        if groq_key:
            try:
                async with httpx.AsyncClient(timeout=12.0) as client:
                    sr = await client.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers={"Authorization": f"Bearer {groq_key}"},
                        json={
                            "model": "llama-3.1-8b-instant",
                            "messages": [{"role": "user", "content":
                                f'Reddit post from r/{subreddit} with {score:,} upvotes: "{title}". '
                                f'Write 1-2 sentences explaining what this is about. Be factual and concise.'}],
                            "max_tokens": 100,
                            "temperature": 0.3,
                        },
                    )
                if sr.status_code == 200:
                    summary_text = sr.json()["choices"][0]["message"]["content"].strip()
            except Exception:
                pass

        trend = Trend(
            title=title,
            source="reddit",
            is_active=True,
            first_seen_at=now,
            appearance_count=1,
            signal_score=signal,
            geo="US",
            traffic_volume=f"{score // 1000}K pts",
        )
        db.add(trend)
        db.flush()

        if summary_text:
            db.add(Summary(trend_id=trend.id, body=summary_text, generated_at=now))

        new_trends.append(trend)
        if len(new_trends) >= 10:
            break

    db.commit()
    logger.info("Reddit trending: %d new trends added", len(new_trends))
    return new_trends
