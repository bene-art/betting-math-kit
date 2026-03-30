# betting-math-kit

Pure-Python sports betting math. Zero dependencies. Tested.

## What's in the box

| Module | What it does |
|--------|-------------|
| `odds` | Convert between American, decimal, and implied probability formats. Basic edge and Kelly calculations for fixed-odds markets. |
| `devig` | Remove bookmaker margin (vig) to recover fair probabilities. Four methods: multiplicative, power, additive, Shin. |
| `kelly` | Pari-mutuel Kelly criterion with pool-size liquidity constraints, friction adjustment (takeout), and race-level exposure caps. |

## Install

```bash
pip install betting-math-kit
```

Or from source:

```bash
git clone https://github.com/bene-art/betting-math-kit.git
cd betting-math-kit
pip install -e .
```

## Quick start

### Odds conversion

```python
from betting_math_kit import american_to_decimal, decimal_to_implied_prob

decimal = american_to_decimal(-150)   # 1.667
prob = decimal_to_implied_prob(decimal)  # 0.6
```

### De-vig a market

```python
from betting_math_kit import devig, get_vig

# Standard -110/-110 line
fair_home, fair_away = devig(-110, -110)
# (0.5, 0.5) -- the vig disappears

vig = get_vig(-110, -110)
# 0.048 (4.8% margin)

# Use the power method for skewed lines
fair_home, fair_away = devig(-300, 250, method="power")
```

### Calculate true edge

```python
from betting_math_kit import calculate_edge_calibrated

# Your model says 60% home win, book has -110/-110
true_edge, fair_prob, raw_edge = calculate_edge_calibrated(0.60, -110, -110)
# true_edge = 0.10 (10% edge vs fair 50%)
# raw_edge = 0.076 (7.6% vs vigged implied -- overstated!)
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
# should_bet = True, stake ~ 3.3% of bankroll
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
print(bet.bet_size)    # dollar amount
print(bet.reason)      # human-readable explanation
print(bet.pool_limited)  # True if pool constraint kicked in
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
| `multiplicative` | General use | Scales each implied prob proportionally. Most common. |
| `power` | Skewed lines | Finds exponent k where p1^k + p2^k = 1. More accurate for heavy favorites. |
| `additive` | Quick estimates | Subtracts equal margin from each side. Simple but least accurate. |
| `shin` | Sharp markets | Models margin as informed-bettor proportion (Shin 1991). Best for liquid markets. |

## Running tests

```bash
pip install pytest
pytest
```

## License

MIT
