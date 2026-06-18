"""
Backtest the House seat model against 2022 + 2024 actual results to calibrate
the seat-level idiosyncratic noise δ (DELTA_HOUSE).

Method (current maps, so no redistricting reconciliation):
  prior lean      = 2020 presidential margin by CD, detrended by the 2020
                    national margin → "lean vs nation"  (house_pres2020_by_cd.csv)
  predicted margin = prior_lean + actual national House environment that cycle
  residual         = actual House two-party margin − predicted        (house_results_history.csv)
The SD of residuals over contested two-party seats is the empirical δ — i.e. how
far individual seats scatter once the national environment is known. Compare to
the model's current DELTA_HOUSE to see if the model is over/under-confident.

Run:  .venv/bin/python -m scripts.backtest      (from backend/)
"""
import csv
import os
import statistics

DATA = os.path.join(os.path.dirname(__file__), "..", "app", "data")

# 2020 national two-party presidential margin (Dem−Rep), from the same Downballot
# source the per-CD priors come from, so the detrend is internally consistent.
NAT_PRES_2020 = 4.29
# Actual national House two-party popular-vote margin (Dem−Rep) per cycle.
NAT_HOUSE_MARGIN = {"2022": -2.8, "2024": -2.6}


def _load(name):
    with open(os.path.join(DATA, name), newline="") as f:
        return list(csv.DictReader(f))


def main():
    prior = {(r["state"], r["district"]): float(r["pres2020_margin"]) for r in _load("house_pres2020_by_cd.csv")}
    results = _load("house_results_history.csv")

    rows = []   # (predicted_margin, actual_margin, dem_won)
    unmatched = uncontested = 0
    for r in results:
        key = (r["state"], r["district"])
        if key not in prior:
            unmatched += 1
            continue
        if not r["dem_margin"]:          # uncontested / no two-party margin
            uncontested += 1
            continue
        lean = prior[key] - NAT_PRES_2020
        predicted = lean + NAT_HOUSE_MARGIN[r["cycle"]]
        rows.append((predicted, float(r["dem_margin"]), r["winner"] == "D"))

    print(f"seats used: {len(rows)} contested  ({uncontested} uncontested, {unmatched} unmatched)\n")

    # δ should govern outcomes near the threshold, not safe-seat blowout variance.
    # Report residual SD over all seats vs only competitive ones.
    def sd(pred_window):
        res = [a - p for p, a, _ in rows if abs(p) <= pred_window]
        return statistics.pstdev(res), len(res)
    for w in (100, 20, 10):
        s, n = sd(w)
        tag = "all seats" if w == 100 else f"|predicted|≤{w}"
        print(f"residual SD, {tag:>16}: {s:5.1f} pts  (n={n})")
    comp_sd = sd(20)[0]
    print(f"\nmodel currently uses DELTA_HOUSE=5.0 ; empirical (competitive) ≈ {comp_sd:.1f}")

    # Win-probability calibration: bin by predicted margin, show actual D-win rate.
    print("\npredicted-margin bin   seats   actual D-win%")
    bins = [(-999, -15), (-15, -8), (-8, -3), (-3, 3), (3, 8), (8, 15), (15, 999)]
    for lo, hi in bins:
        b = [w for p, a, w in rows if lo <= p < hi]
        if b:
            label = f"[{lo:>4},{hi:>4})".replace("-999", "  -∞").replace(" 999", "  +∞")
            print(f"  {label:>14}      {len(b):>4}      {100*sum(b)/len(b):5.0f}%")


if __name__ == "__main__":
    main()
