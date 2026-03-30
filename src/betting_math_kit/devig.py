"""
De-vig algorithms: remove bookmaker margin to recover fair probabilities.

Four methods, each with different assumptions about how the bookmaker
allocates margin across outcomes:

- **Multiplicative** (most common): margin is proportional to each side's
  probability.  Best general-purpose default.
- **Power**: finds exponent *k* such that p1^k + p2^k = 1.  Better when
  odds are heavily skewed (e.g. -500 / +400).
- **Additive**: splits margin equally across outcomes.  Simple but least
  accurate for skewed lines.
- **Shin** (1991/1992): models margin as a function of informed-bettor
  proportion.  Best for sharp, liquid markets.

All four methods converge to the same answer on symmetric odds (e.g.
-110 / -110) and diverge as the line becomes more lopsided.

**When to use which:**

- Default to multiplicative.
- Use power for heavy favorites (-300 and beyond).
- Use Shin when you trust that the market is efficient and want
  to model the favorite-longshot bias.
- Avoid additive unless you want a quick sanity check.

**n-outcome markets:** Use :func:`devig_multi` for outrights, props
ladders, or any market with more than two mutually exclusive outcomes.
Currently only the multiplicative method is supported for n-outcome.
"""

from __future__ import annotations

from .exceptions import InvalidOddsError, UnknownMethodError
from .odds import american_to_decimal, decimal_to_implied_prob
from .types import DevigMethod, DevigResult, MultiOutcomeDevigResult

# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _validate_american_pair(home_odds: int, away_odds: int) -> None:
    """Raise on invalid American odds."""
    if home_odds == 0:
        raise InvalidOddsError("home_odds cannot be 0")
    if away_odds == 0:
        raise InvalidOddsError("away_odds cannot be 0")


# ---------------------------------------------------------------------------
# Two-outcome algorithms (internal, return raw tuples)
# ---------------------------------------------------------------------------


def _mult(home_impl: float, away_impl: float) -> tuple[float, float]:
    total = home_impl + away_impl
    return home_impl / total, away_impl / total


def _power(
    home_impl: float, away_impl: float, max_iter: int = 100
) -> tuple[float, float]:
    k_low, k_high = 0.5, 2.0
    k = 1.0
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


def _additive(home_impl: float, away_impl: float) -> tuple[float, float]:
    total = home_impl + away_impl
    margin = (total - 1.0) / 2

    fair_home = max(0.01, home_impl - margin)
    fair_away = max(0.01, away_impl - margin)
    total = fair_home + fair_away
    return fair_home / total, fair_away / total


def _shin_prob(impl_p: float, z: float, total: float) -> float:
    """Shin probability for a single outcome."""
    if z == 0:
        return impl_p / total
    denom = 2.0 * (1.0 - z)
    numerator = (z**2 + 4.0 * (1.0 - z) * impl_p / (1.0 - z)) ** 0.5 - z
    return float(numerator / denom)


def _shin(
    home_impl: float, away_impl: float, max_iter: int = 100
) -> tuple[float, float]:
    total = home_impl + away_impl
    z_low, z_high = 0.0, 0.5
    z = 0.0

    for _ in range(max_iter):
        z = (z_low + z_high) / 2
        if z >= 1:
            z = 0.99

        try:
            p1 = _shin_prob(home_impl, z, total)
            p2 = _shin_prob(away_impl, z, total)
            prob_sum = p1 + p2
            if abs(prob_sum - 1.0) < 1e-10:
                break
            elif prob_sum > 1:
                z_high = z
            else:
                z_low = z
        except (ValueError, ZeroDivisionError):
            return _mult(home_impl, away_impl)

    if z > 0:
        fair_home = _shin_prob(home_impl, z, total)
        fair_away = _shin_prob(away_impl, z, total)
    else:
        fair_home = home_impl / total
        fair_away = away_impl / total

    norm = fair_home + fair_away
    if norm > 0:
        return fair_home / norm, fair_away / norm
    return _mult(home_impl, away_impl)


def _dispatch(
    method: DevigMethod,
    home_impl: float,
    away_impl: float,
) -> tuple[float, float]:
    """Dispatch to the correct de-vig algorithm."""
    if method is DevigMethod.MULTIPLICATIVE:
        return _mult(home_impl, away_impl)
    elif method is DevigMethod.POWER:
        return _power(home_impl, away_impl)
    elif method is DevigMethod.ADDITIVE:
        return _additive(home_impl, away_impl)
    elif method is DevigMethod.SHIN:
        return _shin(home_impl, away_impl)
    else:
        return _mult(home_impl, away_impl)


# ---------------------------------------------------------------------------
# Public two-outcome API
# ---------------------------------------------------------------------------


def devig_multiplicative(home_odds: int, away_odds: int) -> DevigResult:
    """Multiplicative (proportional) margin removal.

    Args:
        home_odds: American odds for home side.
        away_odds: American odds for away side.

    Returns:
        :class:`DevigResult` with fair probabilities summing to 1.0.

    Raises:
        InvalidOddsError: If either odds value is 0.
    """
    _validate_american_pair(home_odds, away_odds)
    home_impl = decimal_to_implied_prob(american_to_decimal(home_odds))
    away_impl = decimal_to_implied_prob(american_to_decimal(away_odds))
    vig = home_impl + away_impl - 1.0
    fh, fa = _mult(home_impl, away_impl)
    return DevigResult(
        fair_home=fh, fair_away=fa, method=DevigMethod.MULTIPLICATIVE, vig=vig
    )


def devig_power(home_odds: int, away_odds: int) -> DevigResult:
    """Power method de-vig (better for uneven odds).

    Finds exponent *k* such that ``p1^k + p2^k = 1``.

    Args:
        home_odds: American odds for home side.
        away_odds: American odds for away side.

    Returns:
        :class:`DevigResult`.

    Raises:
        InvalidOddsError: If either odds value is 0.
    """
    _validate_american_pair(home_odds, away_odds)
    home_impl = decimal_to_implied_prob(american_to_decimal(home_odds))
    away_impl = decimal_to_implied_prob(american_to_decimal(away_odds))
    vig = home_impl + away_impl - 1.0
    fh, fa = _power(home_impl, away_impl)
    return DevigResult(fair_home=fh, fair_away=fa, method=DevigMethod.POWER, vig=vig)


def devig_additive(home_odds: int, away_odds: int) -> DevigResult:
    """Additive de-vig (equal margin removal from each side).

    Args:
        home_odds: American odds for home side.
        away_odds: American odds for away side.

    Returns:
        :class:`DevigResult`.

    Raises:
        InvalidOddsError: If either odds value is 0.
    """
    _validate_american_pair(home_odds, away_odds)
    home_impl = decimal_to_implied_prob(american_to_decimal(home_odds))
    away_impl = decimal_to_implied_prob(american_to_decimal(away_odds))
    vig = home_impl + away_impl - 1.0
    fh, fa = _additive(home_impl, away_impl)
    return DevigResult(fair_home=fh, fair_away=fa, method=DevigMethod.ADDITIVE, vig=vig)


def devig_shin(home_odds: int, away_odds: int) -> DevigResult:
    """Shin method de-vig (accounts for favorite-longshot bias).

    Based on Shin (1991, 1992) model of informed trading.

    Args:
        home_odds: American odds for home side.
        away_odds: American odds for away side.

    Returns:
        :class:`DevigResult`.

    Raises:
        InvalidOddsError: If either odds value is 0.
    """
    _validate_american_pair(home_odds, away_odds)
    home_impl = decimal_to_implied_prob(american_to_decimal(home_odds))
    away_impl = decimal_to_implied_prob(american_to_decimal(away_odds))
    vig = home_impl + away_impl - 1.0
    fh, fa = _shin(home_impl, away_impl)
    return DevigResult(fair_home=fh, fair_away=fa, method=DevigMethod.SHIN, vig=vig)


def devig(
    home_odds: int,
    away_odds: int,
    method: DevigMethod | str = DevigMethod.MULTIPLICATIVE,
) -> DevigResult:
    """Remove vig from a two-sided market.

    Args:
        home_odds: American odds for home side.
        away_odds: American odds for away side.
        method: A :class:`DevigMethod` enum value, or one of the strings
                ``"multiplicative"``, ``"power"``, ``"additive"``,
                ``"shin"``.

    Returns:
        :class:`DevigResult` with fair probabilities, method, and vig.

    Raises:
        InvalidOddsError: If either odds value is 0.
        UnknownMethodError: If *method* is not recognized.

    Examples:
        >>> r = devig(-110, -110)
        >>> round(r.fair_home, 1)
        0.5
    """
    # Coerce string → enum (raises ValueError on bad string)
    if isinstance(method, str):
        try:
            method = DevigMethod(method)
        except ValueError:
            raise UnknownMethodError(
                f"Unknown de-vig method {method!r}. "
                f"Valid: {[m.value for m in DevigMethod]}"
            ) from None

    _validate_american_pair(home_odds, away_odds)
    home_impl = decimal_to_implied_prob(american_to_decimal(home_odds))
    away_impl = decimal_to_implied_prob(american_to_decimal(away_odds))
    vig = home_impl + away_impl - 1.0

    fh, fa = _dispatch(method, home_impl, away_impl)
    return DevigResult(fair_home=fh, fair_away=fa, method=method, vig=vig)


# ---------------------------------------------------------------------------
# n-outcome de-vig
# ---------------------------------------------------------------------------


def devig_multi(
    odds_list: list[int],
    method: DevigMethod | str = DevigMethod.MULTIPLICATIVE,
) -> MultiOutcomeDevigResult:
    """Remove vig from an n-outcome market (outrights, props ladders, etc.).

    Currently only the **multiplicative** method is supported for n > 2.

    Args:
        odds_list: American odds for each outcome. Must have >= 2 entries.
                   None of the values may be 0.
        method: De-vig algorithm (only ``MULTIPLICATIVE`` for now).

    Returns:
        :class:`MultiOutcomeDevigResult` with fair probabilities in the
        same order as *odds_list*.

    Raises:
        InvalidOddsError: If any odds value is 0.
        ValueError: If fewer than 2 outcomes are provided.
        UnknownMethodError: If *method* is not ``MULTIPLICATIVE``.

    Examples:
        >>> r = devig_multi([200, 300, 150])
        >>> sum(r.fair_probs)  # doctest: +ELLIPSIS
        1.0...
    """
    if len(odds_list) < 2:
        raise ValueError("Need at least 2 outcomes for de-vigging")

    if isinstance(method, str):
        try:
            method = DevigMethod(method)
        except ValueError:
            raise UnknownMethodError(f"Unknown de-vig method {method!r}") from None

    if method is not DevigMethod.MULTIPLICATIVE:
        raise UnknownMethodError(
            f"n-outcome de-vig only supports MULTIPLICATIVE, got {method.value}"
        )

    implied = []
    for odds in odds_list:
        if odds == 0:
            raise InvalidOddsError("American odds cannot be 0")
        implied.append(decimal_to_implied_prob(american_to_decimal(odds)))

    total = sum(implied)
    vig = total - 1.0
    fair = tuple(p / total for p in implied)

    return MultiOutcomeDevigResult(
        fair_probs=fair, method=method, vig=vig, n_outcomes=len(odds_list)
    )


# ---------------------------------------------------------------------------
# Vig calculation
# ---------------------------------------------------------------------------


def get_vig(home_odds: int, away_odds: int) -> float:
    """Calculate the bookmaker's vig (juice / margin).

    Args:
        home_odds: American odds for home side.
        away_odds: American odds for away side.

    Returns:
        Vig as a decimal (0.048 = 4.8 % vig).

    Raises:
        InvalidOddsError: If either odds value is 0.

    Examples:
        >>> round(get_vig(-110, -110), 3)
        0.048
    """
    _validate_american_pair(home_odds, away_odds)
    home_impl = decimal_to_implied_prob(american_to_decimal(home_odds))
    away_impl = decimal_to_implied_prob(american_to_decimal(away_odds))
    return home_impl + away_impl - 1.0
