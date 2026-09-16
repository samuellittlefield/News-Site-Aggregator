"""Open seats never list the member who is vacating them.

FEC keeps a departing member on file as an active candidate with the money
they had already raised, so ME-2 showed "Jared Golden is retiring" and Jared
Golden as the leading Democrat in the same panel. `/api/polls/house/districts`
drops the departing member from `candidates`; `departing_incumbent` is the one
place they appear.

The match has to bridge FEC's "GOLDEN, JARED F" and the Wikipedia retirements
list's "Jared Golden", without taking a same-surname relative or primary rival
down with it — that is what `app.elections.services.names.same_person` is for.
"""
import pytest

from app.elections.services.names import same_person
from app.models import Candidate, HouseRetirement

ENDPOINT = "/api/polls/house/districts"


def _district(body, label):
    return next(d for d in body if d["label"] == label)


def _names(district):
    return [c["name"] for c in district["candidates"]]


def _seed_me2(db):
    """ME-2: Golden (D, incumbent) retiring; LePage (R) and Dunlap (D) running."""
    db.add(HouseRetirement(
        state="ME", district=2, member_name="Jared Golden", party="D",
        reason="is retiring",
    ))
    db.add_all([
        Candidate(fec_id="H8ME02123", name="GOLDEN, JARED F", party="DEM",
                  state="ME", district=2, office="H", incumbent_challenge="I",
                  fundraising_total=2_600_000.0),
        Candidate(fec_id="H6ME02456", name="LEPAGE, PAUL", party="REP",
                  state="ME", district=2, office="H", incumbent_challenge="O",
                  fundraising_total=2_550_000.0),
        Candidate(fec_id="H6ME02789", name="DUNLAP, MATTHEW", party="DEM",
                  state="ME", district=2, office="H", incumbent_challenge="O",
                  fundraising_total=400_000.0),
    ])
    db.flush()


# ── the reported bug ────────────────────────────────────────────────────────

def test_departing_member_not_listed_as_candidate(client, db):
    _seed_me2(db)
    me2 = _district(client.get(ENDPOINT).json(), "ME-2")

    assert me2["open_seat"] is True
    assert me2["departing_incumbent"]["name"] == "Jared Golden"
    assert "GOLDEN, JARED F" not in _names(me2)


def test_other_candidates_survive_the_filter(client, db):
    """Only the departing member is dropped — the actual field is untouched."""
    _seed_me2(db)
    me2 = _district(client.get(ENDPOINT).json(), "ME-2")

    assert _names(me2) == ["LEPAGE, PAUL", "DUNLAP, MATTHEW"]  # fundraising order


def test_incumbent_kept_when_seat_is_not_open(client, db):
    """No retirement row → nothing is filtered, incumbent included."""
    db.add(Candidate(fec_id="H8ME02123", name="GOLDEN, JARED F", party="DEM",
                     state="ME", district=2, office="H", incumbent_challenge="I",
                     fundraising_total=2_600_000.0))
    db.flush()
    me2 = _district(client.get(ENDPOINT).json(), "ME-2")

    assert me2["open_seat"] is False
    assert _names(me2) == ["GOLDEN, JARED F"]


def test_same_surname_candidate_is_not_dropped(client, db):
    """A relative or primary rival sharing the surname keeps their slot — the
    filter needs the given name too (or an FEC incumbent flag)."""
    db.add(HouseRetirement(state="ME", district=2, member_name="Jared Golden",
                           party="D", reason="is retiring"))
    db.add(Candidate(fec_id="H6ME02999", name="GOLDEN, SARAH", party="DEM",
                     state="ME", district=2, office="H", incumbent_challenge="O",
                     fundraising_total=120_000.0))
    db.flush()
    me2 = _district(client.get(ENDPOINT).json(), "ME-2")

    assert _names(me2) == ["GOLDEN, SARAH"]


# ── the name matcher itself ─────────────────────────────────────────────────

@pytest.mark.parametrize("display, fec", [
    ("Jared Golden", "GOLDEN, JARED F"),            # FEC middle initial
    ("Jared Golden", "Golden, Jared F. Mr."),       # honorific + punctuation
    ("J. Golden", "GOLDEN, JARED F"),               # initial on the display side
    ("Monica De La Cruz", "De La Cruz, Monica"),    # multi-token surname
    ("Derrick Van Orden", "Van Orden, Derrick"),
    ("Mariannette Miller-Meeks", "Miller-Meeks, Mariannette Jane"),
    ("María Elvira Salazar", "SALAZAR, MARIA ELVIRA"),  # diacritics folded
])
def test_same_person_matches(display, fec):
    assert same_person(display, fec) is True


@pytest.mark.parametrize("display, fec", [
    ("Jared Golden", "GOLDEN, SARAH"),   # same surname, different person
    ("Jared Golden", "LEPAGE, PAUL"),
    ("Golden Smith", "GOLDEN, JARED"),   # surname must be a trailing run, not any token
    ("Jared Golden", ""),
])
def test_same_person_rejects(display, fec):
    assert same_person(display, fec) is False


def test_surname_only_match_is_opt_in():
    """require_given=False is the incumbent-flag path — never the default."""
    assert same_person("Nick Begich", "BEGICH, NICHOLAS") is False
    assert same_person("Nick Begich", "BEGICH, NICHOLAS", require_given=False) is True
