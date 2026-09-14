---
name: Implement polling-page-glass-theme
runs: 3
max_turns: 25
timeout_seconds: 900
allowed_tools: [Bash, Write, Edit, Read, Grep, Glob]
model: claude-3-5-sonnet-20241022
---
Read docs/features/polling-page-glass-theme/01-feature-plan.md,
02-acceptance-criteria.md, and 03-implementation-plan.md.

Implement the feature they describe: retheme the Polling page from its
flat dark neutral surfaces to the lavender liquid-glass treatment,
scoped exactly as the acceptance criteria specify (in scope: the Polling
page and the components it exclusively renders; out of scope: the
Dashboard and every other page).

When you believe the acceptance criteria are met, run `npm run build`
inside frontend/ and confirm it succeeds before finishing.
