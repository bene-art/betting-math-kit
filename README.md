# betting-math-kit

Pure-Python sports betting math. Zero dependencies. Typed. Tested.

## What's in the box

| Module | What it does |
|--------|-------------|
| `odds` | Convert between American, decimal, and implied probability. Edge calculation (naive and calibrated). Fixed-odds Kelly. |
| `devig` | Remove bookmaker margin (vig) to recover fair probabilities. Four methods: multiplicative, power, additive, Shin. Supports 2-outcome and n-outcome markets. |
| `kelly` | Pari-mutuel Kelly criterion with pool-size liquidity constraints, takeout friction, and race-level exposure caps. |
| `types` | Domain types: `Side`, `DevigMethod` (enums), `DevigResult`, `EdgeResult`, `MultiOutcomeDevigResult`, `KellyBet` (frozen dataclasses). |
| `exceptions` | `InvalidOddsError`, `InvalidProbabilityError`, `InvalidBankrollError`, `UnknownMethodError`. |

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

## Quick start

### Odds conversion

```python
from betting_math_kit import american_to_decimal, decimal_to_implied_prob

decimal = american_to_decimal(-150)      # 1.667
prob = decimal_to_implied_prob(decimal)   # 0.6
```

### De-vig a two-sided market

```python
from betting_math_kit import devig, get_vig, DevigMethod

r = devig(-110, -110)
# DevigResult(fair_home=0.5, fair_away=0.5, method=MULTIPLICATIVE, vig=0.048)

r = devig(-300, 250, method=DevigMethod.POWER)
# Uses the power method for skewed lines

vig = get_vig(-110, -110)  # 0.048 (4.8% margin)
```

### De-vig an n-outcome market (outrights, props)

```python
from betting_math_kit import devig_multi

r = devig_multi([200, 300, 150, 800])
# MultiOutcomeDevigResult with fair_probs summing to 1.0
print(r.fair_probs)  # (0.31, 0.21, 0.36, 0.10) approximately
```

### Calculate true edge

```python
from betting_math_kit import calculate_edge_calibrated

r = calculate_edge_calibrated(0.60, -110, -110)
# EdgeResult with:
#   r.true_edge = 0.10  (10% edge vs fair 50%)
#   r.raw_edge  = 0.076 (7.6% vs vigged implied -- overstated!)
#   r.fair_prob = 0.50
#   r.method    = DevigMethod.MULTIPLICATIVE
```

### Kelly criterion (fixed-odds)

```python
from betting_math_kit import kelly_calibrated

stake, edge, fair, should_bet = kelly_calibrated(
    model_prob=0.60,
    home_odds=-110,
    away_odds=-110,
    kelly_fraction_mult=0.25,  # quarter-Kelly
)
# should_bet=True, stake~3.3% of bankroll
```

### Kelly criterion (pari-mutuel / horse racing)

```python
from betting_math_kit import compute_kelly_bet

bet = compute_kelly_bet(
    selection_id=7,
    prob=0.35,
    odds_decimal=4.0,
    bankroll=5000,
    fraction=0.25,       # quarter-Kelly
    takeout=0.16,        # 16% track takeout
    pool_size=50_000,    # win pool size (optional)
)
print(bet.bet_size)       # dollar amount
print(bet.reason)         # human-readable explanation
print(bet.pool_limited)   # True if pool constraint kicked in
```

### Size an entire race

```python
from betting_math_kit import size_race_bets

runners = [
    {"selection_id": 1, "prob": 0.35, "odds_decimal": 4.0},
    {"selection_id": 2, "prob": 0.25, "odds_decimal": 5.0, "pool_size": 20_000},
    {"selection_id": 3, "prob": 0.15, "odds_decimal": 8.0},
]

bets = size_race_bets(runners, bankroll=5000, max_race_exposure=0.15)
for b in bets:
    print(f"#{b.selection_id}: ${b.bet_size:.0f} (edge {b.edge:.1%})")
```

## De-vig methods

| Method | Best for | How it works |
|--------|----------|-------------|
| `MULTIPLICATIVE` | General use | Scales each implied prob proportionally. Most common. |
| `POWER` | Skewed lines (-300+) | Finds exponent k where p1^k + p2^k = 1. More accurate for heavy favorites. |
| `ADDITIVE` | Quick estimates | Subtracts equal margin from each side. Simple but least accurate. |
| `SHIN` | Sharp markets | Models margin as informed-bettor proportion (Shin 1991). Best for liquid markets with favorite-longshot bias. |

All four methods converge on symmetric odds and diverge as the line becomes more lopsided. Default to multiplicative unless you have a reason not to.

## Assumptions and caveats

- **Two-outcome de-vig** assumes a binary market (moneyline, spread, total). For n-outcome markets, use `devig_multi()`.
- **n-outcome de-vig** currently only supports the multiplicative method. Power and Shin for n > 2 are not yet implemented.
- **Shin method** uses binary search with 100 iterations and 1e-10 tolerance. Falls back to multiplicative on numerical failure.
- **Power method** uses binary search with k in [0.5, 2.0]. This range covers typical bookmaker margins but may not converge for extreme synthetic inputs.
- **Kelly sizing** is pure math. The `compute_kelly_bet()` function layers policy constraints (caps, floors, pool limits) on top. Separate your math from your risk policy.
- **Pari-mutuel takeout** defaults to 16% (US win bet standard). Adjust for your jurisdiction.
- **Pool-size limit** uses a simplified linear model. Real pool dynamics are more complex.

## Validation

All public functions validate inputs and raise typed exceptions:

| Exception | When |
|-----------|------|
| `InvalidOddsError` | American odds = 0, decimal odds <= 1 |
| `InvalidProbabilityError` | Probability outside [0, 1] |
| `InvalidBankrollError` | Bankroll <= 0 |
| `UnknownMethodError` | Unrecognized de-vig method string |

Unknown de-vig methods **raise** rather than silently falling back.

## Running tests

```bash
pip install -e ".[dev]"
pytest
```

141 tests covering odds conversion, all four de-vig methods, n-outcome de-vig, Kelly sizing, validation failures, round-trip invariants, monotonicity checks, and boundary conditions.

## Development

```bash
ruff check src/ tests/    # lint
ruff format src/ tests/   # format
mypy src/betting_math_kit/  # type check
```

## License

MIT
