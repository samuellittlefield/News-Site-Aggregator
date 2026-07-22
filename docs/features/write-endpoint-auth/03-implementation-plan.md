# Implementation Plan: Auth on Write Endpoints

**Slug:** `write-endpoint-auth` &nbsp; **Source:** `01-feature-plan.md`, `02-acceptance-criteria.md`

## Summary
Add a `require_admin_key` FastAPI dependency that checks an `X-Admin-Key` header against `ADMIN_API_KEY` (read at call time, not import time, so tests can vary it), apply it to the two candidate issue-tag write routes, add an in-memory cooldown to `/api/refresh` instead, and update `AdminPage.tsx` to prompt for and attach the key.

## Backend Changes
*(Python 3.9 — use `Optional[...]`, not `X | Y`)*

| File | Change |
|---|---|
| `backend/app/auth.py` | New. `require_admin_key(x_admin_key: str = Header(None, alias="X-Admin-Key")) -> None` — reads `os.getenv("ADMIN_API_KEY")` inside the function body (not at module load), raises `HTTPException(401)` if the env var is unset (AC-4, fail closed) or if the header doesn't match via `secrets.compare_digest` (AC-2, constant-time per the ACs' edge-case note) |
| `backend/app/routers/candidates.py` | Add `Depends(require_admin_key)` to `add_issue_tag` (line ~158) and `update_issue_tag` (line ~184) — additive to the existing `Depends(get_db)`, no signature changes otherwise |
| `backend/app/main.py` | Add a simple in-memory cooldown to `POST /api/refresh` (`manual_refresh`, line ~138): a module-level `_last_refresh_at: Optional[datetime]` guarded by cooldown length (e.g. `REFRESH_COOLDOWN_SECONDS`, a constant — no new env var needed unless you want it configurable); reject with `429` if called again inside the window, otherwise proceed exactly as today and update the timestamp |
| `backend/.env.example` | Add `ADMIN_API_KEY=` (mirrors the existing `FEC_API_KEY` gap noted in roadmap chores) |

Note: no new upstream API, no new data model, no migration — this is pure application-layer, doesn't touch `SOURCES.md`'s ingestion pattern.

## Frontend Changes
| File | Change |
|---|---|
| `frontend/src/api/client.ts` | `confirmTag`, `rejectTag`, `addManualTag` each attach an `X-Admin-Key` header, sourced from a small in-memory holder (e.g. a module-level variable set by `AdminPage`, not React state passed through every call site) — must not touch `localStorage`/`sessionStorage` per AC-8 |
| `frontend/src/pages/AdminPage.tsx` | On first write attempt without a stored key, prompt (a simple inline password-style input is enough for v1) for the admin key, hold it in memory for the session; on a 401 response from any write call, surface a visible error and clear/re-prompt for the key (AC-9) rather than failing silently |

`POST /api/refresh` (`TrendsPage.tsx`, `triggerRefresh()`) is unchanged on the frontend — no key involved, just may now occasionally get a 429 if clicked rapidly; worth a light client-side disable-while-cooling-down for UX, though not required by the ACs.

## Data Model / Migration Notes
None — no schema changes, no migration.

## Sequencing
1. `backend/app/auth.py` (`require_admin_key`)
2. Wire into `candidates.py`'s two write routes
3. `/api/refresh` cooldown in `main.py`
4. `.env.example` update
5. Frontend: `client.ts` header plumbing → `AdminPage.tsx` prompt/error handling
6. Tests (per `04-test-cases.md`)

## Documentation Updates
- [ ] `.env.example` — `ADMIN_API_KEY=` added
- [ ] `SOURCES.md` — not applicable, no data source changed
- [ ] Consider a one-line note in `backend/README.md` (if one exists) on setting `ADMIN_API_KEY` locally to use the admin UI — check during implementation

## Risks / Rollback
- Fail-closed default (AC-4) means if `ADMIN_API_KEY` isn't set in any environment (including a fresh local checkout), the two candidate write endpoints 401 until it's set — expected and desired, but worth a clear error message so it's not mistaken for a bug.
- Rollback is trivial: remove the two `Depends(require_admin_key)` calls and the cooldown check — no data or migration to reverse.
- Low risk to other endpoints: `require_admin_key` is additive per-route, not global middleware, so nothing else is affected by construction.

## Test Plan Pointer
See `04-test-cases.md`. All backend cases are automatable now via the existing `backend/tests/` pytest harness (`client`/`db` fixtures) — use `monkeypatch.setenv("ADMIN_API_KEY", ...)` per test since the dependency reads the env var at call time, not import time.
