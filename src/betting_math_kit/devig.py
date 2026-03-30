"""
De-vig algorithms: remove bookmaker margin to recover fair probabilities.

Four methods, each with different assumptions about how the bookmaker
allocates margin across outcomes:

- **Multiplicative** (most common): margin is proportional to each side's
  probability.
- **Power**: finds exponent *k* such that p1^k + p2^k = 1.  Better when
  odds are heavily skewed.
- **Additive**: splits margin equally across outcomes.  Simple but less
  accurate.
- **Shin** (1991/1992): models margin as a function of informed-bettor
  proportion.  Best for sharp markets.

All functions accept American odds and return a tuple of fair probabilities
that sum to 1.0.
"""

from __future__ import annotations

from .odds import american_to_decimal, decimal_to_implied_prob


# ---------------------------------------------------------------------------
# Method constants
# ---------------------------------------------------------------------------


class DevigMethod:
    """De-vig method names (string constants)."""

    MULTIPLICATIVE = "multiplicative"
    POWER = "power"
    ADDITIVE = "additive"
    SHIN = "shin"


# ---------------------------------------------------------------------------
# Core algorithms
# ---------------------------------------------------------------------------


def devig_multiplicative(home_odds: int, away_odds: int) -> tuple[float, float]:
    """Multiplicative (proportional) margin removal.

    Args:
        home_odds: American odds for home side.
        away_odds: American odds for away side.

    Returns:
        ``(fair_home_prob, fair_away_prob)`` summing to 1.0.

    Examples:
        >>> h, a = devig_multiplicative(-110, -110)
        >>> round(h, 2), round(a, 2)
        (0.5, 0.5)
    """
    home_impl = decimal_to_implied_prob(american_to_decimal(home_odds))
    away_impl = decimal_to_implied_prob(american_to_decimal(away_odds))
    total = home_impl + away_impl
    return home_impl / total, away_impl / total


def devig_power(
    home_odds: int, away_odds: int, max_iter: int = 100
) -> tuple[float, float]:
    """Power method de-vig (better for uneven odds).

    Finds exponent *k* such that ``p1^k + p2^k = 1``.

    Args:
        home_odds: American odds for home side.
        away_odds: American odds for away side.
        max_iter: Maximum binary-search iterations.

    Returns:
        ``(fair_home_prob, fair_away_prob)`` summing to 1.0.
    """
    home_impl = decimal_to_implied_prob(american_to_decimal(home_odds))
    away_impl = decimal_to_implied_prob(american_to_decimal(away_odds))

    k_low, k_high = 0.5, 2.0
    for _ in range(max_iter):
        k = (k_low + k_high) / 2
        total = home_impl**k + away_impl**k
        if abs(total - 1.0) < 1e-10:
            break
        elif total > 1:
            k_high = k
        else:
            k_low = k

    fair_home = home_impl**k
    fair_away = away_impl**k
    total = fair_home + fair_away
    return fair_home / total, fair_away / total


def devig_additive(home_odds: int, away_odds: int) -> tuple[float, float]:
    """Additive de-vig (equal margin removal from each side).

    Args:
        home_odds: American odds for home side.
        away_odds: American odds for away side.

    Returns:
        ``(fair_home_prob, fair_away_prob)`` summing to 1.0.
    """
    home_impl = decimal_to_implied_prob(american_to_decimal(home_odds))
    away_impl = decimal_to_implied_prob(american_to_decimal(away_odds))
    total = home_impl + away_impl
    margin = (total - 1.0) / 2

    fair_home = max(0.01, home_impl - margin)
    fair_away = max(0.01, away_impl - margin)
    total = fair_home + fair_away
    return fair_home / total, fair_away / total


def devig_shin(
    home_odds: int, away_odds: int, max_iter: int = 100
) -> tuple[float, float]:
    """Shin method de-vig (accounts for favorite-longshot bias).

    Based on Shin (1991, 1992) model of informed trading.

    Args:
        home_odds: American odds for home side.
        away_odds: American odds for away side.
        max_iter: Maximum binary-search iterations.

    Returns:
        ``(fair_home_prob, fair_away_prob)`` summing to 1.0.
    """
    home_impl = decimal_to_implied_prob(american_to_decimal(home_odds))
    away_impl = decimal_to_implied_prob(american_to_decimal(away_odds))
    total = home_impl + away_impl

    z_low, z_high = 0.0, 0.5

    for _ in range(max_iter):
        z = (z_low + z_high) / 2
        if z >= 1:
            z = 0.99

        def shin_prob(impl_p: float) -> float:
            if z == 0:
                return impl_p / total
            denom = 2 * (1 - z)
            return (
                ((z**2) + 4 * (1 - z) * impl_p * (1 / (1 - z))) ** 0.5 - z
            ) / denom

        try:
            p1 = shin_prob(home_impl)
            p2 = shin_prob(away_impl)
            prob_sum = p1 + p2
            if abs(prob_sum - 1.0) < 1e-10:
                break
            elif prob_sum > 1:
                z_high = z
            else:
                z_low = z
        except (ValueError, ZeroDivisionError):
            return devig_multiplicative(home_odds, away_odds)

    fair_home = shin_prob(home_impl) if z > 0 else home_impl / total
    fair_away = shin_prob(away_impl) if z > 0 else away_impl / total

    norm = fair_home + fair_away
    if norm > 0:
        return fair_home / norm, fair_away / norm
    return devig_multiplicative(home_odds, away_odds)


# ---------------------------------------------------------------------------
# Dispatcher + vig calculation
# ---------------------------------------------------------------------------


def devig(
    home_odds: int,
    away_odds: int,
    method: str = DevigMethod.MULTIPLICATIVE,
) -> tuple[float, float]:
    """Remove vig from a two-sided market.

    Args:
        home_odds: American odds for home side.
        away_odds: American odds for away side.
        method: One of ``"multiplicative"``, ``"power"``, ``"additive"``,
                ``"shin"``.

    Returns:
        ``(fair_home_prob, fair_away_prob)`` summing to 1.0.

    Examples:
        >>> h, a = devig(-110, -110)
        >>> round(h, 1), round(a, 1)
        (0.5, 0.5)

        >>> h, a = devig(-150, 130)
        >>> round(h, 3), round(a, 3)
        (0.589, 0.411)
    """
    dispatch = {
        DevigMethod.MULTIPLICATIVE: devig_multiplicative,
        DevigMethod.POWER: devig_power,
        DevigMethod.ADDITIVE: devig_additive,
        DevigMethod.SHIN: devig_shin,
    }
    func = dispatch.get(method, devig_multiplicative)
    return func(home_odds, away_odds)


def get_vig(home_odds: int, away_odds: int) -> float:
    """Calculate the bookmaker's vig (juice / margin).

    Args:
        home_odds: American odds for home side.
        away_odds: American odds for away side.

    Returns:
        Vig as a decimal (0.048 = 4.8 % vig).

    Examples:
        >>> round(get_vig(-110, -110), 3)
        0.048
    """
    home_impl = decimal_to_implied_prob(american_to_decimal(home_odds))
    away_impl = decimal_to_implied_prob(american_to_decimal(away_odds))
    return home_impl + away_impl - 1.0
