"""
Odds conversion and basic edge/Kelly calculations.

Pure functions for converting between American, decimal, and implied
probability formats, plus edge and Kelly criterion computations.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Odds conversion
# ---------------------------------------------------------------------------


def american_to_decimal(odds: int) -> float:
    """Convert American odds to decimal odds.

    Args:
        odds: American odds (e.g. -110, +150).

    Returns:
        Decimal odds (e.g. 1.909, 2.5).

    Examples:
        >>> american_to_decimal(-110)
        1.9090909090909092
        >>> american_to_decimal(150)
        2.5
    """
    if odds > 0:
        return 1 + (odds / 100)
    else:
        return 1 + (100 / abs(odds))


def decimal_to_american(decimal_odds: float) -> int:
    """Convert decimal odds to American odds.

    Args:
        decimal_odds: Decimal odds (e.g. 2.5).

    Returns:
        American odds (e.g. +150 or -110).

    Examples:
        >>> decimal_to_american(2.5)
        150
        >>> decimal_to_american(1.5)
        -200
    """
    if decimal_odds >= 2.0:
        return int((decimal_odds - 1) * 100)
    else:
        return int(-100 / (decimal_odds - 1))


def decimal_to_implied_prob(decimal_odds: float) -> float:
    """Convert decimal odds to implied probability.

    Args:
        decimal_odds: Decimal odds (e.g. 2.0).

    Returns:
        Implied probability (e.g. 0.5).

    Examples:
        >>> decimal_to_implied_prob(2.0)
        0.5
        >>> decimal_to_implied_prob(4.0)
        0.25
    """
    return 1 / decimal_odds


def implied_prob_to_decimal(prob: float) -> float:
    """Convert implied probability to decimal odds.

    Args:
        prob: Implied probability (0 < prob <= 1).

    Returns:
        Decimal odds.

    Examples:
        >>> implied_prob_to_decimal(0.5)
        2.0
        >>> implied_prob_to_decimal(0.25)
        4.0
    """
    if prob <= 0:
        raise ValueError("Probability must be positive")
    return 1 / prob


# ---------------------------------------------------------------------------
# Edge calculation
# ---------------------------------------------------------------------------


def calculate_edge(model_prob: float, book_odds: int) -> float:
    """Calculate raw betting edge (model prob minus implied prob).

    This is the simple version that does NOT account for vig.
    For proper edge calculation, use ``calculate_edge_calibrated()``.

    Args:
        model_prob: Your estimated win probability (0-1).
        book_odds: Bookmaker's American odds.

    Returns:
        Edge as a decimal (0.05 = 5% edge).

    Examples:
        >>> calculate_edge(0.55, -110)  # doctest: +ELLIPSIS
        0.025...
    """
    decimal_odds = american_to_decimal(book_odds)
    implied_prob = decimal_to_implied_prob(decimal_odds)
    return model_prob - implied_prob


def calculate_edge_calibrated(
    model_prob: float,
    home_odds: int,
    away_odds: int,
    pick: str = "home",
    method: str = "multiplicative",
) -> tuple[float, float, float]:
    """Calculate TRUE edge using de-vigged fair probability.

    This is the correct way to calculate edge. The simple ``calculate_edge()``
    compares your model to the vigged implied probability, which creates
    phantom edges that are really just margin allocation.

    Args:
        model_prob: Your model's probability for the pick (0-1).
        home_odds: American odds for home side.
        away_odds: American odds for away side.
        pick: ``"home"`` or ``"away"``.
        method: De-vig method (see ``devig()``).

    Returns:
        ``(true_edge, fair_prob, raw_edge)``

        - **true_edge**: edge vs de-vigged fair probability (use this).
        - **fair_prob**: the de-vigged fair probability.
        - **raw_edge**: edge vs raw implied probability (for comparison).

    Examples:
        Model says 60 % for home, book has -110 / -110::

            >>> true, fair, raw = calculate_edge_calibrated(0.60, -110, -110)
            >>> round(true, 2), round(fair, 2), round(raw, 3)
            (0.1, 0.5, 0.076)
    """
    from .devig import devig  # avoid circular at module level

    fair_home, fair_away = devig(home_odds, away_odds, method)

    fair_prob = fair_home if pick == "home" else fair_away
    book_odds = home_odds if pick == "home" else away_odds

    true_edge = model_prob - fair_prob
    implied_prob = decimal_to_implied_prob(american_to_decimal(book_odds))
    raw_edge = model_prob - implied_prob

    return true_edge, fair_prob, raw_edge


# ---------------------------------------------------------------------------
# Kelly criterion (fixed-odds)
# ---------------------------------------------------------------------------


def kelly_fraction(model_prob: float, book_odds: int) -> float:
    """Half-Kelly fraction for a fixed-odds bet.

    Args:
        model_prob: Estimated win probability (0-1).
        book_odds: Bookmaker's American odds.

    Returns:
        Fraction of bankroll to stake (0.0-0.25, capped).

    Examples:
        >>> kelly_fraction(0.60, -110)  # doctest: +ELLIPSIS
        0.0...
    """
    decimal_odds = american_to_decimal(book_odds)
    b = decimal_odds - 1
    q = 1 - model_prob
    kelly = (b * model_prob - q) / b

    if kelly <= 0:
        return 0.0
    return min(kelly * 0.5, 0.25)


def kelly_calibrated(
    model_prob: float,
    home_odds: int,
    away_odds: int,
    pick: str = "home",
    kelly_fraction_mult: float = 0.25,
    max_stake: float = 0.05,
    min_edge: float = 0.03,
    method: str = "multiplicative",
) -> tuple[float, float, float, bool]:
    """Calibrated Kelly criterion with proper de-vigging.

    Uses quarter-Kelly by default and requires a minimum edge threshold
    before recommending a bet.

    Args:
        model_prob: Your model's probability for the pick (0-1).
        home_odds: American odds for home side.
        away_odds: American odds for away side.
        pick: ``"home"`` or ``"away"``.
        kelly_fraction_mult: Kelly multiplier (0.25 = quarter-Kelly).
        max_stake: Maximum stake as fraction of bankroll.
        min_edge: Minimum edge required to bet.
        method: De-vig method.

    Returns:
        ``(stake_fraction, true_edge, fair_prob, should_bet)``

    Examples:
        >>> stake, edge, fair, bet = kelly_calibrated(0.60, -110, -110)
        >>> bet
        True
    """
    true_edge, fair_prob, _ = calculate_edge_calibrated(
        model_prob, home_odds, away_odds, pick, method
    )

    book_odds = home_odds if pick == "home" else away_odds
    decimal_odds = american_to_decimal(book_odds)
    b = decimal_odds - 1

    q = 1 - model_prob
    kelly = (b * model_prob - q) / b

    if kelly <= 0 or true_edge < min_edge:
        return 0.0, true_edge, fair_prob, False

    stake = min(kelly * kelly_fraction_mult, max_stake)
    return stake, true_edge, fair_prob, True
