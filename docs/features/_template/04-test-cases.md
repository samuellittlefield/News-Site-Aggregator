<!--
TEMPLATE: Test Cases
File location once approved: news-site/docs/features/<slug>/04-test-cases.md
Every case maps to an AC ID from 02-acceptance-criteria.md.
NOTE: backend has a pytest harness (`backend/tests/`, Postgres-backed, respx-mocked upstreams; see
`backend/README.md` and `docs/features/test-harness-ci/`). Backend cases should be added there.
Frontend still has no harness (Vitest is a future follow-up), so frontend cases stay manual for now.
-->

# Test Cases: <Feature Name>

**Slug:** `<slug>` &nbsp; **Source:** `02-acceptance-criteria.md`

## Coverage Map
| AC | Test IDs |
|---|---|
| AC-1 | TC-1, TC-2 |
| AC-2 | TC-3 |

## Backend

### TC-1 — <title> (covers AC-1)
- **Type:** integration (API route) / unit (service function)
- **Setup:** DB state, mocked upstream response, etc.
- **Steps:**
  1. ...
  2. ...
- **Expected Result:** ...
- **Automation note:** add to `backend/tests/` (pytest harness exists — Postgres `db`/`client` fixtures, respx-mocked upstreams; see `backend/README.md`).

### TC-2 — <title> (covers AC-1)
- **Type:** ...
- **Steps:** ...
- **Expected Result:** ...

## Frontend

### TC-3 — <title> (covers AC-2)
- **Type:** component / manual
- **Steps:**
  1. Run `npm run dev` in `frontend/`
  2. Navigate to <page>
  3. ...
- **Expected Result:** ...
- **Automation note:** target `frontend/src/**/*.test.tsx` with Vitest + React Testing Library once harness exists.

## Edge Cases & Failure Modes
- Upstream source down/malformed → scheduler job should log and continue, not crash other jobs
- Empty DB / first run → upsert doesn't error, doesn't duplicate on re-run
- Rate limit / auth failure → graceful degradation, surfaced in logs

## Regression Check
Existing features/routes that could be affected by this change — list them so they get a manual smoke check before merge.

## Sign-off
- [ ] All test cases pass
- [ ] Samuel has reviewed results before merge to main
