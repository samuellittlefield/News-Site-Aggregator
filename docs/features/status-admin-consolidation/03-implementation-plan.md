# Implementation Plan: Consolidate Status + Admin into One Page

**Slug:** `status-admin-consolidation` &nbsp; **Source:** `01-feature-plan.md`, `02-acceptance-criteria.md`

## Summary
Frontend-only consolidation: fold `StatusPage.tsx`'s two health sections into `AdminPage.tsx`, reorder so data-pipeline health leads and third-party status is collapsed by default, flip the default admin tab from tag-review to candidate-browsing, fix the dead empty-state copy, and retire `/status` as a client-side redirect to `/admin`. No backend changes.

## Backend Changes
None. This feature is entirely frontend/routing.

## Frontend Changes
| File | Change |
|---|---|
| `frontend/src/pages/AdminPage.tsx` | Becomes the consolidated page. Add a page title + one-line intro (per AC-2). Add a top-of-page health summary banner, computed from `useSourceRuns()` reusing `SourceHealthSection`'s existing `classify()` logic (see Data Model / below — this needs to be exported/shared, not duplicated, per AC-3). Render `<SourceHealthSection />` prominently near the top (AC-4). Render `<ServiceStatusSection />` wrapped in a collapsed-by-default disclosure (native `<details>` is sufficient — no new dependency needed) per AC-4/AC-5. Change `useState<AdminTab>("pending")` default to `useState<AdminTab>("candidates")` so candidate browsing is the default view, not tag review (AC-7). Fix `PendingTagsTab`'s empty state: remove the `POST /api/admin/run-tagger` line entirely, replace with accurate copy about the weekly scheduled job (AC-8) |
| `frontend/src/components/SourceHealthSection.tsx` | Export the `classify` function (and/or a small derived-summary helper) so the new page-level banner can compute "N sources need attention" using the same logic instead of a parallel implementation (AC-3) |
| `frontend/src/pages/StatusPage.tsx` | Delete — its two sections now live in `AdminPage.tsx` |
| `frontend/src/App.tsx` | Remove the `StatusPage` import and the `{page === "status" && <StatusPage />}` line. When `page === "status"`, redirect client-side to `/admin` (e.g. a `useEffect` calling `navigate("admin")`, or handling it directly in `useNavigation`'s `fromPath` so `/status` resolves straight to the `admin` page state) — confirm which approach fits better once in the code, either is fine as long as a direct `/status` visit lands on the consolidated page rather than a blank/broken route (AC-1) |
| `frontend/src/lib/useNavigation.ts` | If the redirect is handled here instead of `App.tsx`: `fromPath()` can map `/status` directly to `{ page: "admin" }` rather than needing a separate render-time redirect. Pick one approach, not both |

Before removing `/status`: grep the repo (and ask Samuel) for any hardcoded links to `/status` — none expected (it wasn't in `NAV_TABS`), but confirm rather than assume (per AC-1's "confirmed no external link depends on it first").

## Data Model / Migration Notes
None — no backend/schema changes.

## Sequencing
1. Export `classify()` (or equivalent) from `SourceHealthSection.tsx`
2. Restructure `AdminPage.tsx`: title/intro, summary banner, `SourceHealthSection` (prominent), `ServiceStatusSection` (collapsed), default tab flip, empty-state copy fix
3. Remove `StatusPage.tsx`
4. Update `App.tsx`/`useNavigation.ts` for the `/status` → `/admin` redirect
5. Tests (per `04-test-cases.md`)

## Documentation Updates
- [ ] No `SOURCES.md` change needed (no data source affected)
- [ ] No `.env.example` change needed

## Risks / Rollback
- Low risk — no backend/data changes, purely a frontend recomposition of existing, already-shipped components. Rollback is a straightforward revert of the frontend diff.
- Main thing to watch: the `AdminGateContext`/key-prompt wrapper currently wraps the whole `AdminPage` return value — confirm the health sections (which need no key) aren't accidentally nested inside anything that assumes a key is present, since AC-9 requires them to render freely without one.
- Confirm no dead import of `StatusPage` is left anywhere after deletion (a stale import would break the build, not silently pass).

## Test Plan Pointer
See `04-test-cases.md`. Frontend-only feature — no backend pytest cases apply here; all cases are manual/click-through (no Vitest harness yet, per the ongoing roadmap chore).
