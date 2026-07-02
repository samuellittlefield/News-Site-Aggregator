<!--
TEMPLATE: Feature Plan
File location once approved: news-site/docs/features/<slug>/01-feature-plan.md
Fill in every section. Delete instructional comments (like this one) before finalizing.
-->

# Feature Plan: <Feature Name>

**Slug:** `<slug>` &nbsp; **Owner:** Samuel &nbsp; **Status:** Draft &nbsp; **Date:** <YYYY-MM-DD>

## Problem / Goal
What's broken, missing, or worth building? One paragraph, plain language.

## Context
- Which part of the system does this touch — Politics & Polling, Forecasting, News, Trends & Attention, Weather/Hazards, Service Status, or something new?
- Any related existing source/service/route/UI (per `SOURCES.md`) this builds on or replaces?
- Why now — what prompted this?

## Scope
What's in for v1. Be specific about which surfaces change:
- [ ] New/changed data source (upstream, cadence)
- [ ] New/changed backend service (`backend/app/services/`)
- [ ] New/changed API route (`backend/app/routers/`)
- [ ] New/changed scheduler job (`backend/app/scheduler.py`)
- [ ] New/changed data model (`backend/app/models.py` + Alembic migration)
- [ ] New/changed frontend component/page (`frontend/src/components/` or `/pages/`)

## Non-Goals
What this explicitly does NOT cover in v1 (defer to a follow-up plan).

## Proposed Approach
How you'd solve it, at a level someone unfamiliar with this feature could follow. If it's a new data source, note the ingestion pattern it follows: `async def fetch_*(db)` → upsert into a model → router → scheduler job (per `SOURCES.md` convention).

## Open Questions / Risks
- Upstream API stability, rate limits, auth requirements?
- Anything that could break the "one bad source can't starve the rest" isolation pattern?
- Dependencies on other in-flight work?

## References
Links to upstream API docs, related GitHub issues/commits, prior art in the codebase.
