# Test Cases: Auth on Write Endpoints

**Slug:** `write-endpoint-auth` &nbsp; **Source:** `02-acceptance-criteria.md`

> Backend cases are automated pytest, following `backend/tests/`'s existing conventions (`client`/`db` fixtures from `conftest.py`, `monkeypatch.setenv` for `ADMIN_API_KEY` since the dependency reads it at call time). Frontend cases stay manual/click-through — no Vitest harness yet (separate, unshipped roadmap chore).

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
| (regression) | TC-10 |

## Backend

### TC-1 — Missing key rejected on both write routes (covers AC-1)
- **Type:** integration, `backend/tests/test_write_endpoint_auth.py`
- **Setup:** `monkeypatch.setenv("ADMIN_API_KEY", "test-secret")`; seed a `Candidate` row via the `db` fixture
- **Steps:**
  1. `client.post(f"/api/candidates/{candidate.id}/issues", json={"issue_code": "..."})` with no `X-Admin-Key` header
  2. `client.patch(f"/api/candidates/{candidate.id}/issues/{tag.id}", json={"confirmed": True})` with no header
- **Expected Result:** both return 401; querying `CandidateIssueTag` afterward shows no new/changed row

### TC-2 — Wrong key rejected (covers AC-2)
- **Type:** integration
- **Setup:** same as TC-1
- **Steps:** repeat both calls with `headers={"X-Admin-Key": "wrong-value"}`
- **Expected Result:** both 401, no data written

### TC-3 — Correct key succeeds, response unchanged (covers AC-3)
- **Type:** integration
- **Setup:** same as TC-1
- **Steps:** repeat both calls with `headers={"X-Admin-Key": "test-secret"}`
- **Expected Result:** both succeed (200) with the same response shape/behavior as before this feature — assert the tag is actually created/updated in the DB

### TC-4 — Unset `ADMIN_API_KEY` fails closed (covers AC-4)
- **Type:** integration
- **Setup:** `monkeypatch.delenv("ADMIN_API_KEY", raising=False)` (ensure it's genuinely unset for this test)
- **Steps:** call both write routes, once with no header and once with an arbitrary header value
- **Expected Result:** both attempts return 401 in both cases — misconfiguration never falls through to "allow all"

### TC-5 — `/api/refresh` still requires no key (covers AC-5)
- **Type:** integration
- **Steps:** `client.post("/api/refresh")` with no headers at all
- **Expected Result:** not a 401 — either 200 (queued) or, if a prior test in the same run tripped the cooldown, 429 (never 401), confirming this route was deliberately excluded from `require_admin_key`

### TC-6 — Rapid repeat `/api/refresh` calls hit the cooldown (covers AC-6)
- **Type:** integration
- **Steps:**
  1. `client.post("/api/refresh")` → expect 200
  2. Immediately `client.post("/api/refresh")` again
- **Expected Result:** second call returns 429; assert (via mock/spy on the background task, or a counter) that the refresh job was only queued once

### TC-7 — Cooldown clears after the window (covers AC-7)
- **Type:** integration, time-manipulated
- **Setup:** monkeypatch the cooldown constant to something small (e.g. patch `REFRESH_COOLDOWN_SECONDS` to 0.1s) or monkeypatch `datetime.now`/the module's clock function to advance time
- **Steps:**
  1. `client.post("/api/refresh")` → 200
  2. Advance time past the (shortened) cooldown window
  3. `client.post("/api/refresh")` again
- **Expected Result:** second call succeeds (200), not 429

### TC-10 — Existing unauthenticated GET routes unaffected (regression, covers Data Quality note)
- **Type:** integration
- **Steps:** `client.get("/api/candidates/issues/pending")`, `client.get("/api/candidates/taxonomy")`, `client.get("/api/debug/sources")`
- **Expected Result:** all still 200 with no header required — confirms `require_admin_key` was added only to the two intended routes, not accidentally broader

## Frontend

### TC-8 — AdminPage prompts for and attaches the key (covers AC-8)
- **Type:** manual/click-through
- **Steps:**
  1. Set `ADMIN_API_KEY` in the local backend `.env`, run `npm run dev`
  2. Navigate to the admin page (direct nav, since it's unlinked in `NAV_TABS`)
  3. Attempt to confirm or add an issue tag without having entered a key yet
- **Expected Result:** prompted for the key inline; after entering the correct value, the action succeeds; reloading the page and repeating requires re-entering the key (confirms it's memory-only, not persisted)
- **Automation note:** target `frontend/src/pages/AdminPage.test.tsx` with Vitest once that harness exists

### TC-9 — Wrong key in the UI surfaces a visible error (covers AC-9)
- **Type:** manual/click-through
- **Steps:** enter an incorrect key when prompted, attempt a write action
- **Expected Result:** a visible error message appears (not a silently-ignored click); the user is re-prompted for the key rather than the UI acting as if the write succeeded
- **Automation note:** same Vitest note as TC-8

## Edge Cases & Failure Modes
- `ADMIN_API_KEY` unset in any environment → both protected routes 401 unconditionally (TC-4)
- Header present but empty string → treated as wrong key, not as "no header" — should still 401 (worth asserting explicitly alongside TC-1/TC-2)
- Cooldown is in-memory/module-level → resets on app restart; not persisted, and that's intentional (noted in ACs, not a bug to chase)
- Key comparison uses `secrets.compare_digest`, not `==` — no dedicated test needed, but worth a code-review check during implementation rather than a runtime assertion (timing differences aren't practically testable in a unit test)

## Regression Check
- Existing `candidates.py` read routes (`GET /api/candidates`, `GET /{candidate_id}`, `/taxonomy`, `/issues/pending`) — unaffected (TC-10)
- Existing `test_routers_smoke.py` suite — should still pass unmodified
- `TrendsPage.tsx`'s public refresh button — still works for a normal (non-rapid-clicking) user; only rapid repeats are affected

## Sign-off
- [ ] All test cases pass (`pytest backend/tests/` for TC-1–TC-7, TC-10; manual click-through for TC-8/TC-9)
- [ ] Samuel has reviewed results before merge to main
