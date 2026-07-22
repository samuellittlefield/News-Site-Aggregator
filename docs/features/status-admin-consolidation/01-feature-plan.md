# Feature Plan: Consolidate Status + Admin into One Page

**Slug:** `status-admin-consolidation` &nbsp; **Owner:** Samuel &nbsp; **Status:** Draft &nbsp; **Date:** 2026-07-21

## Problem / Goal
`/status` and `/admin` are both unlinked (not in `NAV_TABS`), single-user, internal-only pages, and neither explains itself. `/status` has no page title or intro copy — it drops straight into two unlabeled card rails with nothing to actually do on it. `/admin` is better labeled but its "Pending AI Tags" empty state instructs `POST /api/admin/run-tagger to trigger manually` — an endpoint that doesn't exist anywhere in the backend, a dead/false instruction. Neither page's information hierarchy reflects what actually matters: on `/status`, our own data pipeline health (`SourceHealthSection`, from `ingestion-health`) is visually equal to third-party infra uptime, when only the former affects what users see.

Separately, during review it came out that the AI issue-tag review workflow (`PendingTagsTab`) moderates data that nothing on the public site currently consumes — `confirmed_issues`/`issue_tags` are only read by `/api/candidates` and the Admin page itself, not by any ranked/trending candidate list. It's a working pipeline producing currently-unused output, so it should stay in the redesign but not be the first thing a visitor sees.

Goal: consolidate both pages into one, with a layout that answers "is the site healthy" at a glance, puts our own data first, and folds in the existing admin actions without pretending the tag-review workflow is more load-bearing than it is.

## Context
- Frontend-only — no backend changes needed. This is information architecture and layout, not new functionality (explicitly not adding new triggerable actions — see Non-Goals).
- Builds directly on existing components: `SourceHealthSection.tsx` and `ServiceStatusSection.tsx` (currently on `StatusPage.tsx`), and `PendingTagsTab`/`CandidateBrowserTab` plus the `AdminGateContext` key-prompt machinery (currently on `AdminPage.tsx`).
- Why now: Samuel visited both pages directly (they're not linked) and found them unclear; a design pass (mockup reviewed and approved 2026-07-21) settled on consolidation plus a clearer hierarchy, rather than just patching each page separately.

## Scope
- [x] New/changed frontend page: retire `StatusPage.tsx` and `AdminPage.tsx` as separate routes, replace with one consolidated page (route TBD in implementation plan — likely keep `/admin` since it's the more specific existing URL Samuel already knows, retire `/status` as a redirect or removed route; implementation plan should confirm nothing else links to `/status` before removing it).
- [x] Page gets a real title and one-line intro explaining what it is and isn't (a read-only status view is not a control panel).
- [x] At-a-glance summary at the top: overall health (all current / N sources need attention), replacing the need to scan card rails to find out.
- [x] Reordered hierarchy: our own data pipeline health (`SourceHealthSection`) first and prominent; third-party dependency status (`ServiceStatusSection`) demoted to a collapsed/secondary section (e.g. `<details>` or an explicit "show" toggle).
- [x] Admin actions (candidate browsing + manual tag add, from `CandidateBrowserTab`) remain prominent — these are real, used actions.
- [x] AI tag review (`PendingTagsTab`) folded into the same page but de-emphasized — not the default view, smaller visual weight, given it currently feeds nothing downstream.
- [x] Fix the dead `POST /api/admin/run-tagger` instruction — replace with accurate copy (suggestions come from the weekly scheduled job; nothing to trigger manually), per the approved mockup.
- [x] Auth model carries over unchanged: read-only health info stays visible without the admin key; the key prompt only fires on write actions (confirm/reject/add tag), exactly as `write-endpoint-auth` already built it.

## Non-Goals
- No new backend endpoints or triggerable actions (no manual "run tagger" button, no manual per-source refresh trigger) — this was explicitly decided as a "full UX rework" pass, not an "add real admin actions" pass.
- No change to the tag-review data model, confirm/reject logic, or the weekly scheduler job itself — only how prominently it's presented.
- No decision here about whether `/status` should ever become a genuinely public page — noted as a real tension (see Open Questions) but not resolved in this pass; if it matters later, it's a straightforward split back out since nothing about this consolidation is destructive to the underlying components.
- No redesign of the candidate browser's own interaction pattern beyond what's needed to fit the new page — it stays largely as-is.

## Proposed Approach
One consolidated page (component composition, not a rewrite) that reuses `SourceHealthSection`, `ServiceStatusSection`, `PendingTagsTab`, and `CandidateBrowserTab` largely as-is, wrapped in a new top-level layout: title + intro + summary banner, then data-pipeline health, then a collapsed third-party section, then the admin actions area (candidate browser prominent, tag review folded in as a secondary tab or a de-emphasized section — implementation plan to pick the exact pattern based on the approved mockup direction). The existing `AdminGateContext`/key-prompt logic wraps the whole page as it does today, but since health info no longer requires a key, only the write-triggering components inside stay wrapped by `runAdminAction`.

## Open Questions / Risks
- Final route: keep `/admin`, introduce something more neutral like `/ops`, or keep both `/status` and `/admin` as URLs that both render the same consolidated component? Leaning toward single URL (`/admin`) per the stated goal of "one URL to remember," but implementation plan should confirm nothing currently deep-links to `/status` before removing it.
- The public-status-page tension (noted above) isn't resolved, just deliberately deferred — worth revisiting if that ever becomes a real ask, since it would mean splitting this back into two surfaces with different auth postures.
- Exact visual pattern for "de-emphasized" tag review (collapsed section vs. secondary tab vs. smaller card treatment) — settle in implementation plan/mockup refinement, not a blocker to starting.

## References
- Mockup direction reviewed and approved 2026-07-21 (Cowork visual concept, not committed anywhere — implementation plan should treat it as directional, not pixel-spec).
- `frontend/src/pages/StatusPage.tsx`, `frontend/src/pages/AdminPage.tsx`, `frontend/src/components/SourceHealthSection.tsx`, `frontend/src/components/ServiceStatusSection.tsx`
- `write-endpoint-auth` (shipped, PR #10) — the auth-gate pattern this consolidation must preserve unchanged
