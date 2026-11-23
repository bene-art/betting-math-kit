"""
Odds conversion and basic edge/Kelly calculations.

Pure functions for converting between American, decimal, and implied
probability formats, plus edge and Kelly criterion computations.

All functions validate inputs and raise typed exceptions
(:class:`InvalidOddsError`, :class:`InvalidProbabilityError`) on bad data.
"""

from __future__ import annotations

from .exceptions import InvalidOddsError, InvalidProbabilityError
from .types import DevigMethod, EdgeResult, Side

# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _validate_american_odds(odds: int) -> None:
    """Raise if American odds are invalid."""
    if odds == 0:
        raise InvalidOddsError(
            "American odds cannot be 0. "
            "Use negative for favorites, positive for underdogs."
        )


def _validate_probability(prob: float, name: str = "probability") -> None:
    """Raise if probability is outside [0, 1]."""
    if prob < 0.0 or prob > 1.0:
        raise InvalidProbabilityError(f"{name} must be between 0 and 1, got {prob}")


def _validate_decimal_odds(decimal_odds: float) -> None:
    """Raise if decimal odds are not > 1."""
    if decimal_odds <= 1.0:
        raise InvalidOddsError(f"Decimal odds must be > 1.0, got {decimal_odds}")


# ---------------------------------------------------------------------------
# Odds conversion
# ---------------------------------------------------------------------------


def american_to_decimal(odds: int) -> float:
    """Convert American odds to decimal odds.

    Args:
        odds: American odds (e.g. -110, +150). Must not be 0.

    Returns:
        Decimal odds (always > 1.0).

    Raises:
        InvalidOddsError: If *odds* is 0.

    Examples:
        >>> american_to_decimal(-110)  # doctest: +ELLIPSIS
        1.909...
        >>> american_to_decimal(150)
        2.5
    """
    _validate_american_odds(odds)
    if odds > 0:
        return 1.0 + (odds / 100.0)
    else:
        return 1.0 + (100.0 / abs(odds))


def decimal_to_american(decimal_odds: float) -> int:
    """Convert decimal odds to American odds.

    Args:
        decimal_odds: Decimal odds (must be > 1.0).

    Returns:
        American odds (positive for underdogs, negative for favorites).

    Raises:
        InvalidOddsError: If *decimal_odds* <= 1.0.

    Examples:
        >>> decimal_to_american(2.5)
        150
        >>> decimal_to_american(1.5)
        -200
    """
    _validate_decimal_odds(decimal_odds)
    if decimal_odds >= 2.0:
        return int((decimal_odds - 1) * 100)
    else:
        return int(-100 / (decimal_odds - 1))


def decimal_to_implied_prob(decimal_odds: float) -> float:
    """Convert decimal odds to implied probability.

    Args:
        decimal_odds: Decimal odds (must be > 1.0).

    Returns:
        Implied probability in (0, 1).

    Raises:
        InvalidOddsError: If *decimal_odds* <= 1.0.

    Examples:
        >>> decimal_to_implied_prob(2.0)
        0.5
    """
    _validate_decimal_odds(decimal_odds)
    return 1.0 / decimal_odds


def implied_prob_to_decimal(prob: float) -> float:
    """Convert implied probability to decimal odds.

    Args:
        prob: Implied probability (must be in (0, 1]).

    Returns:
        Decimal odds (always > 1.0).

    Raises:
        InvalidProbabilityError: If *prob* <= 0 or *prob* > 1.

    Examples:
        >>> implied_prob_to_decimal(0.5)
        2.0
    """
    if prob <= 0.0 or prob > 1.0:
        raise InvalidProbabilityError(f"Probability must be in (0, 1], got {prob}")
    return 1.0 / prob


# ---------------------------------------------------------------------------
# Edge calculation
# ---------------------------------------------------------------------------


def calculate_edge(model_prob: float, book_odds: int) -> float:
    """Calculate raw betting edge (model prob minus implied prob).

    This is the **naive** version that does NOT account for vig.
    For proper edge calculation, use :func:`calculate_edge_calibrated`.

    Args:
        model_prob: Your estimated win probability in [0, 1].
        book_odds: Bookmaker's American odds.

    Returns:
        Edge as a decimal (0.05 = 5 % edge).

    Raises:
        InvalidProbabilityError: If *model_prob* is outside [0, 1].
        InvalidOddsError: If *book_odds* is 0.
    """
    _validate_probability(model_prob, "model_prob")
    decimal_odds = american_to_decimal(book_odds)
    implied_prob = decimal_to_implied_prob(decimal_odds)
    return model_prob - implied_prob


def calculate_edge_calibrated(
    model_prob: float,
    home_odds: int,
    away_odds: int,
    pick: Side | str = Side.HOME,
    method: DevigMethod | str = DevigMethod.MULTIPLICATIVE,
) -> EdgeResult:
    """Calculate TRUE edge using de-vigged fair probability.

    The naive :func:`calculate_edge` compares your model to the **vigged**
    implied probability, which overstates edge by the bookmaker's margin.
    This function de-vigs first, then measures edge against the fair line.

    Args:
        model_prob: Your model's probability for the pick, in [0, 1].
        home_odds: American odds for home side.
        away_odds: American odds for away side.
        pick: :attr:`Side.HOME` or :attr:`Side.AWAY` (strings ``"home"``
              / ``"away"`` accepted for convenience).
        method: De-vig algorithm (see :class:`DevigMethod`). Strings
                accepted for convenience.

    Returns:
        :class:`EdgeResult` with ``true_edge``, ``fair_prob``,
        ``raw_edge``, and metadata.

    Raises:
        InvalidProbabilityError: If *model_prob* is outside [0, 1].
        InvalidOddsError: If either odds value is 0.
        UnknownMethodError: If *method* is not a recognized de-vig algorithm.

    Examples:
        >>> r = calculate_edge_calibrated(0.60, -110, -110)
        >>> round(r.true_edge, 2)
        0.1
    """
    from .devig import devig  # avoid circular at module level

    _validate_probability(model_prob, "model_prob")

    # Coerce string to enum
    pick_enum = Side(pick) if isinstance(pick, str) else pick
    method_enum = DevigMethod(method) if isinstance(method, str) else method

    result = devig(home_odds, away_odds, method_enum)

    if pick_enum is Side.HOME:
        fair_prob = result.fair_home
        book_odds = home_odds
    else:
        fair_prob = result.fair_away
        book_odds = away_odds

    true_edge = model_prob - fair_prob
    implied_prob = decimal_to_implied_prob(american_to_decimal(book_odds))
    raw_edge = model_prob - implied_prob

    return EdgeResult(
        model_prob=model_prob,
        implied_prob=implied_prob,
        fair_prob=fair_prob,
        raw_edge=raw_edge,
        true_edge=true_edge,
        pick=pick_enum,
        method=method_enum,
    )


# ---------------------------------------------------------------------------
# Kelly criterion (fixed-odds)
# ---------------------------------------------------------------------------


def kelly_fraction(model_prob: float, book_odds: int) -> float:
    """Half-Kelly fraction for a fixed-odds bet.

    This is a convenience function that bakes in half-Kelly (0.5x) and
    a 25 % cap.  For full control over Kelly parameters, use
    :func:`kelly_calibrated`.

    Args:
        model_prob: Estimated win probability in [0, 1].
        book_odds: Bookmaker's American odds.

    Returns:
        Fraction of bankroll to stake, in [0.0, 0.25].

    Raises:
        InvalidProbabilityError: If *model_prob* is outside [0, 1].
        InvalidOddsError: If *book_odds* is 0.
    """
    _validate_probability(model_prob, "model_prob")
    decimal_odds = american_to_decimal(book_odds)
    b = decimal_odds - 1.0
    q = 1.0 - model_prob
    kelly = (b * model_prob - q) / b

    if kelly <= 0:
        return 0.0
    return min(kelly * 0.5, 0.25)


def kelly_calibrated(
    model_prob: float,
    home_odds: int,
    away_odds: int,
    pick: Side | str = Side.HOME,
    kelly_fraction_mult: float = 0.25,
    max_stake: float = 0.05,
    min_edge: float = 0.03,
    method: DevigMethod | str = DevigMethod.MULTIPLICATIVE,
) -> tuple[float, float, float, bool]:
    """Calibrated Kelly criterion with proper de-vigging.

    Uses quarter-Kelly by default and requires a minimum edge threshold
    before recommending a bet.

    .. note::

       This function mixes **math** (Kelly formula) with **policy**
       (max stake, min edge gate).  The policy defaults are conservative
       starting points — adjust them for your use case.

    Args:
        model_prob: Your model's probability for the pick, in [0, 1].
        home_odds: American odds for home side.
        away_odds: American odds for away side.
        pick: :attr:`Side.HOME` or :attr:`Side.AWAY`.
        kelly_fraction_mult: Kelly multiplier (0.25 = quarter-Kelly).
        max_stake: Maximum stake as fraction of bankroll.
        min_edge: Minimum true edge required to bet.
        method: De-vig algorithm.

    Returns:
        ``(stake_fraction, true_edge, fair_prob, should_bet)``

    Raises:
        InvalidProbabilityError: If *model_prob* is outside [0, 1].
        InvalidOddsError: If either odds value is 0.
    """
    edge_result = calculate_edge_calibrated(
        model_prob, home_odds, away_odds, pick, method
    )

    pick_enum = Side(pick) if isinstance(pick, str) else pick
    book_odds = home_odds if pick_enum is Side.HOME else away_odds
    decimal_odds = american_to_decimal(book_odds)
    b = decimal_odds - 1.0

    q = 1.0 - model_prob
    kelly = (b * model_prob - q) / b

    if kelly <= 0 or edge_result.true_edge < min_edge:
        return 0.0, edge_result.true_edge, edge_result.fair_prob, False

    stake = min(kelly * kelly_fraction_mult, max_stake)
    return stake, edge_result.true_edge, edge_result.fair_prob, True
