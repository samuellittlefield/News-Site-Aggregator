"""
Tunable constants for the experimental in-house seat model (`forecast_model.py`).

These are JUDGMENT values, not fitted to history — that calibration is Phase F.
The uncertainty knobs (TAU, DELTA*) set how wide the probability spread is; the
adjustment terms (INCUMBENCY_ADV) are crude fundamentals. Anything here is a
candidate for backtesting later.
"""

# 2024 national two-party presidential margin (Dem − Rep), computed from the
# vendored district vote totals (Downballot). District priors are presidential
# leans, so this is the baseline the live generic ballot is swung against.
NATIONAL_PRES_MARGIN_2024_D = -1.65

# Current Senate composition going into 2026 (independents counted with Dems).
CURRENT_SENATE = {"D": 47, "R": 53}

# Control thresholds. House majority = 218. Senate: a Republican VP breaks 50–50
# ties, so Democrats need 51 to control while Republicans hold at 50.
HOUSE_MAJORITY = 218
SENATE_DEM_CONTROL = 51

# Fundamentals / uncertainty knobs (points, experimental — to be calibrated).
INCUMBENCY_ADV = 3.0      # margin shift toward the incumbent party
TAU = 3.0                 # national-error SD, shared across seats in a sim (correlation)
DELTA_HOUSE = 5.0         # per-district idiosyncratic SD
DELTA_SENATE = 7.0        # per-seat idiosyncratic SD (Senate is more candidate-driven)

N_SIMS = 20000
