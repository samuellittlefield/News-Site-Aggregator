<!--
TEMPLATE: User Acceptance Criteria
File location once approved: news-site/docs/features/<slug>/02-acceptance-criteria.md
Derived from 01-feature-plan.md. Each criterion should be testable and map to a test case later.
-->

# Acceptance Criteria: <Feature Name>

**Slug:** `<slug>` &nbsp; **Source plan:** `01-feature-plan.md`

## Criteria

Number each one — test cases will reference these IDs (AC-1, AC-2, ...).

### AC-1: <short title>
- **Given** <starting state / precondition>
- **When** <action or trigger — API call, scheduler tick, user interaction>
- **Then** <observable, verifiable outcome>

### AC-2: <short title>
- **Given** ...
- **When** ...
- **Then** ...

<!-- Add as many as needed. -->

## Data Quality / Edge Cases
Criteria specific to this codebase's ingestion pattern — call out explicitly where relevant:
- What happens when the upstream source is unavailable or returns malformed data? (should degrade gracefully, not starve other sources)
- What happens on first run with an empty table vs. a re-run that should upsert, not duplicate?
- Any rate-limit or auth-failure behavior to verify?

## Out of Scope
Anything the feature plan explicitly excluded — restate here so it's not accidentally tested or implemented.

## Sign-off
- [ ] Samuel has reviewed and approved these criteria before implementation planning begins.
