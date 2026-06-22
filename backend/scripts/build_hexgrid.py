"""
Build the House district hex-cartogram layout (`backend/app/data/house_hexgrid.csv`).

A hex cartogram draws every one of the 435 districts as an equal-size hexagon, so
competitive urban seats read at the same weight as sprawling rural ones — the
failure mode of a geographic/3D map at 435-seat scale.

We don't promise sub-state hex identity (no stylized cartogram does). What we
guarantee: each state is a compact hex blob anchored at its true geographic
center, sized to the *current* apportionment, and every real district gets exactly
one cell. The 50 state anchors (STATE_CENTER) were frozen once from Daniel
Donner's / Daily Kos Elections congressional hexmap topology
(github.com/alecrajeev/UnitedStatesHex). Current per-state district counts come
from house_priors.csv, so the layout always matches the model's universe — no
external download, fully reproducible.

Packing: process states largest-first (so CA/TX claim contiguous space before
smaller neighbors encroach); each state greedily claims the N nearest unclaimed
hex cells to its anchor. Output is axial (q, r) coordinates; the frontend converts
to pixels with the standard pointy-top formulas.

Run:  python backend/scripts/build_hexgrid.py
"""
import collections
import csv
import math
import os

PITCH = 3.94  # median nearest-neighbor district spacing in the source topology

# Frozen geographic anchors (x = west→east, y = north→south) from the Donner hexmap.
STATE_CENTER = {
    "AK": (16.8, 106.1), "AL": (92.89, 81.59), "AR": (82.6, 69.3), "AZ": (39.47, 79.43),
    "CA": (19.87, 60.66), "CO": (52.6, 66.5), "CT": (159.24, 29.38), "DE": (135.8, 52.1),
    "FL": (110.09, 108.68), "GA": (104.3, 85.27), "HI": (42.0, 106.9), "IA": (75.8, 40.5),
    "ID": (23.2, 17.7), "IL": (86.89, 47.12), "IN": (96.67, 48.23), "KS": (68.5, 51.5),
    "KY": (101.23, 60.43), "LA": (79.97, 84.03), "MA": (163.71, 21.97), "MD": (128.12, 53.55),
    "ME": (161.7, 9.9), "MI": (101.27, 24.24), "MN": (76.47, 20.75), "MO": (78.22, 56.05),
    "MS": (85.8, 80.9), "MT": (26.0, 13.3), "NC": (121.6, 71.7), "ND": (69.0, 15.3),
    "NE": (66.53, 44.23), "NH": (157.8, 13.3), "NJ": (145.62, 47.87), "NM": (48.8, 75.7),
    "NV": (34.3, 63.9), "NY": (142.25, 24.5), "OH": (109.1, 44.7), "OK": (72.36, 73.06),
    "OR": (12.0, 29.14), "PA": (131.02, 39.39), "RI": (168.0, 29.7), "SC": (113.91, 79.53),
    "SD": (69.0, 19.3), "TN": (97.89, 69.34), "TX": (60.29, 87.28), "UT": (41.1, 66.3),
    "VA": (119.51, 61.26), "VT": (154.2, 12.9), "WA": (13.78, 18.38), "WI": (85.78, 25.65),
    "WV": (115.27, 54.5), "WY": (28.0, 17.3),
}

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "app", "data")
_SIZE = PITCH / math.sqrt(3)  # hex "size" so horizontal spacing ≈ PITCH


def _px(q, r):
    """Pointy-top axial → pixel center."""
    return (_SIZE * math.sqrt(3) * (q + r / 2), _SIZE * 1.5 * r)


def _load_apportionment():
    """{state: [district_id, ...]} from house_priors.csv (the model's universe)."""
    by_state = collections.defaultdict(list)
    path = os.path.join(_DATA_DIR, "house_priors.csv")
    for row in csv.DictReader(open(path, newline="")):
        by_state[row["state"]].append(row["district"])
    return by_state


def _district_sort_key(d):
    """At-large states use 'AL'; everything else is a number."""
    return (0, 0) if d == "AL" else (1, int(d))


def build():
    by_state = _load_apportionment()
    assert sum(len(v) for v in by_state.values()) == 435, "expected 435 districts"

    # Candidate hex cells covering the anchors' bounding box (+margin).
    xs = [c[0] for c in STATE_CENTER.values()]
    ys = [c[1] for c in STATE_CENTER.values()]
    cand = []
    for q in range(-10, 90):
        for r in range(-5, 80):
            cx, cy = _px(q, r)
            if min(xs) - 2 * PITCH <= cx <= max(xs) + 2 * PITCH and \
               min(ys) - 2 * PITCH <= cy <= max(ys) + 2 * PITCH:
                cand.append((q, r))

    claimed = {}  # (q, r) -> state
    state_cells = {}
    for state in sorted(by_state, key=lambda s: -len(by_state[s])):  # big states first
        n = len(by_state[state])
        cx, cy = STATE_CENTER[state]
        free = [qr for qr in cand if qr not in claimed]
        free.sort(key=lambda qr: (_px(*qr)[0] - cx) ** 2 + (_px(*qr)[1] - cy) ** 2)
        take = free[:n]
        for qr in take:
            claimed[qr] = state
        state_cells[state] = take

    # Assign real district ids to cells in reading order (row, then column).
    rows_out = []
    for state, cells in state_cells.items():
        cells_sorted = sorted(cells, key=lambda qr: (qr[1], qr[0]))
        districts = sorted(by_state[state], key=_district_sort_key)
        for (q, r), district in zip(cells_sorted, districts):
            rows_out.append((state, district, q, r))

    rows_out.sort(key=lambda x: (x[0], _district_sort_key(x[1])))
    out_path = os.path.join(_DATA_DIR, "house_hexgrid.csv")
    with open(out_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["state", "district", "q", "r"])
        w.writerows(rows_out)

    # Contiguity sanity check.
    def neighbors(q, r):
        return [(q + 1, r), (q - 1, r), (q, r + 1), (q, r - 1), (q + 1, r - 1), (q - 1, r + 1)]
    broken = []
    for state, cells in state_cells.items():
        cset = set(cells)
        seen = {cells[0]}
        stack = [cells[0]]
        while stack:
            c = stack.pop()
            for nb in neighbors(*c):
                if nb in cset and nb not in seen:
                    seen.add(nb)
                    stack.append(nb)
        if len(seen) != len(cset):
            broken.append(state)

    print(f"wrote {len(rows_out)} districts to {out_path}")
    print(f"non-contiguous states: {broken or 'none'}")


if __name__ == "__main__":
    build()
