# Test Cases: Draw the Backend Elections/Monitor Seam

**Slug:** `elections-seam` &nbsp; **Source:** `02-acceptance-criteria.md`

All cases are automatable against the existing pytest harness (`backend/tests/`,
`pytest.ini`, `newsdb_test` auto-created by `conftest.py`, autouse respx network
guard). No manual-only cases in this ticket except TC-8, which touches Alembic
against a scratch database.

## Coverage Map

| AC | Test IDs |
|---|---|
| AC-1 Packages | TC-1, TC-2 |
| AC-2 No API change | TC-3 |
| AC-3 Model split, one `Base` | TC-4, TC-5 |
| AC-4 Import paths work | TC-6, TC-7 |
| AC-5 Empty autogenerate | TC-8 |
| AC-6 Migrations run clean | TC-9 |
| AC-7 Boundary enforced | TC-10, **TC-11** |
| AC-8 `shared/` is domain-free | TC-12 |
| AC-9 17 jobs unchanged | TC-13 |
| AC-10 Suite passes | TC-14 |
| AC-11 Startup unchanged | TC-15 |

## Backend

### TC-1 — Old flat paths no longer resolve (covers AC-1)
- **Type:** unit
- **Steps:** `importlib.util.find_spec("app.routers.polls")` and
  `find_spec("app.services.house_polls")`, plus one more from each old directory.
- **Expected:** every lookup returns `None`, and `app/routers/` and `app/services/`
  do not exist on disk.
- **Note:** clear `__pycache__` before running — a stale `.pyc` can make a deleted
  module look importable and turn this test green for the wrong reason.

### TC-2 — Every module has exactly one home (covers AC-1)
- **Type:** unit
- **Steps:** walk `app/elections`, `app/monitor`, `app/shared`; collect module
  basenames per subpackage.
- **Expected:** routers 6 / 6 / 1 and services 10 / 21 / 3, matching the plan's
  table exactly; no basename appears in two packages.

### TC-3 — OpenAPI surface is byte-identical (covers AC-2)
- **Type:** integration
- **Setup:** capture `GET /openapi.json` from `main` **before** the refactor, commit
  it as `backend/tests/fixtures/openapi_baseline.json`.
- **Steps:** start `TestClient`, fetch `/openapi.json`, compare paths, methods and
  component schemas against the fixture.
- **Expected:** no added, removed or renamed path, method, status code or schema
  field. Ordering differences are acceptable; content differences are not.

### TC-4 — Model classes are distributed correctly (covers AC-3)
- **Type:** unit
- **Steps:** import the three modules; assert class counts and membership.
- **Expected:** `elections` 11, `monitor` 12, `shared` 2 — exactly the classes named
  in the plan, and 25 total.

### TC-5 — Exactly one `Base` (covers AC-3)
- **Type:** unit
- **Steps:** assert `elections.Base is monitor.Base is shared.Base is base.Base`;
  assert `len(Base.metadata.tables) == 25`.
- **Expected:** all four are the same object. **This is the test that catches the
  ticket's main failure mode** — three modules each calling `declarative_base()`
  would pass TC-4 and fail here.

### TC-6 — Model imports still resolve (covers AC-4)
- **Type:** unit
- **Steps:** `from app.models import <each of the 25 class names>`.
- **Expected:** all resolve; each is the same object as the one in its submodule.

### TC-7 — `from app.models import Base` resolves (covers AC-4)
- **Type:** unit
- **Steps:** import `Base` from `app.models`; assert it is `app.models.base.Base`.
- **Expected:** resolves. `alembic/env.py` line 23 depends on this exact import for
  `target_metadata`; forgetting `Base` in `__init__.py`'s re-export breaks every
  migration while leaving TC-6 green.

### TC-8 — Autogenerate produces an empty diff (covers AC-5)
- **Type:** integration (CI step)
- **Setup:** scratch database at head revision `d4e5f6a7b8c9`.
- **Steps:** `alembic upgrade head`, then
  `alembic revision --autogenerate -m drift-check`, then inspect the generated file.
- **Expected:** no `op.create_table`, `op.drop_table`, `op.add_column`,
  `op.drop_column` or `op.alter_column` in the output. Delete the generated file
  afterwards so it never lands in `versions/`.

### TC-9 — Migrations still run from empty (covers AC-6)
- **Type:** integration
- **Steps:** drop and recreate an empty database; `alembic upgrade head`.
- **Expected:** all four migrations apply cleanly; resulting table and column set
  matches the pre-refactor schema.

### TC-10 — Boundary test passes on the clean tree (covers AC-7)
- **Type:** unit
- **Steps:** run `test_module_boundaries.py` against the refactored tree.
- **Expected:** passes. Uses `ast.parse` to read imports statically — it must not
  execute module bodies.

### TC-11 — Boundary test FAILS on a deliberate violation (covers AC-7)
- **Type:** unit (negative)
- **Steps:** add `from app.monitor.services import trends` to any `app/elections/**`
  module; run the boundary test; revert.
- **Expected:** **the test fails**, naming the offending module and the import.
  A boundary test that cannot fail proves nothing, so this case is not optional.

### TC-12 — `shared/` depends on neither domain (covers AC-8)
- **Type:** unit
- **Steps:** AST-scan every module under `app/shared/`.
- **Expected:** no import of `app.elections.*` or `app.monitor.*`. Confirms
  `topic_matcher` really is domain-free rather than assumed to be.

### TC-13 — Scheduler registration is unchanged (covers AC-9)
- **Type:** unit
- **Steps:** call `start_scheduler()` with a stub scheduler; collect
  `(id, trigger interval)` pairs.
- **Expected:** the same 17 ids with the same intervals as before the refactor, and
  the set matches `SOURCE_CADENCE` keys (the existing TC-7 from `ingestion-health`).

### TC-14 — Full existing suite passes (covers AC-10)
- **Type:** integration
- **Steps:** `pytest -v` across all 11 existing modules.
- **Expected:** all pass. **Review the diff on `backend/tests/`** — every changed
  line must be an import path. A changed assertion or expected value means the
  refactor altered behaviour and the ticket has failed its premise.

### TC-15 — Startup behaviour is unchanged (covers AC-11)
- **Type:** integration
- **Steps:** (a) with `DISABLE_SCHEDULER=1`, start under `TestClient` and assert no
  jobs register and no startup refresh fires; (b) with it unset and refresh
  functions patched, assert `_startup_refresh` calls the same 15 steps in the same
  order with the same timeout values.
- **Expected:** both hold. (a) is what the entire suite depends on.

## Frontend

**No frontend test cases.** This ticket touches no file under `frontend/`. CI's
existing `npm ci` + build job is the only frontend check needed, and it should pass
untouched.

## Edge Cases & Failure Modes

- **Runtime-only imports.** A deferred `import` inside a function body won't be seen
  by the AST boundary scan or by module-level import tests. Before merge, grep for
  indented `import` statements across the moved modules, and smoke one route per
  domain (`/api/polls/generic-ballot`, `/api/trends`, `/api/status/sources`) against
  a running instance.
- **Circular imports from packaging.** Grouping can surface cycles the flat layout
  hid. The app importing at all, plus TC-14, is the check.
- **Upstream failures are out of scope here** — no `fetch_*` body changes, so
  failure isolation and upsert idempotency carry over by construction. If any
  service body shows a diff, reject it in review rather than testing around it.
- **`create_all` in the lifespan** still runs as the release-1 safety net and reads
  the same metadata. TC-5 covers the only way it could break.

## Regression Check

Smoke before merge — one route per domain plus the shared surface:

- `GET /api/polls/generic-ballot`, `/api/polls/house`, `/api/forecasts/congress` (elections)
- `GET /api/trends`, `/api/news`, `/api/weather/alerts`, `/api/hazards/earthquakes` (monitor)
- `GET /api/status/sources` and the Admin page's Data Sources panel (shared)
- `POST /api/refresh` — still returns 200 then 429 within 60s
- `GET /health`
- Admin page candidate issue-tag confirm/reject — still 401 without `X-Admin-Key`

## Sign-off
- [ ] All test cases pass
- [ ] Samuel has reviewed results before merge to main
