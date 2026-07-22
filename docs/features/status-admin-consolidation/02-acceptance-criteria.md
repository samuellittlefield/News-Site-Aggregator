# Acceptance Criteria: Consolidate Status + Admin into One Page

**Slug:** `status-admin-consolidation` &nbsp; **Source plan:** `01-feature-plan.md`

## Criteria

### AC-1: One consolidated page replaces both routes
- **Given** the feature is implemented
- **When** a user navigates to `/admin`
- **Then** they see one page containing data-pipeline health, third-party status, candidate browsing, and tag review — not two separate pages
- **And** `/status` either redirects to `/admin` or is removed entirely (implementation plan's call, confirmed no external link depends on `/status` first)

### AC-2: Page explains itself
- **Given** a user with no prior context lands on the consolidated page
- **When** the page renders
- **Then** a title and one-line intro are visible, stating what the page is (an internal ops/admin view) and that the health sections are read-only

### AC-3: Health summary is accurate and immediate
- **Given** the data-pipeline sources have a mix of healthy/stale/failing states
- **When** the page loads
- **Then** a top-of-page summary reflects the correct aggregate state (e.g. "all N current" vs. "N need attention") without requiring the user to scan individual cards first — reusing the existing `classify()` logic from `SourceHealthSection`, not reimplementing it

### AC-4: Our data pipelines are visually primary
- **Given** the page renders with both data-pipeline and third-party sections present
- **When** viewed at default (collapsed) state
- **Then** the data-pipeline section (`SourceHealthSection`) is immediately visible and visually first; the third-party section (`ServiceStatusSection`) is collapsed/secondary by default and requires an explicit expand action to view in full

### AC-5: Third-party section still works when expanded
- **Given** the third-party section is collapsed by default (AC-4)
- **When** a user expands it
- **Then** it shows the same information `ServiceStatusSection` shows today (all services, indicators, last-updated times) — no data loss from the demotion, just default visibility

### AC-6: Admin actions function identically to today
- **Given** a user with a valid admin key
- **When** they confirm/reject a pending tag, or add a manual tag via the candidate browser
- **Then** the action succeeds exactly as it does on the current `AdminPage` — same endpoints, same auth gate, same optimistic UI behavior

### AC-7: Tag review is present but de-emphasized
- **Given** the consolidated page includes the AI tag review workflow
- **When** the page renders at its default view
- **Then** tag review is not the first/most prominent thing shown — candidate browsing (the more load-bearing action) takes visual priority, and tag review requires a switch/expand to reach, consistent with the plan's finding that it currently gates nothing downstream

### AC-8: Dead instruction is gone
- **Given** there are zero pending AI tag suggestions
- **When** the tag review section's empty state renders
- **Then** it shows accurate copy (suggestions come from the weekly scheduled job; nothing to trigger manually) — the `POST /api/admin/run-tagger` reference is removed entirely, not just hidden

### AC-9: Read-only content requires no admin key
- **Given** a user has not entered an admin key this session
- **When** they view the health summary, data-pipeline section, or expanded third-party section
- **Then** all of it renders normally with no key prompt — the key prompt only fires when a write action (confirm/reject/add tag) is actually attempted, exactly as today's `AdminGateContext` behavior

### AC-10: No new network calls introduced
- **Given** this is a frontend-only consolidation
- **When** the consolidated page loads
- **Then** it uses the same existing hooks (`useSourceRuns`, `useServiceStatus`, `usePendingTags`, `useCandidates`, `useIssueTaxonomy`) with no new API endpoints called and no duplicate fetches of the same data

## Data Quality / Edge Cases
- Zero data-pipeline sources or zero third-party services (e.g. a fresh/broken deploy) — sections should degrade gracefully (no crash), consistent with each component's existing `if (loading || X.length === 0) return null` guard.
- All sources healthy — summary banner should say so plainly (not just silently show nothing), matching the existing "All N sources current" / "All services operational" copy patterns.
- A user who lands directly on `/status` via an old bookmark — should not hit a broken/blank page (AC-1's redirect-or-removal decision must handle this, not leave a dangling route).

## Out of Scope
- Any new backend endpoint, manual trigger button, or scheduler change (per feature plan Non-Goals).
- Changing what `confirmed_issues` is used for, or building a consumer for it elsewhere.
- Resolving the "should `/status` ever be public" question — explicitly deferred.

## Sign-off
- [ ] Samuel has reviewed and approved these criteria before implementation planning begins.
