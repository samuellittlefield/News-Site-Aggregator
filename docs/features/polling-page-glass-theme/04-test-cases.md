# Test Cases: Polling Page Liquid Glass Theme

**Slug:** `polling-page-glass-theme` &nbsp; **Source:** `02-acceptance-criteria.md`

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

## Frontend

All cases are manual — no `pytest`/`vitest` harness exists in this repo yet. Every case is a `npm run dev` + browser walkthrough.

### TC-1 — Polling page loads on the lavender glass base (covers AC-1)
- **Type:** manual
- **Steps:**
  1. Run `npm run dev` in `frontend/`, navigate to the Polling page.
  2. Inspect the top-level page background via devtools.
  3. Search the rendered DOM/devtools styles panel for any remaining `bg-gray-900`/`bg-gray-950` class on the page.
- **Expected Result:** page background resolves to `glass-base` (`#e9e3f6`), not `gray-950`; no element on the page still carries the old flat gray panel classes.
- **Automation note:** target a Playwright/Vitest DOM snapshot once a harness exists — assert no `gray-9\d\d` class names present in the rendered Polling page.

### TC-2 — Panel surfaces render with the glass treatment (covers AC-2)
- **Type:** manual, visual
- **Steps:**
  1. Load the Polling page with dev tools open.
  2. For each of the 8 components (`ForecastSection`, `GenericBallotBar`, `VoteHubApprovalCard`, `ApprovalSection`, `DistrictMap`, `PollCarousel`, `RecentPollsList`, `SourcesDisclosure`), inspect a representative panel element's computed styles.
- **Expected Result:** each panel shows `background: rgba(255,255,255,...)`, a non-zero `backdrop-filter: blur(...)` (except `RecentPollsList` rows, see TC-6), a `glass-border` outline, 14–16px `border-radius`, and a shadow — not a flat opaque `gray-900` fill.

### TC-3 — Red/blue party data stays legible and distinguishable (covers AC-3)
- **Type:** manual, visual
- **Steps:**
  1. Load the Polling page.
  2. Check the generic ballot bar (`GenericBallotBar.tsx`) margin text/fill and the R/D bars + margin text on poll cards (`PollCarousel.tsx`).
  3. Confirm neither uses the old `red-400/600/900`/`blue-400/600/900` classes (devtools).
  4. Visually confirm R and D values are clearly distinguishable at a glance (not just by position/label).
- **Expected Result:** all party-data elements use `poll-red`/`poll-blue` (or their `-bar` variants); Republican vs. Democrat values are unambiguous by color alone.

### TC-4 — Grade badges are legible on the light background (covers AC-4)
- **Type:** manual, visual
- **Steps:**
  1. Scroll the poll carousel until at least one poll of each grade (`B+`, `B`, `C-`, `D`) is visible (or temporarily hardcode all four in `PollCarousel.tsx` locally to check side by side).
  2. Confirm none use the old dark fills (`bg-blue-900`, `bg-red-950`, etc.).
- **Expected Result:** all four grades render with the light-mode-equivalent pairing (`bg-{color}-100`/`text-{color}-700`), each visually distinct from the other three and from the R/D data colors.

### TC-5 — Text contrast holds over worst-case backgrounds (covers AC-5)
- **Type:** manual, contrast check
- **Steps:**
  1. Load the Polling page, scroll `DistrictMap` so a glass panel overlaps the cartogram's darkest hex fill (`leanColor()` deep red `#991b1b` / deep blue `#1e3a8a`).
  2. Sample the effective composite color behind the panel text (devtools color picker, or screenshot + eyedropper) and check `ink`/`ink-muted` text against it with a contrast checker (e.g. WebAIM contrast checker).
  3. Repeat for a `PollCarousel` card over a visually busy area, if applicable.
- **Expected Result:** body text ≥ 4.5:1, large/label text ≥ 3:1 against the worst realistic composite, not just the flat lavender base.
- **Automation note:** could be scripted with Playwright + `axe-core` color-contrast rule once a harness exists, but the "worst-case composite behind a blurred panel" scenario likely still needs manual/visual spot-checks even then.

### TC-6 — Blur is applied selectively based on a real perf check (covers AC-6)
- **Type:** manual, performance
- **Steps:**
  1. Load the Polling page with `DistrictMap` and `RecentPollsList` both on screen (resize/scroll as needed).
  2. Open Chrome DevTools Performance panel (or the FPS meter), scroll `RecentPollsList` continuously for ~5 seconds.
  3. Check for dropped frames / jank correlated with the blur.
- **Expected Result:** if jank is present, `RecentPollsList` rows use a flat translucent fill (no `backdrop-filter`) while `ForecastSection`/`GenericBallotBar`/`VoteHubApprovalCard` keep full blur; if no jank, blur may stay on `RecentPollsList` too. Either outcome is a pass as long as the decision was actually checked, not assumed.

### TC-7 — No other page is affected (covers AC-7)
- **Type:** manual, regression
- **Steps:**
  1. Before making changes, screenshot the Dashboard page (particularly `dashboard/PollsPanel.tsx`) and any other page for a baseline.
  2. After implementation, reload the Dashboard and compare pixel-for-pixel (or close visual inspection) against the baseline.
  3. Confirm `tailwind.config.js`'s new `glass`/`ink`/`poll` tokens are additive (grep for any other file referencing the same token names before this change — should be none).
- **Expected Result:** Dashboard and every other page render identically to before this change.

## Edge Cases & Failure Modes
- `backdrop-filter` unsupported browser → panel falls back to its flat `rgba` background; spot-check in an older browser/engine if available, otherwise note as accepted risk per the feature plan.
- Overscroll bounce at page top/bottom → global dark `body` background may flash briefly; confirmed acceptable per feature plan, not a failure.
- Loading skeletons (`pollsLoading`/`distLoading`/`ballotLoading` `animate-pulse` blocks in `PollsPage.tsx`) → verify these also moved off `bg-gray-900` onto a glass-consistent placeholder, not just the loaded state.
- Secondary accent colors (`poll-positive`, `poll-amber`, `poll-purple`) — sanity-check all four usages (`VoteHubApprovalCard.tsx` net approval, `ApprovalSection.tsx` net approval + Independent bar, `ForecastSection.tsx` tuning badge, `RecentPollsList.tsx` approval badge) render legibly and don't get confused with `poll-red`/`poll-blue` at a glance.

## Regression Check
- Existing interactions still function after the class-only changes: district click-to-expand in `DistrictMap.tsx`, poll carousel scroll/swipe in `PollCarousel.tsx`, the "tuning" toggle button in `ForecastSection.tsx`, and the crosstab expand/collapse in `ApprovalSection.tsx` — all pure markup/style changes, but worth a functional smoke pass since 9 files are touched.
- `dashboard/PollsPanel.tsx` and any other page — confirmed unaffected per TC-7.
- `frontend/src/index.css`'s global `body` styles — confirmed untouched, other pages keep the dark theme.

## Sign-off
- [x] All test cases pass
- [x] Samuel has reviewed results before merge to main

**Shipped:** PR #4 (`78b828d`, merged `26f93ce`), 2026-07-02. TC-7 confirmed directly from the diff (Dashboard/other pages untouched). TC-5/TC-6 (contrast, blur perf) rely on Code's pre-merge verification, not re-checked independently in this session.
