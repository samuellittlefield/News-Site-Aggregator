"""The elections/monitor seam is enforced, not merely organized
(elections-seam T1, AC-7 / TC-10, TC-11; AC-8 / TC-12).

Walks every `.py` file under `app/elections/` and `app/monitor/` with
`ast.parse` (static parsing — module bodies are never executed) and collects
every `Import` / `ImportFrom` target. `app/elections/**` may not import
`app.monitor.*` or vice versa; `app/shared/**` may not import either domain
(it's the one holding position both domains may depend on, per the feature
plan). Feeding either side's own domain, or shared, back to itself is fine —
only cross-domain edges are forbidden.

To see one of these actually go red: add
`from app.monitor.services import trends` to the top of any
`app/elections/**` module and run
`pytest tests/test_module_boundaries.py::test_elections_does_not_import_monitor`
— it must fail, naming the file and the import. Revert before committing. The
`test_violation_detection_actually_fires` case below does this same thing
automatically, against a throwaway file, so the mechanism is proven without
depending on a human remembering to try it by hand.
"""
import ast
import pathlib

APP_DIR = pathlib.Path(__file__).parent.parent / "app"


def _imported_modules(path: pathlib.Path) -> list:
    tree = ast.parse(path.read_text(), filename=str(path))
    mods = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.append(node.module)
    return mods


def _py_files(root: pathlib.Path) -> list:
    return sorted(root.rglob("*.py"))


def _violations(files: list, forbidden_prefixes: list) -> list:
    out = []
    for f in files:
        for mod in _imported_modules(f):
            if any(mod == p or mod.startswith(p + ".") for p in forbidden_prefixes):
                out.append((f, mod))
    return out


# ── TC-10: passes on the clean tree ─────────────────────────────────────────

def test_elections_does_not_import_monitor():
    v = _violations(_py_files(APP_DIR / "elections"), ["app.monitor"])
    assert v == [], f"app/elections importing app/monitor: {v}"


def test_monitor_does_not_import_elections():
    v = _violations(_py_files(APP_DIR / "monitor"), ["app.elections"])
    assert v == [], f"app/monitor importing app/elections: {v}"


# ── AC-8 / TC-12: shared depends on neither domain ──────────────────────────

def test_shared_imports_neither_domain():
    v = _violations(_py_files(APP_DIR / "shared"), ["app.elections", "app.monitor"])
    assert v == [], f"app/shared importing a domain package: {v}"


# ── TC-11: the check can actually fail ──────────────────────────────────────

def test_violation_detection_actually_fires(tmp_path):
    bad = tmp_path / "elections_violation.py"
    bad.write_text("from app.monitor.services import trends\n")
    v = _violations([bad], ["app.monitor"])
    assert v == [(bad, "app.monitor.services")]
