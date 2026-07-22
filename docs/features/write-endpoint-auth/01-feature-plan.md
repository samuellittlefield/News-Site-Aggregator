# Feature Plan: Auth on Write Endpoints

**Slug:** `write-endpoint-auth` &nbsp; **Owner:** Samuel &nbsp; **Status:** Draft &nbsp; **Date:** 2026-07-21

## Problem / Goal
Three mutating endpoints have no authentication today: `POST /api/refresh` (`backend/app/main.py:138`), `POST /api/candidates/{id}/issues`, and `PATCH /api/candidates/{id}/issues/{tag_id}` (both `backend/app/routers/candidates.py`). Anyone who can reach the API can trigger a full data refresh or add/confirm/reject a candidate's issue tags. Goal: require a shared secret on these endpoints so only an authorized caller (Samuel, via the admin UI) can perform them.

## Context
- Cross-cutting/infra, not tied to one `SOURCES.md` domain.
- Roadmap item #3, queued behind `ingestion-health` (currently in progress with Claude Code).
- **Important discovery during planning** — the three endpoints don't have the same threat model, which affects how "simple API-key header" actually gets applied:
  - The two candidate issue-tag endpoints are called only from `frontend/src/pages/AdminPage.tsx` (`confirmTag`, `rejectTag`, `addManualTag` in `client.ts`). `AdminPage` is not in `NAV_TABS` — it's reachable only via direct navigation state, not linked in the UI — but it has **zero auth today**, frontend or backend. These two are genuinely admin-only actions; gating them with a shared secret is exactly the intended fix.
  - `POST /api/refresh` is different: it's called from the public, nav-linked `TrendsPage.tsx` (`triggerRefresh()`, a visible "refresh" button any visitor can click) — not admin-only today, by design or by drift. Putting the same shared secret in front of it means either (a) shipping that secret in public frontend JS, which defeats the purpose since anyone can view-source it, or (b) removing/relocating the public refresh button, which is a UX change beyond "add auth."

## Scope
- [x] New shared dependency: a `require_admin_key` FastAPI dependency (new `backend/app/auth.py` or similar) checking a header (e.g. `X-Admin-Key`) against an `ADMIN_API_KEY` env var, raising 401 if missing/wrong.
- [x] Apply it to `POST /api/candidates/{id}/issues` and `PATCH /api/candidates/{id}/issues/{tag_id}`.
- [x] Frontend: `AdminPage.tsx` needs a way to supply the key — simplest v1 is a one-time prompt/password field stored in memory (not `localStorage`/`sessionStorage` — see risk note) that `client.ts`'s `confirmTag`/`rejectTag`/`addManualTag` attach as a header on each call.
- [x] `.env.example` gets `ADMIN_API_KEY=` added (flagging the existing gap noted in the roadmap chores list for `FEC_API_KEY` — same convention applies here).
- [x] **Decided:** `POST /api/refresh` stays public, no key required — add a simple cooldown (reject repeat calls within N minutes) instead of auth. Samuel's call: the site isn't promoted/discoverable, so an unauthenticated stranger hitting refresh is a surprising edge case, not a real threat worth breaking the public UX over.

## Non-Goals
- Full user accounts / login system — this is a single shared secret, not per-user auth.
- Auth on read (`GET`) endpoints — out of scope, no roadmap ask for this.
- Rotating/expiring the key, rate limiting in general (unless chosen as the `/api/refresh` approach below).
- Gating the `AdminPage` *route* itself in the frontend (vs. the backend calls it makes) — arguably a related gap (the page is unlinked but not password-protected), flagged as a possible fast-follow, not bundled into this v1 unless you want it folded in.

## Proposed Approach
A single `require_admin_key` dependency, added via FastAPI's `Depends()` to each protected route, checks a header against `ADMIN_API_KEY` from the environment. `AdminPage.tsx` prompts for the key once (e.g. on page load, stored in a React state variable, never persisted to browser storage) and every admin-triggered write call sends it. This mirrors the existing `Depends(get_db)` pattern already used throughout the routers, so it's a familiar, small addition — no new library needed (FastAPI's `Security`/`APIKeyHeader` or a plain header dependency both work; implementation plan can pick).

## Open Questions / Risks
- `/api/refresh` cooldown mechanism: in-memory (module-level timestamp, resets on deploy/restart) is simplest and sufficient for v1 — no need for a DB-backed or Redis-backed cooldown given the low-stakes threat model. Implementation plan should confirm this is enough.
- Storing the key in frontend memory only (not `localStorage`) means it's re-entered every page reload — acceptable friction for an admin-only, low-frequency action, but worth confirming that's fine.
- `AdminPage` itself being unlinked-but-unprotected is a real gap; decide whether it's in v1 scope or a fast-follow (see Non-Goals).

## References
- `backend/app/main.py:138` (`/api/refresh`)
- `backend/app/routers/candidates.py:158,184` (issue-tag POST/PATCH)
- `frontend/src/pages/AdminPage.tsx`, `frontend/src/pages/TrendsPage.tsx`, `frontend/src/api/client.ts`
- `docs/ROADMAP.md` item #3
