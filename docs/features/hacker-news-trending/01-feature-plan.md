# Feature Plan: Hacker News Trending Source

**Slug:** `hacker-news-trending` &nbsp; **Owner:** Samuel &nbsp; **Status:** Draft (dry run) &nbsp; **Date:** 2026-07-02

## Problem / Goal
Trends & Attention currently pulls from Google Trends, Wikipedia, Reddit, and NYT RSS, but misses tech/startup-adjacent stories that break early on Hacker News before they hit mainstream feeds. Adding HN as a source fills that gap with minimal new surface area.

## Context
- Section: **Trends & Attention** (per `SOURCES.md`).
- Closest existing precedent: `backend/app/services/reddit_trending.py` — fetches a public, no-auth JSON feed, filters for signal, and writes rows into the existing `Trend` model rather than a dedicated table.
- Why now: it's a small, self-contained feature — good first real run through the new planning pipeline.

## Scope
- [x] New data source (Hacker News Firebase API — `hacker-news.firebaseio.com/v0`, no auth, no rate limit stated)
- [x] New backend service (`backend/app/services/hackernews_trending.py`)
- [ ] New/changed API route — **not needed**, HN stories surface through the existing `/api/trends*` endpoints since they land in the shared `Trend` table
- [x] New/changed scheduler job (`backend/app/scheduler.py`)
- [ ] New/changed data model — **not needed**, reuse `Trend` (existing `source` column already supports multiple values, e.g. `"reddit"`)
- [ ] New/changed frontend component — **not needed**, `Trend` rows already render through `TrendCarousel` / `TrendCard` regardless of source

## Non-Goals
- No per-source filtering UI (e.g. a toggle to hide HN stories) — out of scope for v1.
- No comment-count or discussion-thread display — story title + link + score only, matching how Reddit trends are handled today.

## Proposed Approach
Follow the same ingestion pattern as `reddit_trending.py`: fetch the top-story ID list from HN's `/v0/topstories.json`, pull item details for the top N, filter by a minimum score threshold, de-dupe against active trends via the existing `topic_matcher.find_match`, and upsert into `Trend` with `source="hackernews"`. Register the fetch as a scheduler job alongside the existing Reddit enrichment step (same cadence tier — hourly).

## Open Questions / Risks
- HN API has no documented rate limit but is a Firebase real-time DB — confirm reasonable polling interval (likely fine at hourly, same as other trend sources).
- Score threshold needs tuning so this doesn't flood trends with niche programming posts — start conservative (e.g. score ≥ 200) and adjust after a day of real data.
- No auth/failure-mode risk beyond the standard "source down → skip, don't block other jobs" pattern already used elsewhere.

## References
- HN API docs: `https://github.com/HackerNews/API`
- Precedent: `backend/app/services/reddit_trending.py`, `backend/app/services/topic_matcher.py`
