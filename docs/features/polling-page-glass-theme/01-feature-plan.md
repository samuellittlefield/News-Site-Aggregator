# Feature Plan: Polling Page Liquid Glass Theme

**Slug:** `polling-page-glass-theme` &nbsp; **Owner:** Samuel &nbsp; **Status:** Draft &nbsp; **Date:** 2026-07-02

## Problem / Goal
The Polling page's dark mode reads flat and generic — it's Tailwind's stock `gray-950`/`gray-900` neutral scale with zero custom tokens, so it looks like any other default Tailwind dashboard. Retheme it to a distinct visual identity: a light lavender base with translucent "liquid glass" panels (low-opacity, blurred, softly bordered), replacing the current flat dark neutral surfaces — while keeping the existing red/blue party-color data encoding legible and un-clashing.

## Context
- Section: **Politics & Polling** (per `SOURCES.md`).
- Scoped to `frontend/src/pages/PollsPage.tsx` and the 8 components it exclusively renders: `ForecastSection`, `GenericBallotBar`, `VoteHubApprovalCard`, `ApprovalSection`, `DistrictMap`, `PollCarousel`, `RecentPollsList`, `SourcesDisclosure`. Confirmed via grep that none of these are imported anywhere else in the app (the Dashboard's condensed poll widget, `dashboard/PollsPanel.tsx`, is a separate component) — so this retheme is fully containable to the Polling page.
- Why now: worked through several directions with Samuel before landing here — a same-family dark retint (warm graphite/stone/cool neutral, still near-black), a mid-tone "paper" editorial concept (serif, ink-on-stone), and finally a lighter liquid-glass concept (translucent panels over a pale lavender base, sans-serif, no newspaper feel). Lavender was picked over sage/blush as the base hue.

## Scope
- [ ] New/changed data source — not needed
- [ ] New/changed backend service — not needed
- [ ] New/changed API route — not needed
- [ ] New/changed scheduler job — not needed
- [ ] New/changed data model — not needed
- [x] New/changed frontend component/page — `frontend/src/pages/PollsPage.tsx` + its 8 child components (listed above), plus a new custom color token layer (`frontend/tailwind.config.js` and/or CSS variables in `frontend/src/index.css`)

## Non-Goals
- `dashboard/PollsPanel.tsx` (the Dashboard's condensed poll widget) stays on the existing dark theme — out of scope unless requested as a follow-up.
- No new data or content — purely a visual retheme of existing surfaces.
- No site-wide dark/light mode toggle. This is a fixed new theme for the Polling page only, not a user-togglable preference, and not a change to any other page's styling.
- No serif/editorial "newspaper" treatment — that direction was explicitly explored and ruled out in favor of glass. Sans-serif throughout, keep the existing `Inter` font.

## Proposed Approach
1. Add a small custom color token layer (`theme.extend.colors` in `tailwind.config.js`, or CSS variables in `index.css`) rather than continuing to hardcode Tailwind's stock `gray-*`/`red-*`/`blue-*` classes inline. Tokens needed: `glass-base` (pale lavender page bg, `#e9e3f6`), `glass-panel` (`rgba(255,255,255,0.55)`), `glass-panel-nested` (`rgba(255,255,255,0.4)`, for panels-within-panels), `glass-border` (`rgba(255,255,255,0.8)` / `0.7`), `ink` (`#241f33`, primary text), `ink-muted` (`#544a6e`, secondary text), and light-background-tuned data colors `poll-red` (`#a83c37` text / `#c0453f` bar fill) and `poll-blue` (`#2d5390` text / `#3763a8` bar fill) to replace the current dark-mode-tuned `red-400/600/900` and `blue-400/600/900` Tailwind defaults.
2. Swap `PollsPage.tsx`'s top-level wrapper (`bg-gray-950`) to `glass-base`.
3. Convert each panel-style surface across the 8 components (currently `bg-gray-900`/`bg-gray-950` rounded blocks) to the glass treatment: `background: glass-panel` (or `glass-panel-nested` for inner blocks), `backdrop-filter: blur(16px)`, `border: 1px solid glass-border`, `border-radius: 14–16px`, soft low-opacity shadow. Two visual tiers (outer card, inner stat block) mirror what was mocked up.
4. Swap text utilities (`text-white`, `text-gray-100/500/600/700`) for `ink`/`ink-muted` across all 8 components.
5. Recolor every red/blue data element — ballot margin text and bars in `GenericBallotBar.tsx`, the R/D bars and grade badges in `PollCarousel.tsx` — from the dark-tuned Tailwind defaults to `poll-red`/`poll-blue`.
6. Leave `body`'s global `bg-gray-950` in `index.css` untouched — every page (including this one) already sets its own explicit top-level background, so this stays scoped without a global change. Note the one known edge case: overscroll bounce at the top/bottom of the page may briefly show the dark body color behind the lavender page — acceptable, not blocking.
7. Apply `backdrop-filter` selectively rather than blanket — prioritize it on panels that sit over visually varied content (over the `DistrictMap` cartogram, over `PollCarousel` items) where the glass effect actually reads; verify manually that dense list rows (`RecentPollsList`) don't introduce scroll jank before deciding whether they get blur too.

## Open Questions / Risks
- Text contrast on ~50% translucent white panels depends on what's rendering behind them (varies with the district map's fill colors and scroll position) — need to check worst-case contrast, not just against the flat lavender base. Will become an acceptance criterion.
- `backdrop-filter` is GPU-cost — no perf harness in this repo, so this needs a manual check with the `DistrictMap` (SVG cartogram) and `PollCarousel` scrolling simultaneously before calling it done.
- `backdrop-filter` support is solid in current Chrome/Safari/Firefox; no graceful-degradation fallback is planned unless Samuel wants one for older browsers.
- Grade badges in `PollCarousel.tsx` (`B+`, `B`, `C-`, `D`) currently use dark badge fills (`bg-blue-900`, `bg-red-950`, etc.) — these need a light-background-appropriate treatment too, not just the R/D data colors.

## References
- Prior art / files to change: `frontend/src/index.css`, `frontend/tailwind.config.js`, `frontend/src/pages/PollsPage.tsx`, `frontend/src/components/{ForecastSection,GenericBallotBar,VoteHubApprovalCard,ApprovalSection,DistrictMap,PollCarousel,RecentPollsList,SourcesDisclosure}.tsx`
- Direction settled via in-conversation mockups (lavender liquid-glass, low opacity, sans-serif) — sage and blush were considered and set aside in favor of lavender.
