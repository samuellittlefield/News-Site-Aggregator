# Implementation Plan: Polling Page Liquid Glass Theme

**Slug:** `polling-page-glass-theme` &nbsp; **Source:** `01-feature-plan.md`, `02-acceptance-criteria.md`

## Summary
Add a small custom color token layer to `tailwind.config.js`, then swap `PollsPage.tsx` and its 8 child components off the stock `gray-*`/`red-*`/`blue-*` classes onto the new `glass-*`/`ink`/`poll-*` tokens with `backdrop-filter` blur on panel surfaces. Pure frontend CSS/markup change — no backend, API, or data model touched.

**Scope call-out found during this pass, resolved with Samuel:** the feature plan and AC-3/AC-4 named red/blue data and grade badges specifically. Grepping all 8 components turned up additional accent colors riding on the same dark-tuned Tailwind defaults that weren't discussed in the mockups: `emerald-400`/`green-400` (net-approval positive values, `VoteHubApprovalCard.tsx` + `ApprovalSection.tsx`), `amber-700/300/950` (the "tuning" state badge in `ForecastSection.tsx`), and `purple-400`/`violet-900/300` (Independent bar in `ApprovalSection.tsx`, approval-poll badge in `RecentPollsList.tsx`). Decision: keep each color's identity, retune to the equivalent Tailwind light-mode register (same move as `poll-red`/`poll-blue`) rather than inventing new hues. Final values:
- `poll.positive`: `#047857` (emerald-700) — unifies the two existing green/emerald "net positive" usages into one token.
- `poll.amber`: text `#b45309` (amber-700) / bg `#fef3c7` (amber-100) / border `#fcd34d` (amber-300) — for the `ForecastSection.tsx` tuning badge.
- `poll.purple`: bar fill `#9333ea` (purple-600) / badge text `#7e22ce` (purple-700) / badge bg `#f3e8ff` (purple-100).
- Grade badges (`PollCarousel.tsx`): same mechanical swap, each existing `bg-{color}-900/text-{color}-300` dark pairing → the equivalent `bg-{color}-100/text-{color}-700` light pairing, no new hues needed.

## Frontend Changes

| File | Change |
|---|---|
| `frontend/tailwind.config.js` | Add `theme.extend.colors`: `glass: { base: "#e9e3f6", panel: "rgba(255,255,255,0.55)", "panel-nested": "rgba(255,255,255,0.4)", border: "rgba(255,255,255,0.8)", "border-soft": "rgba(255,255,255,0.7)" }`, `ink: { DEFAULT: "#241f33", muted: "#544a6e" }`, `poll: { red: "#a83c37", "red-bar": "#c0453f", blue: "#2d5390", "blue-bar": "#3763a8", positive: "#047857", amber: "#b45309", "amber-bg": "#fef3c7", "amber-border": "#fcd34d", purple: "#7e22ce", "purple-bar": "#9333ea", "purple-bg": "#f3e8ff" }`. |
| `frontend/src/index.css` | No change to `body` (stays `bg-gray-950 text-gray-100` — other pages keep the dark theme, per AC-7). Optionally add a `.glass-panel` utility class via `@layer components` if the blur/border/shadow combo proves too repetitive as inline Tailwind classes across 8 files — decide during implementation, not required. |
| `frontend/src/pages/PollsPage.tsx` | `min-h-screen bg-gray-950` → `min-h-screen bg-glass-base`. `text-white`, `text-gray-500` in the header block → `text-ink`, `text-ink-muted`. Both `animate-pulse` skeleton placeholders (`bg-gray-900 rounded-xl`, lines ~50/60) → glass-consistent placeholder (`bg-glass-panel-nested`, no blur needed on a pulse skeleton). |
| `frontend/src/components/ForecastSection.tsx` | Panel shells (`bg-gray-900 border border-gray-800 rounded-xl`, lines 41 and 166) → `bg-glass-panel backdrop-blur-md border border-glass-border rounded-2xl shadow-[0_4px_16px_rgba(74,61,112,0.08)]`. `text-blue-400`/`text-red-400` (line 48) → `text-poll-blue`/`text-poll-red`. `bg-blue-500`/`bg-red-500` bars (58–59) → `bg-poll-blue-bar`/`bg-poll-red-bar`. All `text-gray-400/500/600/700/300` labels → `text-ink-muted` (or `text-ink` where currently `gray-300`, the more prominent stops). Amber "tuning" badge (line 189) → `text-poll-amber bg-poll-amber-bg border-poll-amber-border`. |
| `frontend/src/components/VoteHubApprovalCard.tsx` | Skeleton (line 9) and panel shell (line 22) same swap as above. `text-red-400`/`text-emerald-400` (line 30) → `text-poll-red`/`text-poll-positive`. Remaining `text-gray-400/600` → `text-ink-muted`. |
| `frontend/src/components/ApprovalSection.tsx` | Sticky-column cells `bg-gray-950` (lines 93/102/112) → `bg-glass-panel` (sticky cells need an opaque-enough backdrop to stay legible while the table scrolls under them — verify during implementation, may need a higher-opacity variant than the standard panel). `text-green-400`/`text-red-400` (line 181, 189) → `text-poll-positive`/`text-poll-red`. `bg-blue-500`/`bg-purple-400`/`bg-red-500` (line 207) → `bg-poll-blue-bar`/`bg-poll-purple-bar`/`bg-poll-red-bar`. Panel shells (`border border-gray-800 rounded-xl`, lines 176/232) → full glass treatment. Remaining `text-gray-*` → `text-ink`/`text-ink-muted` per weight. |
| `frontend/src/components/DistrictMap.tsx` | Panel/loading shells (`bg-gray-900 border-gray-800`, lines 127/228) → glass treatment. UI chrome (`text-gray-*`, lines throughout) → `text-ink`/`text-ink-muted`. **Leave `leanColor()` (line 20) and `partyColor()` (line 36) hex values as-is for now** — these are the choropleth's actual data-ink (diverging blue/red presidential-margin scale), not UI chrome, and weren't part of the mockup exploration. Verify legibility once the panel around it is glass/light (dark saturated fills like `#1e3a8a`/`#991b1b` should still read fine on a light backdrop; the neutral midpoint `#4b5563` is the one worth a second look) — flag as a manual check, not a planned change. |
| `frontend/src/components/PollCarousel.tsx` | Grade badge map (lines 7–13: `bg-blue-900/text-blue-300/border-blue-700` etc.) → four retuned light-bg badge pairings, one per grade, keeping blue-family for B+/B and red-family for C-/D per the existing pattern. R/D bars (36–37, 68–69) → `bg-poll-red-bar`/`bg-poll-blue-bar`. Margin/R/D text (40–41, 44, 72–73, 76) → `text-poll-red`/`text-poll-blue`. |
| `frontend/src/components/RecentPollsList.tsx` | Row shell (line 13: `bg-gray-900 border border-gray-800 rounded-lg`) → glass treatment, **flat (no blur) per AC-6** unless the manual perf check clears blur for this list. Approval-vs-generic badge (line 15: `bg-violet-900/50 text-violet-300` / `bg-blue-900/50 text-blue-300`) → `bg-poll-purple-bg text-poll-purple` / `bg-blue-100 text-poll-blue`. `text-red-400`/`text-blue-400` (33, 37, 39) → `text-poll-red`/`text-poll-blue`. Remaining `text-gray-*` → `text-ink-muted`. |
| `frontend/src/components/SourcesDisclosure.tsx` | Panel shell (line 54: `border border-gray-800 rounded-xl`) → glass treatment. `text-gray-*` (throughout) → `text-ink`/`text-ink-muted`. Lowest-risk file in the set — no data colors, text and one container only. |
| `frontend/src/components/GenericBallotBar.tsx` | (Referenced in feature plan/AC-3 — confirm current file state before editing, wasn't re-grepped in this pass; apply the same `poll-red`/`poll-blue` swap on its margin text and R/D bars as `PollCarousel.tsx`'s bottom section, which shares near-identical markup.) |

## Data Model / Migration Notes
None — no schema, model, or API changes.

## Sequencing
1. Add the `glass`/`ink`/`poll` token set to `tailwind.config.js`. Confirm the retuned amber/positive/purple values (scope call-out above) before wiring components, so it's one pass per file rather than two.
2. `PollsPage.tsx` — swap the top-level background and skeletons first, so the page is visibly on the new base while the rest is still mid-migration (easier to eyeball progress).
3. Lowest-risk components first to validate the glass panel pattern before touching data-color logic: `SourcesDisclosure.tsx`, then `RecentPollsList.tsx` (flat, no blur, per AC-6).
4. Data-color components: `GenericBallotBar.tsx`, `PollCarousel.tsx`, `VoteHubApprovalCard.tsx`, `ApprovalSection.tsx`, `ForecastSection.tsx` — swap panel shells and every red/blue/amber/positive/purple reference together per file.
5. `DistrictMap.tsx` last — it's the most visually complex surface (SVG cartogram + glass chrome) and the one place with a manual legibility check on existing data-ink colors, not just token swaps.
6. Manual QA pass against every AC: contrast over worst-case backgrounds (AC-5), scroll perf with `RecentPollsList` + `DistrictMap` both on screen (AC-6), and a side-by-side check that Dashboard is unchanged (AC-7).

## Documentation Updates
- [ ] `SOURCES.md` — not needed, no data source added/changed.
- [ ] `.env.example` — not needed, no new env vars/secrets.

## Risks / Rollback
No migration, no route, no data touched — rollback is reverting the component diffs and the `tailwind.config.js` token additions, nothing to clean up. Main real risks are the ones already named in the feature plan and baked into AC-5/AC-6: contrast on translucent panels over varied backgrounds, and `backdrop-filter` scroll performance. The secondary-accent values (positive/amber/purple) are resolved per the scope call-out above — Samuel signed off on the light-mode-equivalent approach during implementation planning.

## Test Plan Pointer
See `04-test-cases.md`.
