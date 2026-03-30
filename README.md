# betting-math-kit

[![CI](https://github.com/bene-art/betting-math-kit/actions/workflows/ci.yml/badge.svg)](https://github.com/bene-art/betting-math-kit/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Pure-Python sports betting math. Zero dependencies. Typed. Tested.

## Where this fits

[props-scorer](https://github.com/bene-art/props-scorer) takes player stats and returns a probability. This library takes that probability and tells you what to do with it — how much edge you have, how much to bet, and whether your model is actually any good over time.

```
props-scorer                    betting-math-kit
┌──────────────┐    prob    ┌──────────────────────────────────────────┐
│ player stats │ ────────→  │ de-vig → edge → Kelly → stake size      │
│ → XGBoost    │            │                                          │
│ → probability│            │ after results: Brier, ECE, CLV, sim     │
└──────────────┘            └──────────────────────────────────────────┘
```

Both came out of a larger system I built to fund med school through sports betting. The full system is private. These are the pieces I can show — and the ones that work as standalone tools.

## Why the math matters

Every sportsbook bakes a margin (the "vig") into its odds. A -110/-110 line implies each side has a 52.4% chance of winning — but 52.4 + 52.4 = 104.8%, not 100%. That extra 4.8% is the house edge.

This creates a subtle problem: if you compare your model's probability directly against vigged implied odds, you systematically overstate your edge. You think you have 7.6% edge when you really have 10%. That sounds like a good thing — but it means your Kelly sizing is wrong, your bankroll simulation is off, and your feedback metrics are measuring the wrong baseline.

The fix is to de-vig first:

```
raw odds  →  de-vig  →  fair probability  →  edge  →  Kelly  →  stake size
```

1. **De-vig** the line to recover what the market actually thinks (fair probability).
2. **Measure edge** against the fair line, not the vigged one.
3. **Size the bet** using Kelly criterion against the true edge.
4. **Evaluate** with calibration metrics and closing line value.
5. **Simulate** bankroll trajectories before risking real money.

## Modules

| Module | Purpose |
|--------|---------|
| `odds` | Odds conversion (American / decimal / implied prob), edge calculation (naive and calibrated), fixed-odds Kelly. |
| `devig` | Remove bookmaker margin. Four methods (multiplicative, power, additive, Shin). 2-outcome and n-outcome markets. |
| `kelly` | Pari-mutuel Kelly criterion with pool-size liquidity constraints, takeout friction, and race-level exposure caps. |
| `metrics` | Model evaluation: Brier score, log loss, ECE, calibration buckets, closing line value, edge-bucket analysis. |
| `simulation` | Monte Carlo bankroll trajectories, risk-of-ruin estimation, optimal Kelly fraction search. |
| `types` | Frozen dataclasses (`DevigResult`, `EdgeResult`, `KellyBet`, `SimulationResult`) and enums (`Side`, `DevigMethod`). |
| `exceptions` | Typed error hierarchy: `InvalidOddsError`, `InvalidProbabilityError`, `InvalidBankrollError`, `UnknownMethodError`. |

## Install

```bash
pip install betting-math-kit
```

Or from source:

```bash
git clone https://github.com/bene-art/betting-math-kit.git
cd betting-math-kit
pip install -e ".[dev]"
```

---

## The pipeline in code

### Step 1: De-vig the line

A bookmaker posts -110/-110. What does the market *actually* think?

```python
from betting_math_kit import devig, get_vig, DevigMethod

vig = get_vig(-110, -110)  # 0.048 — the book is charging 4.8%

r = devig(-110, -110)
# fair_home=0.50, fair_away=0.50 — the market thinks it's a coin flip
# The 52.4% implied by -110 was inflated by the vig
```

On skewed lines the method matters. A -500/+400 moneyline allocates margin differently depending on your assumption about how the book prices favorites vs. longshots:

```python
r_mult = devig(-500, 400)                             # proportional removal
r_power = devig(-500, 400, method=DevigMethod.POWER)   # exponent fit
r_shin = devig(-500, 400, method=DevigMethod.SHIN)     # informed-bettor model

# All three sum to 1.0, but the fair probabilities differ:
# MULT:  0.833 / 0.167
# POWER: 0.820 / 0.180  — shifts probability toward the longshot
# SHIN:  0.826 / 0.174  — models favorite-longshot bias
```

For n-outcome markets (outrights, props ladders):

```python
from betting_math_kit import devig_multi

r = devig_multi([200, 300, 150, 800], method=DevigMethod.SHIN)
# fair_probs sum to 1.0, ordered same as input
```

### Step 2: Measure true edge

Your model (or [props-scorer](https://github.com/bene-art/props-scorer)) says home wins 60% of the time. The book has -110/-110. How much edge do you actually have?

```python
from betting_math_kit import calculate_edge_calibrated

r = calculate_edge_calibrated(model_prob=0.60, home_odds=-110, away_odds=-110)

# r.raw_edge  = 0.076  — naive: 0.60 - 0.524 (vigged implied)
# r.true_edge = 0.100  — calibrated: 0.60 - 0.50 (fair probability)
# r.fair_prob = 0.50
```

The difference between 7.6% and 10% doesn't sound like much until you run it through Kelly and realize you've been undersizing every bet. Or worse — you've been *passing* on bets that clear your edge threshold against the fair line but not against the vigged one.

### Step 3: Size the bet

Kelly criterion tells you the optimal fraction of your bankroll to wager given your edge and the odds. Full Kelly maximizes long-run growth rate but is volatile — most practitioners use a fraction (quarter-Kelly, half-Kelly) to trade growth for survival.

**Fixed-odds (sportsbook):**

```python
from betting_math_kit import kelly_calibrated

stake, edge, fair, should_bet = kelly_calibrated(
    model_prob=0.60,
    home_odds=-110,
    away_odds=-110,
    kelly_fraction_mult=0.25,  # quarter-Kelly
    min_edge=0.03,             # don't bet below 3% true edge
)
# should_bet=True, stake ~3.3% of bankroll
```

**Pari-mutuel (horse racing):**

Pari-mutuel markets add two complications: takeout (the track's cut, typically 16% in the US) and pool-size constraints (your bet moves the odds against you).

```python
from betting_math_kit import compute_kelly_bet, size_race_bets

# Single runner
bet = compute_kelly_bet(
    selection_id=7,
    prob=0.35,
    odds_decimal=4.0,
    bankroll=5000,
    fraction=0.25,       # quarter-Kelly
    takeout=0.16,        # 16% track takeout
    pool_size=50_000,    # your bet impacts the pool
)
print(bet.bet_size)       # dollar amount
print(bet.reason)         # human-readable explanation
print(bet.pool_limited)   # True if pool constraint kicked in

# Entire race card with exposure cap
runners = [
    {"selection_id": 1, "prob": 0.35, "odds_decimal": 4.0},
    {"selection_id": 2, "prob": 0.25, "odds_decimal": 5.0, "pool_size": 20_000},
    {"selection_id": 3, "prob": 0.15, "odds_decimal": 8.0},
]
bets = size_race_bets(runners, bankroll=5000, max_race_exposure=0.15)
```

### Step 4: Evaluate your model

You placed the bets. Results came in. Now close the feedback loop.

```python
from betting_math_kit import brier_score, expected_calibration_error, clv_from_odds

# How well-calibrated are your probabilities?
bs = brier_score(predicted_probs, outcomes)        # lower is better
ece = expected_calibration_error(predicted_probs, outcomes)

# Are you beating the closing line?
# Positive CLV means the market moved toward your number after you bet.
val = clv_from_odds(opening_odds=-110, closing_odds=-130)  # +0.041
```

CLV is the single best indicator of long-term profitability. If you're consistently betting numbers that the market later moves toward, you have real edge — even if short-term variance says otherwise.

### Step 5: Stress-test before going live

Before risking real money, simulate what your strategy does over thousands of trials.

```python
from betting_math_kit import simulate_bankroll, risk_of_ruin

result = simulate_bankroll(
    edge=0.03,           # 3% true edge per bet
    odds_decimal=2.0,    # even money
    fraction=0.25,       # quarter-Kelly
    n_bets=1000,
    n_trials=10_000,
    seed=42,
)
print(f"Ruin rate: {result.ruin_rate:.1%}")
print(f"Median final bankroll: ${result.median_final:.0f}")
print(f"5th percentile: ${result.p5_final:.0f}")

# Or just get the ruin probability
rr = risk_of_ruin(edge=0.03, odds_decimal=2.0, fraction=0.25)
```

The 5th percentile is the number that matters. Median tells you the expected case. P5 tells you what happens when you run bad — and whether you survive it.

---

## De-vig methods: when to use which

All four methods answer the same question — "what are the fair probabilities?" — but make different assumptions about how the bookmaker distributes margin.

| Method | Assumption | Best for |
|--------|-----------|----------|
| **Multiplicative** | Margin is proportional to each side's probability. Favorite and longshot are both inflated by the same ratio. | General-purpose default. Most common in the industry. |
| **Power** | There exists an exponent *k* such that p1^k + p2^k = 1. Compresses the gap between favorite and longshot. | Heavy favorites (-300 and beyond), where multiplicative under-corrects the longshot. |
| **Additive** | Equal margin subtracted from each side (margin/2 per outcome). | Quick sanity checks. Least accurate for skewed lines — can produce negative probabilities before clamping. |
| **Shin** | Margin is a function of informed-bettor proportion (Shin 1991, 1992). More margin is loaded onto longshots because sharps disproportionately bet favorites. | Liquid markets where you trust the favorite-longshot bias is real. |

On symmetric odds (-110/-110) all four methods return the same answer. They diverge as the line gets lopsided — that's where your choice actually matters.

For n-outcome markets, multiplicative, power, and Shin are supported. Additive does not generalize well to n outcomes.

## Technical notes

- **Shin method** uses binary search (100 iterations, 1e-10 tolerance) over the informed-bettor proportion *z*. Falls back to multiplicative on numerical failure.
- **Power method** uses binary search over exponent *k*. For 2-outcome: *k* in [0.5, 2.0]. For n-outcome: [0.01, 5.0].
- **Kelly sizing** separates math from policy. `full_kelly_fraction()` is pure math. `compute_kelly_bet()` layers policy on top: caps, floors, pool-size limits, minimum edge gates. Keep these concerns separate or you'll never know which one is wrong.
- **Pari-mutuel takeout** defaults to 16% (US win bet standard). Adjust for your jurisdiction.
- **Pool-size limit** uses a simplified linear impact model. Real pool dynamics are more complex — your bet changes the odds, which changes the Kelly fraction, which changes the bet size. This library doesn't iterate that loop.
- **Simulation** uses Python's `random.Random` with optional seeding for reproducibility.

## Validation

All public functions validate inputs and raise typed exceptions:

| Exception | When |
|-----------|------|
| `InvalidOddsError` | American odds = 0, decimal odds <= 1 |
| `InvalidProbabilityError` | Probability outside [0, 1] |
| `InvalidBankrollError` | Bankroll <= 0 |
| `UnknownMethodError` | Unrecognized de-vig method string |

Unknown methods raise rather than silently falling back. I learned that one the hard way — a typo in a method string silently defaulting to multiplicative cost me a week of bad analysis before I noticed.

## Testing

```bash
pip install -e ".[dev]"
pytest
```

195 tests covering odds conversion, all four de-vig methods, n-outcome de-vig (multiplicative, power, Shin), Kelly sizing (fixed-odds and pari-mutuel), calibration metrics, Monte Carlo simulation, validation failures, round-trip invariants, monotonicity checks, and boundary conditions.

```bash
ruff check src/ tests/       # lint
ruff format src/ tests/      # format
mypy src/betting_math_kit/   # type check
```

CI runs on Python 3.10 - 3.13.

---

## Where this fits in the system

This is one piece of a larger sports betting system I've been building. The full thing includes agents, databases, RAG pipelines, and a lot of stuff that's too messy or too personal to open-source. These two repos are the clean, standalone layers:

- [**props-scorer**](https://github.com/bene-art/props-scorer) — The model. Takes player stats, returns probabilities.
- [**betting-math-kit**](https://github.com/bene-art/betting-math-kit) — The math. Takes probabilities, returns bet sizes.

props-scorer answers "what's going to happen?" This library answers "given what you think is going to happen, what should you do about it?"

## License

MIT

## Author

Benjamin Easington — [GitHub](https://github.com/bene-art)
