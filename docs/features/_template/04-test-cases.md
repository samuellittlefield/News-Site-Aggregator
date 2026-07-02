<!--
TEMPLATE: Test Cases
File location once approved: news-site/docs/features/<slug>/04-test-cases.md
Every case maps to an AC ID from 02-acceptance-criteria.md.
NOTE: this repo has no test harness configured yet (no pytest/vitest found). Cases below are written
to be runnable manually today, and portable to automated tests once a harness exists.
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
- **Automation note:** target `backend/tests/` with pytest once harness exists; until then, run manually via `uvicorn` + curl or the FastAPI docs UI.

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
