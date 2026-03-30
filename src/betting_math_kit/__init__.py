"""
betting-math-kit: Pure-Python sports betting math library.

Odds conversion, de-vigging, Kelly criterion, and position impact matrices.
Zero dependencies. Tested. Documented.
"""

from .devig import (
    DevigMethod,
    devig,
    devig_additive,
    devig_multiplicative,
    devig_power,
    devig_shin,
    get_vig,
)
from .kelly import (
    KellyBet,
    compute_kelly_bet,
    full_kelly_fraction,
    pool_size_limit,
    size_race_bets,
)
from .odds import (
    american_to_decimal,
    calculate_edge,
    calculate_edge_calibrated,
    decimal_to_american,
    decimal_to_implied_prob,
    implied_prob_to_decimal,
    kelly_calibrated,
    kelly_fraction,
)

__version__ = "0.1.0"

__all__ = [
    # Odds conversion
    "american_to_decimal",
    "decimal_to_american",
    "decimal_to_implied_prob",
    "implied_prob_to_decimal",
    # Edge calculation
    "calculate_edge",
    "calculate_edge_calibrated",
    "kelly_fraction",
    "kelly_calibrated",
    # De-vigging
    "DevigMethod",
    "devig",
    "devig_multiplicative",
    "devig_power",
    "devig_additive",
    "devig_shin",
    "get_vig",
    # Kelly criterion (pari-mutuel)
    "KellyBet",
    "compute_kelly_bet",
    "full_kelly_fraction",
    "pool_size_limit",
    "size_race_bets",
]
