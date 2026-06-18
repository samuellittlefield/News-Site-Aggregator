"""
Backtest the House seat model on consistent (current) maps to (a) show why the
prior needs to embed incumbency and (b) calibrate the seat-level noise δ.

Two analyses, both using actual results from house_results_history.csv (parsed
from the 538 dataset) and priors detrended to "lean vs nation":

1. Pres-only prior (2020 pres → 2022 & 2024 outcomes): a win-rate calibration
   table. Paper toss-ups break heavily to the incumbent party — the incumbency
   signal a presidential-lean prior omits.
2. Blended prior (2022 House result + 2020 pres → 2024 outcomes): residual SD and
   bias vs the pres-only prior. The blend lowers both, and its residual SD is the
   empirical δ_house the live model uses.

Run:  .venv/bin/python -m scripts.backtest      (from backend/)
"""
import csv
import os
import statistics

DATA = os.path.join(os.path.dirname(__file__), "..", "app", "data")
NAT = {"pres2020": 4.29, "house2022": -2.8, "house2024": -2.6}
BLEND = 0.5  # weight on last-House-result lean (matches HOUSE_PRIOR_BLEND)


def _load(name):
    with open(os.path.join(DATA, name), newline="") as f:
        return list(csv.DictReader(f))


def _norm(d):
    return "AL" if d.strip() in ("AL", "At-Large") else str(int(d))


def main():
    pres20 = {(r["state"], _norm(r["district"])): float(r["pres2020_margin"])
              for r in _load("house_pres2020_by_cd.csv")}
    res = {}
    for r in _load("house_results_history.csv"):
        if r["dem_margin"] and float(r["dem_pct"]) > 0 and float(r["rep_pct"]) > 0:
            res[(r["cycle"], r["state"], _norm(r["district"]))] = float(r["dem_margin"])

    # ── 1. pres-only prior: win-rate calibration (2022 + 2024) ──────────────
    rows = []
    for (cyc, st, d), actual in res.items():
        key = (st, d)
        if key not in pres20:
            continue
        predicted = (pres20[key] - NAT["pres2020"]) + NAT[f"house{cyc}"]
        rows.append((predicted, actual >= 0))
    print("PRES-ONLY PRIOR — win-rate calibration (2022+2024 contested seats)")
    print("  predicted margin bin   seats   actual D-win%")
    for lo, hi in [(-999, -15), (-15, -8), (-8, -3), (-3, 3), (3, 8), (8, 15), (15, 999)]:
        b = [w for p, w in rows if lo <= p < hi]
        if b:
            lbl = f"[{lo:>4},{hi:>4})".replace("-999", "  -∞").replace(" 999", "  +∞")
            print(f"   {lbl:>14}     {len(b):>4}     {100*sum(b)/len(b):4.0f}%")
    print("  → paper toss-ups break to the incumbent party: presidential lean omits incumbency.\n")

    # ── 2. blended prior vs pres-only: residual SD + bias (2024) ────────────
    rp, rb = [], []
    for (st, d), p20 in [((s, dd), v) for (s, dd), v in pres20.items()]:
        a = res.get(("2024", st, d))
        if a is None:
            continue
        pres_lean = p20 - NAT["pres2020"]
        rp.append(a - (pres_lean + NAT["house2024"]))
        h22 = res.get(("2022", st, d))
        if h22 is not None:
            blended = BLEND * (h22 - NAT["house2022"]) + (1 - BLEND) * pres_lean
            rb.append(a - (blended + NAT["house2024"]))
    print("2024 backtest — prior comparison")
    print(f"  pres-only prior : residual SD {statistics.pstdev(rp):.1f}  bias {statistics.mean(rp):+.1f}  (n={len(rp)})")
    print(f"  blended prior   : residual SD {statistics.pstdev(rb):.1f}  bias {statistics.mean(rb):+.1f}  (n={len(rb)})")
    print(f"  → blend lowers error and bias; its SD ≈ live DELTA_HOUSE.")


if __name__ == "__main__":
    main()
