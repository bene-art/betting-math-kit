"""
betting-math-kit: Pure-Python sports betting math library.

Odds conversion, de-vigging, Kelly criterion. Zero dependencies.
"""

from .devig import (
    devig,
    devig_additive,
    devig_multi,
    devig_multiplicative,
    devig_power,
    devig_shin,
    get_vig,
)
from .exceptions import (
    BettingMathError,
    InvalidBankrollError,
    InvalidOddsError,
    InvalidProbabilityError,
    UnknownMethodError,
)
from .kelly import (
    KellyBet,
    compute_kelly_bet,
    expected_roi,
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
from .types import (
    DevigMethod,
    DevigResult,
    EdgeResult,
    MultiOutcomeDevigResult,
    Side,
)

__version__ = "0.2.0"

__all__ = [
    # Version
    "__version__",
    # Types & enums
    "Side",
    "DevigMethod",
    "DevigResult",
    "MultiOutcomeDevigResult",
    "EdgeResult",
    "KellyBet",
    # Exceptions
    "BettingMathError",
    "InvalidOddsError",
    "InvalidProbabilityError",
    "InvalidBankrollError",
    "UnknownMethodError",
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
    "devig",
    "devig_multiplicative",
    "devig_power",
    "devig_additive",
    "devig_shin",
    "devig_multi",
    "get_vig",
    # Kelly criterion (pari-mutuel)
    "compute_kelly_bet",
    "full_kelly_fraction",
    "pool_size_limit",
    "expected_roi",
    "size_race_bets",
]
