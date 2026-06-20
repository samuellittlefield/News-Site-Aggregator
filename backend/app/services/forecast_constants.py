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

# National baselines for the years the Senate prior results come from, used to
# detrend each last-result margin into a "lean vs the nation that year" before
# blending. 2020 = Biden's presidential popular-vote margin; 2022 = that year's
# national House popular-vote margin (R+2.8).
NATIONAL_PRES_2020_D = 4.5
NATIONAL_2022_D = -2.8

# Senate seat prior = blend of the last same-seat result lean and the 2024
# presidential lean. Weight on the last-result lean (captures incumbency
# strength); the remainder is presidential lean. Experimental — tune in Phase F.
SENATE_PRIOR_BLEND = 0.5

# House seat prior = blend of the 2024 House result lean (embeds incumbency —
# the backtest showed presidential-lean toss-ups went 82% to the incumbent
# party) and the 2024 presidential lean. Falls back to pure presidential lean
# for the ~42 uncontested seats with no two-party House margin.
NATIONAL_HOUSE_2024_D = -2.6   # actual 2024 national House two-party margin
HOUSE_PRIOR_BLEND = 0.5

# Current Senate composition going into 2026 (independents counted with Dems).
CURRENT_SENATE = {"D": 47, "R": 53}

# Control thresholds. House majority = 218. Senate: a Republican VP breaks 50–50
# ties, so Democrats need 51 to control while Republicans hold at 50.
HOUSE_MAJORITY = 218
SENATE_DEM_CONTROL = 51

# Fundamentals / uncertainty knobs (points), backtest-informed where noted
# (scripts/backtest.py). τ≈3.5 from the historical generic-ballot error (~3–4 pts).
# δ_house≈5.5: with the blended (incumbency-aware) House prior, 2024 seats scatter
# ~5.4 pts around the prediction — lower than the ~7 the pres-only prior implied,
# because that prior's incumbency-blindness was showing up as noise.
# DELTA_SENATE is still a judgment value (no Senate backtest panel yet).
INCUMBENCY_ADV = 0.0      # 0: both priors now blend in the last same-office result,
                          # which already embeds incumbency — a separate flat term
                          # would double-count it.
TAU = 3.5                 # national-error SD, shared across seats in a sim (correlation)
DELTA_HOUSE = 5.5         # per-district idiosyncratic SD (backtested, blended prior, 2024)
DELTA_SENATE = 10.0       # per-seat idiosyncratic SD (backtested on 133 Senate races
                          # 2018–24: competitive seats scatter ~11 pts — Senate is far
                          # more candidate-driven than the House, was overconfident at 7)

# Candidate fundraising edge (FEC). Per seat we compare the best-funded Dem vs
# best-funded Rep and shift the seat margin by coef × log10(D$ / R$), capped.
# Money has diminishing returns, so the log; a ~10× cash advantage ≈ +coef points.
# Targets the recent Dem Senate overperformance the backtest flagged. Judgment
# value (sparse this early — primaries ongoing); not yet backtested. 0 disables.
FUNDRAISING_COEF = 3.0
FUNDRAISING_CAP = 8.0

N_SIMS = 20000
