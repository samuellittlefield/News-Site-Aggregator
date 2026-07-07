# Backend

FastAPI + SQLAlchemy + Postgres. Schema is managed by **Alembic migrations**
(`backend/alembic/`), not by `create_all` — see below.

## Database migrations (Alembic)

Deploys run `alembic upgrade head` before uvicorn (see `Procfile`), so the schema
is migrated on every release. `Base.metadata.create_all()` remains in `app/main.py`
`lifespan` as a temporary release-1 safety net and will be removed in a follow-up —
**Alembic is the schema authority.**

### Changing a model — the loop

Any change to `app/models.py` ships its migration **in the same PR**:

1. Edit the model(s) in `app/models.py`.
2. Generate the migration against a local DB that's already at head:
   ```bash
   cd backend
   alembic upgrade head                       # make sure local DB is current
   alembic revision --autogenerate -m "short description"
   ```
3. **Review the generated file** in `alembic/versions/`. Autogenerate is not
   trustworthy blind — always check:
   - **JSONB columns / lambda defaults** (e.g. `Trend.sources_list`) render correctly.
   - **`server_default`s** (autogenerate can miss or mis-render them).
   - Unique constraints, FK `ondelete`, and index names.
   Edit the migration by hand where needed.
4. Apply and confirm it's clean:
   ```bash
   alembic upgrade head
   alembic revision --autogenerate -m "should-be-empty"   # must produce an empty diff
   ```
   Delete the throwaway "should-be-empty" revision. If it's *not* empty, the
   migration doesn't match the models — fix it.
5. Commit the model change **and** the migration together.

### First-time / fresh database

```bash
alembic upgrade head        # builds the full schema from scratch
```

### Existing database with the schema but no history (one-time)

If a database already has the tables but no `alembic_version` (e.g. a long-lived
local DB predating migrations), stamp it once so the baseline isn't re-applied:

```bash
alembic stamp head
```

> Prod was stamped this way on 2026-07-07 against baseline `1cfc95e31a13`.

### Notes

- `DATABASE_URL` may use Railway's `postgres://` prefix — `alembic/env.py` rewrites
  it to `postgresql://` (mirrors `app/database.py`).
- A failing migration aborts the deploy (the `&&` gate in the `Procfile`): the app
  never starts on a half-migrated schema, and the previous release keeps serving.
  Roll back with `alembic downgrade -1` + revert, or ship a hotfix migration.
