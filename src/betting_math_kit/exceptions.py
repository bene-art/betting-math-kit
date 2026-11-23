"""betting-math-kit exceptions."""


class BettingMathError(Exception):
    """Base exception for betting-math-kit."""


class InvalidOddsError(BettingMathError, ValueError):
    """Raised when odds are invalid (e.g. American odds of 0, decimal odds <= 1)."""


class InvalidProbabilityError(BettingMathError, ValueError):
    """Raised when a probability is outside [0, 1]."""


class InvalidBankrollError(BettingMathError, ValueError):
    """Raised when bankroll is non-positive."""


class UnknownMethodError(BettingMathError, ValueError):
    """Raised when a de-vig or other method name is not recognized."""
