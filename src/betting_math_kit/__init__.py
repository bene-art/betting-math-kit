"""
betting-math-kit: Pure-Python sports betting math library.

Odds conversion, de-vigging, Kelly criterion, calibration metrics,
and Monte Carlo simulation. Zero dependencies.
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
from .metrics import (
    brier_score,
    calibration_buckets,
    clv,
    clv_from_odds,
    edge_bucket_analysis,
    expected_calibration_error,
    log_loss,
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
from .simulation import (
    SimulationResult,
    optimal_fraction_search,
    risk_of_ruin,
    simulate_bankroll,
)
from .types import (
    DevigMethod,
    DevigResult,
    EdgeResult,
    MultiOutcomeDevigResult,
    Side,
)

__version__ = "0.3.0"

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
    "SimulationResult",
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
    # Metrics & calibration
    "brier_score",
    "log_loss",
    "expected_calibration_error",
    "calibration_buckets",
    "clv",
    "clv_from_odds",
    "edge_bucket_analysis",
    # Simulation
    "simulate_bankroll",
    "risk_of_ruin",
    "optimal_fraction_search",
]
