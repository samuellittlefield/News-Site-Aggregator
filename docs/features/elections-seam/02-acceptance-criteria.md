# Acceptance Criteria: Draw the Backend Elections/Monitor Seam

**Slug:** `elections-seam` &nbsp; **Source plan:** `01-feature-plan.md`

## Criteria

### AC-1: Routers and services are grouped into three bounded packages
- **Given** the flat `backend/app/routers/` (14 modules) and `backend/app/services/` (33 modules)
- **When** the refactor is complete
- **Then** every module lives under exactly one of `app/elections/`, `app/monitor/` or `app/shared/`, each with its own `routers/` and `services/` subpackage, and no module remains at the old flat path

### AC-2: No API surface changes
- **Given** the live route table before the change
- **When** the refactored app starts
- **Then** `GET /openapi.json` lists exactly the same paths, methods and response schemas as before — no URL, no status code, no field added, removed or renamed

### AC-3: `models.py` becomes a package, single `Base` preserved
- **Given** 25 model classes in one 445-line `models.py`
- **When** the split is complete
- **Then** classes live in `app/models/elections.py` (11), `app/models/monitor.py` (12) and `app/models/shared.py` (2), all three import the same `Base` from `app.database`, and `app/models/__init__.py` re-exports every class

### AC-4: Existing import paths keep working
- **Given** call sites throughout the app and test suite using `from app.models import HousePoll`
- **When** the model package replaces the module
- **Then** every such import resolves unchanged, with no call-site edits required for model imports specifically

### AC-5: Alembic sees no schema change
- **Given** the database at head revision `d4e5f6a7b8c9`
- **When** `alembic revision --autogenerate` runs against the refactored models
- **Then** the generated migration body is empty — no `create_table`, `drop_table`, `add_column`, `drop_column` or `alter_column` operations

### AC-6: Existing migrations still run from scratch
- **Given** an empty database
- **When** `alembic upgrade head` runs against the refactored codebase
- **Then** all four existing migrations apply cleanly and the resulting schema matches the pre-refactor schema

### AC-7: The boundary is enforced, not merely organized
- **Given** the refactored package layout
- **When** the boundary test runs
- **Then** it passes on the current tree, and **fails** when a deliberate `from app.monitor...` import is added to any `app/elections/**` module, or the reverse

### AC-8: `shared/` contains only domain-free code
- **Given** the classification decisions in the feature plan
- **When** the refactor is complete
- **Then** `app/shared/` holds the status router, `service_status`, `source_run` and `topic_matcher`, and nothing in `app/shared/**` imports from `app/elections/**` or `app/monitor/**`

### AC-9: The scheduler still registers all 17 jobs
- **Given** `scheduler.py` with 17 registered jobs and 17 `SOURCE_CADENCE` entries
- **When** the app starts after the refactor
- **Then** the same 17 job ids are registered with the same cadences and the same callables — import paths are the only change in this file

### AC-10: The existing test suite passes unchanged in substance
- **Given** the 11 test modules in `backend/tests/`
- **When** `pytest` runs after the refactor
- **Then** every test passes, with changes limited to import paths — no test assertion, fixture behaviour or expected value is modified to accommodate the refactor

### AC-11: Startup behaviour is unchanged
- **Given** `main.py`'s `_startup_refresh` and `_do_full_refresh`
- **When** the app starts with `DISABLE_SCHEDULER` unset
- **Then** the same refresh steps run in the same order with the same timeout budgets, and `DISABLE_SCHEDULER=1` still suppresses both the scheduler and the startup refresh

## Data Quality / Edge Cases

This is a structural refactor, not an ingestion feature — the template's upstream-failure
questions don't apply directly. The equivalent risks:

- **Silent partial move.** A module moved but still reachable at its old path (stale
  `.pyc`, a leftover shim) would let the boundary test pass while the seam is
  incomplete. AC-1 must verify old paths are *gone*, not merely that new ones exist.
- **Circular imports.** Grouping into packages can surface import cycles that the flat
  layout hid. The app importing successfully and the suite passing is the check.
- **Upsert and failure-isolation semantics must be untouched.** No `fetch_*` function's
  body changes in this ticket, so existing idempotency and per-source try/except
  behaviour carries over by construction. Any diff inside a service body is out of scope
  and should be rejected in review.
- **No rate-limit or auth behaviour changes.** `require_admin_key` continues to gate the
  same two candidate issue-tag routes.

## Out of Scope

Restated from the feature plan so none of it gets tested or implemented here:

- Splitting the scheduler into job groups (T2, `scheduler-split`)
- Second database, second Alembic history, second deploy (T4, T5b)
- Any frontend change (T3)
- Any route URL, response shape, table or column change
- Final placement of `ServiceStatus` / `SourceRun` / Astronomy (T6 decides; `shared/` is a holding position)
- Renaming the product, or choosing the polling app's public name

## Sign-off
- [ ] Samuel has reviewed and approved these criteria before implementation planning begins.
