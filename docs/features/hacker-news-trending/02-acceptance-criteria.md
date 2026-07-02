# Acceptance Criteria: Hacker News Trending Source

**Slug:** `hacker-news-trending` &nbsp; **Source plan:** `01-feature-plan.md`

## Criteria

### AC-1: New HN stories above the score threshold become Trend rows
- **Given** the scheduler runs the HN enrichment job
- **When** a top story from `/v0/topstories.json` has a score at or above the configured minimum and isn't already an active trend
- **Then** a new `Trend` row is created with `source="hackernews"`, the story title, and its HN link

### AC-2: Low-signal stories are filtered out
- **Given** the scheduler runs the HN enrichment job
- **When** a top story's score is below the minimum threshold
- **Then** no `Trend` row is created for it

### AC-3: Matching an existing trend boosts it instead of duplicating
- **Given** an active trend already exists whose title closely matches an HN story (via `topic_matcher.find_match`)
- **When** the HN job processes that story
- **Then** the existing trend's `signal_score` is boosted and `"hackernews"` is added to its `sources_list`, and no duplicate row is created

### AC-4: HN stories surface in the existing trends UI without frontend changes
- **Given** HN-sourced trends exist in the `trends` table
- **When** a user loads the Trends tab
- **Then** those trends appear in `TrendCarousel`/`TrendCard` exactly like Reddit- or Wikipedia-sourced trends — no visual distinction required for v1

## Data Quality / Edge Cases
- HN API unreachable or returns malformed data → job logs and returns early (empty list), scheduler continues with other jobs uninterrupted.
- Empty `trends` table (first run) → job creates rows without error.
- Re-run within the same hour → no duplicate rows for stories already ingested (either matched-and-boosted per AC-3, or naturally skipped if still in `topstories.json` and still below re-processing window — clarify expected behavior if this comes up in implementation).
- HN item marked deleted/dead (`"dead": true` or missing `"title"`) → skipped, not treated as an error.

## Out of Scope
- No new API route, no new frontend component, no per-source UI filtering (per feature plan Non-Goals).

## Sign-off
- [x] Samuel has reviewed and approved these criteria before implementation planning begins. *(dry run — treat as illustrative, not a real commitment)*
