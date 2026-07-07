"""Pytest fixtures for the backend suite.

Runs against a real Postgres (models use JSONB, so SQLite is out) — a dedicated
`newsdb_test` database, never the dev `newsdb`. The schema is built once per
session via `Base.metadata.create_all` (deliberately independent of Alembic, for
speed and always-current schema); each test runs inside a transaction that is
rolled back, so tests are isolated and two consecutive runs need no cleanup.

Environment is configured *before* the app is imported so `app.database.engine`
binds to the test DB and the scheduler/startup-refresh never fire.
"""
import os

# ── Configure env before importing the app ──────────────────────────────────
os.environ.setdefault(
    "TEST_DATABASE_URL", "postgresql://newsuser:newspass@localhost:5432/newsdb_test"
)
# Point the app's engine at the test DB and gate background jobs.
os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
os.environ["DISABLE_SCHEDULER"] = "1"

import httpx  # noqa: E402
import pytest  # noqa: E402
import respx  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine.url import make_url  # noqa: E402
from sqlalchemy.exc import OperationalError  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402


def _ensure_test_db() -> None:
    """Create the test database if it doesn't exist. Fails fast with a clear
    message if Postgres itself is unreachable (rather than hanging later)."""
    url = make_url(os.environ["TEST_DATABASE_URL"])
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :n"),
                {"n": url.database},
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    except OperationalError as e:  # pragma: no cover - environment guard
        raise RuntimeError(
            f"Cannot reach Postgres at {url.set(password='***')}. "
            "Start it first (e.g. `docker-compose up -d db`)."
        ) from e
    finally:
        admin.dispose()


_ensure_test_db()

from app.database import engine, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _schema():
    """Build the schema once for the session. Left in place afterwards so reruns
    are fast; per-test rollback keeps data clean."""
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def db():
    """A transactional session that rolls back after each test.

    `join_transaction_mode="create_savepoint"` means service code that calls
    `db.commit()` (e.g. `fetch_kalshi`) commits onto a savepoint, so the outer
    transaction rollback still undoes everything.
    """
    connection = engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        outer.rollback()
        connection.close()


@pytest.fixture
def client(db):
    """TestClient with `get_db` overridden to the transactional test session.
    Entering the client triggers lifespan (schema ensured; scheduler gated off)."""

    def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture(autouse=True)
def respx_router():
    """Autouse network guard (AC-2): every test runs with respx active, so any
    unmocked outbound HTTP raises instead of hitting a live API. In-process
    TestClient calls (host `testserver`) are passed through to the ASGI app."""
    with respx.mock(assert_all_called=False) as router:
        router.route(host="testserver").pass_through()
        yield router


# Re-export for tests that build Kalshi responses.
_httpx = httpx
