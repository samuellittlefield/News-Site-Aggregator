"""parse_retirements() wikitext parsing.

Regression for the open-seat-candidate-filter bug: a piped wikilink like
[[Daniel Webster (Florida politician)|Daniel Webster]] must yield the display
text ("Daniel Webster"), not the link target. The target's disambiguation
suffix ("(Florida politician)") breaks polls.py's same_person() surname match,
so the departing incumbent was never filtered out of that district's
`candidates` list.
"""
from app.elections.services.retirements import parse_retirements

WIKITEXT = """
==Retirements==
===Democratic===
#{{ushr|ME|2|X}}: [[Jared Golden]] is retiring.
#{{ushr|NH|1|X}}: [[Chris Pappas (American politician)|Chris Pappas]] is running for governor.
===Republican===
#{{ushr|FL|11|X}}: [[Daniel Webster (Florida politician)|Daniel Webster]] is retiring.
#{{ushr|NY|21|X}}: [[Elise Stefanik]] is retiring (previously ran for governor).
"""


def test_prefers_piped_display_text_over_link_target():
    rows = parse_retirements(WIKITEXT)
    by_district = {(r["state"], r["district"]): r for r in rows}

    assert by_district[("NH", 1)]["name"] == "Chris Pappas"
    assert by_district[("FL", 11)]["name"] == "Daniel Webster"


def test_unpiped_link_falls_back_to_target():
    rows = parse_retirements(WIKITEXT)
    by_district = {(r["state"], r["district"]): r for r in rows}

    assert by_district[("ME", 2)]["name"] == "Jared Golden"
    assert by_district[("NY", 21)]["name"] == "Elise Stefanik"


def test_party_and_reason_still_parsed():
    rows = parse_retirements(WIKITEXT)
    by_district = {(r["state"], r["district"]): r for r in rows}

    assert by_district[("ME", 2)]["party"] == "D"
    assert by_district[("FL", 11)]["party"] == "R"
    assert by_district[("NH", 1)]["reason"] == "is running for governor"
