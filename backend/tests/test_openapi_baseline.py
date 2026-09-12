"""OpenAPI surface regression (elections-seam T1, AC-2 / TC-3).

`fixtures/openapi_baseline.json` was captured from the pre-refactor code
(commit f3e2296 — the flat `app/routers` + `app/services` layout, right before
this ticket started) via `app.openapi()` directly; that call needs no DB or
running server. This test captures the current app's spec the same way and
compares.

One real wrinkle surfaced by this comparison, not a regression: FastAPI
disambiguates same-named response models defined in different modules by
folding each class's `__module__` into its OpenAPI component name (e.g. two
different `ArticleOut` classes, one in the old `trends.py` and one in
`news.py`, became `app__routers__trends__ArticleOut` and
`app__routers__news__ArticleOut` — the plain name collided, so FastAPI had to
qualify it, even before this ticket). Moving those router files to
`app/monitor/routers/` and `app/elections/routers/` changes the folded-in
module path, so six of these synthetic names take a new form
(`app__routers__X__Y` -> `app__monitor__routers__X__Y` or
`app__elections__routers__X__Y`). `_normalize` collapses that synthetic
prefix back to the bare class name on both sides before comparing, so the
check is against the same thing an API consumer actually sees: paths,
methods, status codes, and — via the normalized schemas — every field and
type. None of that differs. Only FastAPI's internal disambiguation string
does, purely because it echoes the file's location.
"""
import json
import pathlib

from app.main import app

BASELINE = json.loads(
    (pathlib.Path(__file__).parent / "fixtures" / "openapi_baseline.json").read_text()
)


def _normalize(spec: dict) -> dict:
    spec = json.loads(json.dumps(spec))
    schemas = spec["components"]["schemas"]
    rename = {name: name.rsplit("__", 1)[-1] for name in schemas if name.startswith("app__")}
    spec["components"]["schemas"] = {rename.get(k, k): v for k, v in schemas.items()}
    raw = json.dumps(spec)
    for old, new in rename.items():
        raw = raw.replace(f'#/components/schemas/{old}"', f'#/components/schemas/{new}"')
    return json.loads(raw)


def test_openapi_surface_unchanged():
    current = _normalize(app.openapi())
    baseline = _normalize(BASELINE)

    assert set(current["paths"]) == set(baseline["paths"])
    assert current["paths"] == baseline["paths"]
    assert current["components"]["schemas"] == baseline["components"]["schemas"]
