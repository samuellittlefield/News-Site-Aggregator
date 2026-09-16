"""Shared candidate-name matching across election sources.

Three upstreams name the same person three ways: FEC files them as
"GOLDEN, JARED F", VoteHub and Wikipedia use display order ("Jared Golden").
Comparing them needs accent/punctuation folding, suffix stripping, and a
surname split that survives multi-token surnames ("De La Cruz", "Van Orden",
"Miller-Meeks").

The VoteHub poll crosswalk and the district feed's open-seat filter both need
that, so the primitives live here rather than inside either caller.
"""
import re
import unicodedata

NAME_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v", "mr", "mrs", "ms", "dr"}


def fold(s: str) -> str:
    """Unicode NFD, drop combining marks, lowercase, punctuation -> space.
    Comparison only — callers never store or mutate the folded form."""
    nfd = unicodedata.normalize("NFD", s)
    stripped = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", stripped.lower())


def tokens(name: str) -> list:
    """Fold a name and split into tokens, dropping suffixes/honorifics."""
    return [t for t in fold(name).split() if t and t not in NAME_SUFFIXES]


def fec_name_parts(name: str) -> tuple:
    """FEC stores 'Last, First Middle' -> (surname_tokens, given_tokens), split
    on the first comma — the surname may itself be several tokens. No comma
    present -> fall back to treating the last token as the surname."""
    if "," in name:
        surname, given = name.split(",", 1)
        return tokens(surname), tokens(given)
    toks = tokens(name)
    if not toks:
        return [], []
    return toks[-1:], toks[:-1]


def _given_agrees(display_first: str, fec_first: str) -> bool:
    """First given names agree, allowing an initial on either side
    ('J. Golden' vs 'GOLDEN, JARED F')."""
    if display_first == fec_first:
        return True
    if len(display_first) == 1:
        return fec_first.startswith(display_first)
    if len(fec_first) == 1:
        return display_first.startswith(fec_first)
    return False


def same_person(display_name: str, fec_name: str, *, require_given: bool = True) -> bool:
    """True when a display-order name and an FEC 'Last, First' name denote the
    same person.

    The FEC surname tokens must form a contiguous suffix of the display name's
    tokens — never derived from the display name's last token alone, which
    breaks every multi-token surname. Given-name agreement is then what keeps a
    relative or a same-surname primary rival from matching; drop it with
    require_given=False only when a separate signal has already pinned the
    person down.
    """
    dt = tokens(display_name)
    sur, giv = fec_name_parts(fec_name)
    if not sur or len(dt) < len(sur) or dt[-len(sur):] != sur:
        return False
    if not require_given:
        return True
    return bool(giv) and len(dt) > len(sur) and _given_agrees(dt[0], giv[0])
