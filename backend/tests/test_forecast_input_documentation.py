"""AC-10 / TC-13 (poll-staleness-labels): the generic-ballot window-drain ->
tier-2 fallback is written down somewhere a reader would find it, not just
true-but-silent in the code. No behaviour to test — PR #11 already surfaces
`swing_source` — just that the trigger itself is documented.
"""
import pathlib

REPO_ROOT = pathlib.Path(__file__).parent.parent.parent


def test_sources_md_documents_the_drain_to_tier2_trigger():
    text = (REPO_ROOT / "SOURCES.md").read_text()
    assert "compute_average" in text
    assert "tier 2" in text or "tier-2" in text
    assert "_current_env" in text
