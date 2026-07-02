# Test Cases: Adopt Alembic Migrations

**Slug:** `alembic-migrations` &nbsp; **Source:** `02-acceptance-criteria.md`

All cases are manual today (no pytest harness at time of writing — if `test-harness-ci` lands first, TC-1/TC-4 are strong candidates for automation). Local cases use the docker-compose Postgres; create throwaway DBs with `createdb`/`dropdb` (or `CREATE DATABASE` via psql).

## Coverage Map
| AC | Test IDs |
|---|---|
| AC-1 | TC-1 |
| AC-2 | TC-2 |
| AC-3 | TC-5, TC-6 |
| AC-4 | TC-4 |
| AC-5 | TC-3 |
| AC-6 | TC-7 |

## Backend

### TC-1 — fresh DB builds to head with empty diff (covers AC-1)
- **Type:** integration (CLI)
- **Setup:** empty database `newsdb_mig1`; `DATABASE_URL` pointed at it
- **Steps:**
  1. From `backend/`: `alembic upgrade head`
  2. `alembic revision --autogenerate -m "should-be-empty"` and inspect the generated file
  3. Compare table list against a `create_all` DB (`\dt` in psql on both)
- **Expected Result:** upgrade succeeds; autogenerate emits no `op.` calls (empty upgrade/downgrade); table lists match. Delete the throwaway revision.
- **Automation note:** portable to `backend/tests/` as an "empty autogenerate diff" check once the harness exists

### TC-2 — stamp on an existing schema (covers AC-2)
- **Type:** integration (CLI)
- **Setup:** database `newsdb_mig2` built via the app's `create_all` (boot the app once against it), no `alembic_version` table
- **Steps:**
  1. `alembic stamp head`
  2. `alembic upgrade head`
  3. Check Postgres logs / `alembic upgrade head --sql` output
- **Expected Result:** stamp creates only the `alembic_version` row; upgrade is a no-op (no DDL); no errors
- **Automation note:** manual — this mirrors the one-time prod ops step; rehearse it here before doing it on prod

### TC-3 — postgres:// URL rewrite (covers AC-5)
- **Type:** unit-ish (CLI)
- **Setup:** `DATABASE_URL=postgres://newsuser:newspass@localhost:5432/newsdb_mig1` (note the `postgres://` prefix)
- **Steps:** run `alembic current`
- **Expected Result:** command succeeds and reports the revision — no SQLAlchemy dialect error. (Without the `env.py` fix this fails with "Can't load plugin: sqlalchemy.dialects:postgres".)
- **Automation note:** trivially automatable later

### TC-4 — model-change loop end-to-end (covers AC-4)
- **Type:** integration (CLI, throwaway branch)
- **Setup:** TC-1 database at head; a scratch git branch
- **Steps:**
  1. Add a nullable column to an existing model (e.g. `test_col = Column(String, nullable=True)` on `Trend`)
  2. `alembic revision --autogenerate -m "add test_col"` — inspect: exactly one `add_column`
  3. `alembic upgrade head`; verify column exists via psql `\d trends`
  4. `alembic revision --autogenerate` again — expect empty diff
  5. `alembic downgrade -1`; verify column gone; discard branch
- **Expected Result:** as per steps — the exact scenario `create_all` silently ignores now works
- **Automation note:** this is the drift-check pattern; candidate for CI per roadmap

## Deploy (Railway)

### TC-5 — migrations run before serve (covers AC-3)
- **Type:** manual (deploy verification)
- **Setup:** Procfile change deployed to Railway *after* prod has been stamped (implementation plan sequencing step 4 → 5)
- **Steps:** trigger a deploy; watch Railway logs
- **Expected Result:** log shows alembic running (and no-oping) before uvicorn starts; app healthy at `/health`
- **Automation note:** manual, per-deploy observation

### TC-6 — failed migration aborts deploy loudly (covers AC-3)
- **Type:** manual (staging-style rehearsal — use a scratch Railway service or local simulation, NOT prod)
- **Setup:** a deliberately broken migration (e.g. `op.execute("SELECT 1/0")`) on a scratch branch
- **Steps:** run the Procfile command (`alembic upgrade head && uvicorn ...`) against a local DB
- **Expected Result:** alembic exits nonzero, uvicorn never starts — the `&&` gate holds. Discard the migration.
- **Automation note:** local simulation is sufficient; don't rehearse on prod

## Docs

### TC-7 — workflow documented + template updated (covers AC-6)
- **Type:** manual (review)
- **Steps:** open the schema-changes doc section and `docs/features/_template/03-implementation-plan.md`
- **Expected Result:** workflow (autogenerate → review → same-PR commit) is documented; template contains the migration checklist line
- **Automation note:** n/a
