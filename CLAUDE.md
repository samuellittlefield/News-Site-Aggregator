# Project conventions

## Merging

Once a feature's tests pass and CI is green on the PR, merge it to `main` yourself —
don't stop and wait for explicit confirmation to merge. Opening the PR and getting
CI green is not "done"; the feature isn't shipped until it's merged. If CI is still
running when you finish your turn, that's fine — just merge as soon as it goes green,
even if that means picking the PR back up in a later session.

The one exception: if something in the diff feels like it needs a second pair of
eyes before it hits `main` (a schema change you're unsure about, a security-relevant
decision, anything you'd flag in a real PR review), say so and wait — don't
auto-merge past your own uncertainty.

After merging, update `docs/ROADMAP.md` (status → shipped, with the PR link) as
part of the same piece of work, not a separate follow-up.

## Feature specs

Planning for new features happens in Cowork, not here — specs land in
`docs/features/<slug>/` as four docs (feature plan, acceptance criteria,
implementation plan, test cases) before implementation starts. Read all four
before writing code. `docs/ROADMAP.md` is the single tracking surface for what's
planned/in-progress/shipped.
