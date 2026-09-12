"""Router/service package layout (elections-seam T1, AC-1 / TC-1, TC-2).

TC-1: the old flat `app.routers` / `app.services` packages must not resolve at
all after the move — not merely "the new paths also work" but "the old paths
are gone". A stale `.pyc` can make a deleted module importable for the wrong
reason, so this is only meaningful with `__pycache__` cleared (done as part of
every step in this ticket; CI starts clean regardless).

TC-2: every module has exactly one home, matching the implementation plan's
table exactly — routers 6/6/1, services 10/21/3 — with no basename duplicated
across packages.
"""
import importlib.util
import pathlib

import pytest

APP_DIR = pathlib.Path(__file__).parent.parent / "app"

OLD_MODULES = [
    "app.routers",
    "app.routers.polls",
    "app.routers.status",
    "app.services",
    "app.services.house_polls",
    "app.services.source_run",
]


@pytest.mark.parametrize("mod", OLD_MODULES)
def test_old_flat_path_does_not_resolve(mod):
    # find_spec on a dotted path needs its parent package importable first;
    # app.routers/app.services don't exist at all post-refactor, so a
    # ModuleNotFoundError while resolving an ancestor means "gone", same as a
    # bare None result for the top-level package itself.
    try:
        spec = importlib.util.find_spec(mod)
    except ModuleNotFoundError:
        spec = None
    assert spec is None, f"{mod} still resolves — old flat path not fully removed"


def test_old_flat_directories_absent():
    assert not (APP_DIR / "routers").exists()
    assert not (APP_DIR / "services").exists()


def _basenames(pkg_dir: pathlib.Path) -> set:
    return {f.stem for f in pkg_dir.glob("*.py") if f.stem != "__init__"}


def test_router_counts_and_no_duplicate_basenames():
    elections = _basenames(APP_DIR / "elections" / "routers")
    monitor = _basenames(APP_DIR / "monitor" / "routers")
    shared = _basenames(APP_DIR / "shared" / "routers")
    assert len(elections) == 6, elections
    assert len(monitor) == 6, monitor
    assert len(shared) == 1, shared
    assert elections & monitor == set()
    assert elections & shared == set()
    assert monitor & shared == set()


def test_service_counts_and_no_duplicate_basenames():
    elections = _basenames(APP_DIR / "elections" / "services")
    monitor = _basenames(APP_DIR / "monitor" / "services")
    shared = _basenames(APP_DIR / "shared" / "services")
    assert len(elections) == 10, elections
    assert len(monitor) == 21, monitor
    assert len(shared) == 3, shared
    assert elections & monitor == set()
    assert elections & shared == set()
    assert monitor & shared == set()
