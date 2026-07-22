# Acceptance Criteria: Auth on Write Endpoints

**Slug:** `write-endpoint-auth` &nbsp; **Source plan:** `01-feature-plan.md`

## Criteria

### AC-1: Missing key is rejected
- **Given** `ADMIN_API_KEY` is set in the environment
- **When** `POST /api/candidates/{id}/issues` or `PATCH /api/candidates/{id}/issues/{tag_id}` is called with no `X-Admin-Key` header
- **Then** the request is rejected with `401 Unauthorized` and no data is written (no `CandidateIssueTag` row created/modified)

### AC-2: Wrong key is rejected
- **Given** `ADMIN_API_KEY` is set
- **When** either endpoint is called with an `X-Admin-Key` header that doesn't match
- **Then** `401 Unauthorized`, no data written

### AC-3: Correct key succeeds, existing behavior unchanged
- **Given** `ADMIN_API_KEY` is set
- **When** either endpoint is called with the matching `X-Admin-Key` header
- **Then** the request succeeds exactly as it does today (200, tag created/updated) — the dependency adds a gate, it doesn't change response shape or business logic

### AC-4: Unset `ADMIN_API_KEY` fails closed
- **Given** the `ADMIN_API_KEY` environment variable is not set at all (e.g. forgotten in a deploy)
- **When** either protected endpoint is called, with or without a header
- **Then** the request is rejected (401) rather than silently allowing all requests through — misconfiguration must fail safe, not fail open

### AC-5: `/api/refresh` requires no key (unaffected by auth)
- **Given** the feature's decision to leave `/api/refresh` public
- **When** `POST /api/refresh` is called with no header at all
- **Then** it is accepted (no 401) — confirms this endpoint is deliberately excluded from the `require_admin_key` dependency, not accidentally missed

### AC-6: `/api/refresh` cooldown blocks rapid repeats
- **Given** `POST /api/refresh` was just called successfully
- **When** it's called again within the cooldown window
- **Then** the second call is rejected (e.g. `429 Too Many Requests`) without queuing another full refresh — the background refresh task is not started twice concurrently

### AC-7: `/api/refresh` cooldown clears after the window
- **Given** the cooldown window has fully elapsed since the last accepted call
- **When** `POST /api/refresh` is called again
- **Then** it's accepted and queues a new refresh, same as today's behavior

### AC-8: AdminPage prompts for and attaches the key
- **Given** a user opens `AdminPage.tsx` (e.g. via direct navigation, since it's unlinked) and has not yet entered a key this session
- **When** they attempt a write action (confirm/reject/add a tag)
- **Then** they're prompted to enter the admin key once; it's held in memory (React state) only — not written to `localStorage`/`sessionStorage` — and attached as the `X-Admin-Key` header on that and subsequent write calls in the same session

### AC-9: Wrong key entered in the UI surfaces a clear error, not a silent failure
- **Given** the user enters an incorrect key in `AdminPage`
- **When** a write call comes back 401
- **Then** the UI shows a visible error (not a swallowed/silent failure) and re-prompts for the key, rather than leaving the user thinking the action succeeded

## Data Quality / Edge Cases
- Cooldown state is in-memory (module-level), so it resets on every deploy/restart — acceptable per the feature plan's low-stakes threat model; explicitly not a goal to persist it across restarts.
- The key comparison should not be vulnerable to trivial timing shortcuts (e.g. use a constant-time compare like `secrets.compare_digest` rather than `==`) — cheap to do right the first time, worth calling out even for a low-stakes secret.
- Existing unauthenticated `GET` endpoints (including `/api/candidates/issues/pending`, `/api/candidates/taxonomy`, and the debug-only `GET /api/debug/sources` found during planning) are explicitly untouched by this feature — confirm no regressions there.

## Out of Scope
- Auth on `/api/refresh` itself (cooldown only, per feature plan decision).
- Gating the `AdminPage` frontend route/page itself (separate from the backend calls it makes) — flagged as a possible fast-follow in the feature plan, not this v1.
- Full user accounts, key rotation, rate limiting beyond the one cooldown.

## Sign-off
- [ ] Samuel has reviewed and approved these criteria before implementation planning begins.
