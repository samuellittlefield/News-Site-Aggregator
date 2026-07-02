# Acceptance Criteria: Adopt Alembic Migrations

**Slug:** `alembic-migrations` &nbsp; **Source plan:** `01-feature-plan.md`

## Criteria

### AC-1: baseline migration builds the full schema
- **Given** a fresh, empty Postgres database
- **When** `alembic upgrade head` is run from `backend/`
- **Then** all ~23 tables exist with columns, constraints, and indexes matching `models.py` — verified by `alembic revision --autogenerate` immediately afterwards producing an empty diff

### AC-2: existing databases are stamped, not re-migrated
- **Given** a database that already has the full schema but no `alembic_version` table (i.e. today's prod)
- **When** `alembic stamp head` is run once, then `alembic upgrade head`
- **Then** the stamp records the baseline as applied and the upgrade is a no-op — no DDL executed, no errors

### AC-3: deploys run migrations before serving traffic
- **Given** the updated `Procfile`
- **When** a Railway deploy starts
- **Then** `alembic upgrade head` completes before uvicorn binds; a failing migration aborts the deploy (app never starts on a half-migrated schema)

### AC-4: the model-change loop works end-to-end
- **Given** a model edit (e.g. a new nullable column on an existing table — exactly the case `create_all` silently ignores)
- **When** `alembic revision --autogenerate` is run, the migration reviewed and applied via `upgrade head`
- **Then** the column exists in the database and a subsequent autogenerate produces an empty diff

### AC-5: postgres:// URLs work in Alembic
- **Given** `DATABASE_URL` set to a `postgres://`-prefixed URL (Railway's format)
- **When** any alembic command runs
- **Then** it succeeds — `alembic/env.py` applies the same `postgres://` → `postgresql://` rewrite `database.py` already does (today it does not, which would crash on Railway)

### AC-6: documentation and pipeline updated
- **Given** the shipped feature
- **When** a future feature touches `models.py`
- **Then** the developer-facing workflow (autogenerate → review → commit migration in the same PR) is documented in the repo, and `docs/features/_template/03-implementation-plan.md` carries an explicit migration checklist line

## Data Quality / Edge Cases
- **JSONB defaults**: autogenerate is known to mis-render `JSONB` columns and lambda defaults (e.g. `Trend.sources_list`) — the baseline must be hand-reviewed against a real `create_all` schema, not trusted blind.
- **Latent drift**: before stamping prod, diff prod's actual schema against models; any existing drift becomes revision 002, not a surprise.
- **Failure mode shift**: a bad migration now blocks deploys loudly (intended). Verify the failure is visible in Railway logs and the previous release keeps serving.

## Out of Scope
Data migrations/backfills, guaranteed downgrade paths, migration-drift CI checks (deferred to roadmap; depends on `test-harness-ci`), and changing test fixtures away from `create_all` (per both feature plans).

## Sign-off
- [x] Samuel has reviewed and approved these criteria (outline-level sign-off, 2026-07-02).
