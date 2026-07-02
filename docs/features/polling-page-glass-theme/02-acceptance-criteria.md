# Acceptance Criteria: Polling Page Liquid Glass Theme

**Slug:** `polling-page-glass-theme` &nbsp; **Source plan:** `01-feature-plan.md`

## Criteria

### AC-1: Polling page renders on the lavender glass base, not the old dark neutral
- **Given** a user loads the Polling page
- **When** the page renders
- **Then** the top-level background is the `glass-base` lavender token (`#e9e3f6`), not `bg-gray-950`, and no element on the page still references the old flat `gray-900`/`gray-950` panel classes

### AC-2: Panels use the translucent glass treatment
- **Given** any panel-style surface across the 8 in-scope components (`ForecastSection`, `GenericBallotBar`, `VoteHubApprovalCard`, `ApprovalSection`, `DistrictMap`, `PollCarousel`, `RecentPollsList`, `SourcesDisclosure`)
- **When** it renders
- **Then** it uses `glass-panel`/`glass-panel-nested` background, `backdrop-filter: blur(16px)`, a `glass-border` outline, 14–16px corner radius, and a soft low-opacity shadow — matching the mocked-up treatment, not a flat opaque fill

### AC-3: Red/blue party data stays legible and distinguishable on the light glass background
- **Given** any element encoding party data (generic ballot margin text/bar in `GenericBallotBar.tsx`, R/D bars and margin text in `PollCarousel.tsx`)
- **When** rendered over a `glass-panel` surface
- **Then** it uses the `poll-red`/`poll-blue` tokens (not the old dark-tuned `red-400/600/900` / `blue-400/600/900`), and Republican vs. Democrat values remain clearly distinguishable by color at a glance

### AC-4: Poll grade badges are re-tuned for the light background
- **Given** a poll grade badge (`B+`, `B`, `C-`, `D`) in `PollCarousel.tsx`
- **When** rendered
- **Then** it no longer uses the old dark badge fills (`bg-blue-900`, `bg-red-950`, etc.) and instead uses a light-background-appropriate fill/text pairing where all four grades remain visually distinct from each other and from the R/D data colors

### AC-5: Text meets contrast minimums against worst-case backgrounds, not just the flat base
- **Given** body and label text rendered inside a `glass-panel` element
- **When** that panel sits over visually varied content (e.g. a `DistrictMap` panel over the cartogram's darkest hex fill, or a `PollCarousel` card over a busy area)
- **Then** `ink`/`ink-muted` text still meets WCAG AA contrast (4.5:1 body, 3:1 large text) against the *worst* realistic composite behind it, not just against the flat lavender page background

### AC-6: Blur is applied selectively, not blanket, based on a manual perf check
- **Given** `RecentPollsList` (a dense, scrollable list) rendered with `backdrop-filter` blur on every row
- **When** a user scrolls the list while the `DistrictMap` cartogram is also on screen
- **Then** scrolling is checked manually for perceptible jank; if present, `RecentPollsList` rows fall back to a flat translucent fill (no blur) while summary/hero panels (`ForecastSection`, `GenericBallotBar`, `VoteHubApprovalCard`) keep the full blur treatment

### AC-7: No other page is visually affected
- **Given** the new `glass-*`/`ink`/`poll-red`/`poll-blue` tokens and any Tailwind config changes
- **When** any other page loads (Dashboard in particular, since it renders its own `dashboard/PollsPanel.tsx`)
- **Then** that page's appearance is pixel-for-pixel unchanged — the new tokens are additive, not a replacement of any token another page already relies on

## Data Quality / Edge Cases
*(Adapted for a frontend-only visual feature — no backend ingestion involved.)*
- `backdrop-filter` unsupported browser (rare, pre-2022 engines) → panel falls back to its flat `rgba` background color without blur; verify it's still legible, not a blocking requirement to support gracefully beyond "doesn't break."
- Overscroll bounce at top/bottom of the page → may briefly reveal the global dark `body` background from `index.css`; acceptable per feature plan, not a bug to fix in this pass.
- Empty/loading states (`pollsLoading`, `distLoading`, `ballotLoading` skeletons in `PollsPage.tsx`) → skeleton placeholders (`animate-pulse` blocks) also need to move off `bg-gray-900` onto a glass-consistent placeholder treatment, not just the loaded content.

## Out of Scope
- `dashboard/PollsPanel.tsx` — stays on the existing dark theme (per feature plan Non-Goals).
- Any site-wide light/dark toggle, or changes to any page other than the Polling page.
- Serif/editorial typography — explicitly ruled out in favor of the glass direction; sans-serif (`Inter`) throughout.

## Sign-off
- [x] Samuel has reviewed and approved these criteria before implementation planning begins.

**Shipped:** PR #4 (`78b828d`, merged `26f93ce`), 2026-07-02. AC-7 confirmed directly from the diff — `dashboard/PollsPanel.tsx` and every other page are absent from the changed-files list. AC-1 through AC-6 match the shipped commit message's explicit call-outs (glass tokens, blur treatment, RecentPollsList shipped flat per the AC-6 perf guardrail, choropleth hex values preserved) — not independently re-verified pixel-by-pixel from this session.
