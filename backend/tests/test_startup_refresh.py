"""Startup refresh sequencing is unchanged (elections-seam T1, AC-11 / TC-15b).

`test_scheduler_does_not_run_under_testclient` in `test_routers_smoke.py`
already covers TC-15a (`DISABLE_SCHEDULER=1` suppresses both the scheduler and
the startup refresh — the entire suite depends on that holding). This covers
the other half: with the gate off, `_startup_refresh` must still run the same
15 steps in the same order with the same per-step timeout budget. The move
only changed which package each `refresh_*` callable imports from, so this
pins the current (unchanged) sequence as a regression guard.
"""
from app import main as main_module

EXPECTED_STEPS = [
    ("votehub", 120.0),
    ("earthquakes", 120.0),
    ("faa", 120.0),
    ("markets", 120.0),
    ("kalshi", 120.0),
    ("all", 180.0),
    ("extended_sources", 180.0),
    ("news", 180.0),
    ("status", 120.0),
    ("weather", 120.0),
    ("nws_alerts", 120.0),
    ("house_polls", 180.0),
    ("candidates", 600.0),
    ("retirements", 120.0),
    ("economist", 180.0),
]


async def test_startup_refresh_runs_same_steps_in_same_order(monkeypatch):
    calls = []

    async def fake_safe_refresh(name, fn, timeout=180.0):
        calls.append((name, timeout))

    async def fake_sleep(_seconds):
        return None

    monkeypatch.setattr(main_module, "_safe_refresh", fake_safe_refresh)
    monkeypatch.setattr(main_module.asyncio, "sleep", fake_sleep)

    await main_module._startup_refresh()

    assert calls == EXPECTED_STEPS
