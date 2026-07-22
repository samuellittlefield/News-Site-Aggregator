# Test Cases: Consolidate Status + Admin into One Page

**Slug:** `status-admin-consolidation` &nbsp; **Source:** `02-acceptance-criteria.md`

> Frontend-only feature, no backend changes — all cases are manual/click-through. No Vitest harness exists yet (separate, unshipped roadmap chore), so automation notes point there for the future.

## Coverage Map
| AC | Test IDs |
|---|---|
| AC-1 | TC-1 |
| AC-2 | TC-2 |
| AC-3 | TC-3 |
| AC-4 | TC-4 |
| AC-5 | TC-5 |
| AC-6 | TC-6 |
| AC-7 | TC-7 |
| AC-8 | TC-8 |
| AC-9 | TC-9 |
| AC-10 | TC-10 |
| (edge cases) | TC-11, TC-12 |

## Test Cases

### TC-1 — One page, `/status` redirects (covers AC-1)
- **Type:** manual/click-through
- **Steps:**
  1. Navigate to `/admin` — confirm it shows data-pipeline health, third-party status, candidate browsing, and tag review all on one page
  2. Navigate to `/status` directly (fresh URL bar entry, simulating an old bookmark)
- **Expected Result:** `/status` lands on the same consolidated page (redirect), not a blank page or 404
- **Automation note:** target a Vitest router test once that harness exists

### TC-2 — Page explains itself (covers AC-2)
- **Type:** manual/click-through
- **Steps:** load `/admin` fresh
- **Expected Result:** a title and one-line intro are visible near the top, stating what the page is and that health sections are read-only

### TC-3 — Summary banner matches actual source health (covers AC-3)
- **Type:** manual/click-through
- **Steps:**
  1. With backend seeded so at least one data-pipeline source is stale or failing, load `/admin`
  2. Compare the top summary banner's count against the individual `SourceHealthSection` cards below it
- **Expected Result:** banner's "N need attention" count matches the number of cards actually flagged stale/failing — confirms it's using the same `classify()` logic, not a separate/divergent calculation

### TC-4 — Data pipelines lead, third-party is collapsed (covers AC-4)
- **Type:** manual/click-through
- **Steps:** load `/admin` fresh, without interacting
- **Expected Result:** the data-pipeline health section is visible and appears before the third-party section; the third-party section is collapsed (not showing full card detail) until explicitly expanded

### TC-5 — Expanding third-party section shows full data (covers AC-5)
- **Type:** manual/click-through
- **Steps:** click/expand the collapsed third-party section
- **Expected Result:** all services render with the same indicators, descriptions, and last-updated times as today's `ServiceStatusSection` — no data missing after the layout change

### TC-6 — Admin write actions work identically (covers AC-6)
- **Type:** manual/click-through
- **Steps:**
  1. With the admin key set, confirm a pending tag
  2. Reject a different pending tag
  3. Add a manual tag to a candidate via the candidate browser
- **Expected Result:** all three succeed exactly as on the current `AdminPage` — same success behavior, tag list updates immediately

### TC-7 — Candidate browsing is the default view (covers AC-7)
- **Type:** manual/click-through
- **Steps:** load `/admin` fresh (no prior tab interaction)
- **Expected Result:** the candidate browser is shown by default, not the pending-tags review — confirms the default tab flipped from "pending" to "candidates"

### TC-8 — No dead instruction in the empty state (covers AC-8)
- **Type:** manual/click-through
- **Steps:** with zero pending AI tag suggestions, switch to the tag-review view
- **Expected Result:** empty state shows accurate copy about the weekly scheduled job; `POST /api/admin/run-tagger` does not appear anywhere on the page

### TC-9 — Read-only content needs no key (covers AC-9)
- **Type:** manual/click-through
- **Steps:** load `/admin` in a fresh session (no admin key entered), view the summary banner, data-pipeline section, and expanded third-party section
- **Expected Result:** all render normally, no key prompt appears until a write action (confirm/reject/add tag) is actually attempted

### TC-10 — No new/duplicate network calls (covers AC-10)
- **Type:** manual, browser dev tools
- **Steps:** open the Network tab, reload `/admin`, inspect the XHR/fetch requests fired
- **Expected Result:** only the existing endpoints are called once each (`/api/status/sources`, `/api/status`, `/api/candidates/issues/pending`, `/api/candidates`, `/api/candidates/taxonomy`) — no new endpoints, no duplicate calls to the same one

### TC-11 — Graceful empty states (edge case)
- **Type:** manual/click-through
- **Steps:** simulate zero data-pipeline sources and/or zero third-party services (or test against a fresh/empty environment if available)
- **Expected Result:** sections degrade gracefully (render nothing or an appropriate empty message), no crash, consistent with each component's existing loading/empty guards

### TC-12 — All-healthy banner reads correctly (edge case)
- **Type:** manual/click-through
- **Steps:** with all sources and services healthy, load `/admin`
- **Expected Result:** summary banner plainly states everything is current/operational — not blank, not silently omitted

## Regression Check
- Existing `write-endpoint-auth` behavior (key prompt, error banner on 401, memory-only key storage) — unaffected by this layout change, re-verify it still works inside the consolidated page (folded into TC-6/TC-9).
- `SourceHealthSection`'s existing stale/failure flagging logic — unchanged, just relocated and additionally summarized (TC-3).
- `ServiceStatusSection`'s existing rendering — unchanged, just collapsed by default (TC-5).

## Sign-off
- [ ] All test cases pass (manual click-through for all — no automated suite for this frontend-only feature yet)
- [ ] Samuel has reviewed results before merge to main
