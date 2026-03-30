"""
Kelly Criterion for pari-mutuel markets.

Fractional Kelly with pool-size liquidity constraints and friction-adjusted
sizing for pari-mutuel (e.g. horse racing) markets.

Core formula::

    f* = (b * p - q) / b

    where:
        b = net decimal odds - 1 (net payout per $1)
        p = estimated win probability
        q = 1 - p

Fractional Kelly::

    f_actual = fraction * f*

    At 0.25x Kelly:
        - Retains 25 % of Kelly growth rate
        - Reduces variance by 93.75 % (variance scales as fraction^2)
        - Much more robust to probability estimation error

Pool-size constraint (pari-mutuel specific)::

    Your bet moves the odds. With pool P and current odds O:
        max_bet ~ P / (O * impact_limit)
    where impact_limit is max acceptable odds impact (default 5 %).

References:
    Kelly, J.L. (1956). "A New Interpretation of Information Rate."
    Thorp, E.O. (2006). "The Kelly Criterion in Blackjack, Sports Betting."
    Benter, W. (1994). "Computer Based Horse Race Handicapping."
"""

from __future__ import annotations

from dataclasses import dataclass

from .exceptions import InvalidBankrollError, InvalidOddsError, InvalidProbabilityError

# ---------------------------------------------------------------------------
# Constants (defaults — override per call)
# ---------------------------------------------------------------------------

DEFAULT_FRACTION = 0.25
DEFAULT_TAKEOUT = 0.16
DEFAULT_IMPACT_LIMIT = 0.05
MIN_BET = 2.0
MAX_BANKROLL_FRACTION = 0.10


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class KellyBet:
    """Result of Kelly sizing for a single selection.

    Attributes:
        selection_id: Identifier for the selection (horse, runner, etc.).
        full_kelly: Full Kelly fraction of bankroll.
        fractional_kelly: Adjusted fraction (after multiplier).
        bet_size: Dollar amount to bet (after all constraints).
        edge: Estimated edge (p - 1/odds).
        expected_roi: Expected return on investment after friction.
        pool_limited: True if bet was reduced due to pool size.
        capped: True if bet was reduced due to max bankroll fraction.
        reason: Human-readable explanation.
    """

    selection_id: int
    full_kelly: float
    fractional_kelly: float
    bet_size: float
    edge: float
    expected_roi: float
    pool_limited: bool
    capped: bool
    reason: str


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _validate_kelly_inputs(
    prob: float, odds_decimal: float, bankroll: float | None = None
) -> None:
    """Validate common Kelly inputs."""
    if prob < 0.0 or prob > 1.0:
        raise InvalidProbabilityError(
            f"Probability must be in [0, 1], got {prob}"
        )
    if odds_decimal <= 1.0:
        raise InvalidOddsError(
            f"Decimal odds must be > 1.0, got {odds_decimal}"
        )
    if bankroll is not None and bankroll <= 0:
        raise InvalidBankrollError(
            f"Bankroll must be positive, got {bankroll}"
        )


# ---------------------------------------------------------------------------
# Core Kelly math (pure — no policy)
# ---------------------------------------------------------------------------


def full_kelly_fraction(
    prob: float,
    odds_decimal: float,
    takeout: float = DEFAULT_TAKEOUT,
) -> float:
    """Compute full Kelly fraction of bankroll to wager.

    This is the **pure math** layer — no caps, no floors, no policy.

    Args:
        prob: Estimated win probability in (0, 1).
        odds_decimal: Decimal odds (e.g. 4.0 for 3-to-1). Must be > 1.
        takeout: Pari-mutuel takeout rate (default 16 %).

    Returns:
        Kelly fraction in [0, 1]. Returns 0 if no edge after friction.

    Raises:
        InvalidProbabilityError: If *prob* is outside [0, 1].
        InvalidOddsError: If *odds_decimal* <= 1.

    Examples:
        >>> full_kelly_fraction(0.30, 5.0)  # doctest: +ELLIPSIS
        0.08...
    """
    _validate_kelly_inputs(prob, odds_decimal)

    if prob == 0.0 or prob == 1.0:
        return 0.0

    effective_odds = 1.0 + (odds_decimal - 1.0) * (1.0 - takeout)
    b = effective_odds - 1.0
    if b <= 0:
        return 0.0

    q = 1.0 - prob
    f_star = (b * prob - q) / b
    return max(0.0, f_star)


def pool_size_limit(
    pool_size: float,
    odds_decimal: float,
    impact_limit: float = DEFAULT_IMPACT_LIMIT,
) -> float:
    """Maximum bet size before significantly moving the odds.

    In pari-mutuel betting your bet enters the pool and changes the
    effective odds.  This returns the largest bet that keeps odds impact
    within *impact_limit*.

    Args:
        pool_size: Total dollars in the win pool (must be > 0).
        odds_decimal: Current decimal odds for this selection (must be > 1).
        impact_limit: Maximum acceptable fractional change in odds.

    Returns:
        Maximum bet size in dollars. Returns 0 if any input is invalid.

    Examples:
        >>> pool_size_limit(100_000, 20.0)
        250.0
    """
    if pool_size <= 0 or odds_decimal <= 1 or impact_limit <= 0:
        return 0.0
    return pool_size * impact_limit / odds_decimal


def expected_roi(prob: float, odds_decimal: float, takeout: float) -> float:
    """Expected ROI after takeout.

    Args:
        prob: Win probability in (0, 1).
        odds_decimal: Decimal odds (> 1).
        takeout: Pari-mutuel takeout rate.

    Returns:
        Expected ROI as a decimal (-0.1 = -10 %, 0.05 = +5 %).
    """
    effective_odds = 1.0 + (odds_decimal - 1.0) * (1.0 - takeout)
    return prob * effective_odds - 1.0


# ---------------------------------------------------------------------------
# Constrained Kelly (math + policy)
# ---------------------------------------------------------------------------


def compute_kelly_bet(
    selection_id: int,
    prob: float,
    odds_decimal: float,
    bankroll: float,
    fraction: float = DEFAULT_FRACTION,
    takeout: float = DEFAULT_TAKEOUT,
    pool_size: float | None = None,
    impact_limit: float = DEFAULT_IMPACT_LIMIT,
    min_bet: float = MIN_BET,
    max_fraction: float = MAX_BANKROLL_FRACTION,
) -> KellyBet:
    """Compute the Kelly-optimal bet size with all constraints.

    Pipeline:
        1. Compute full Kelly fraction (after friction).
        2. Apply fractional Kelly multiplier.
        3. Convert to dollar amount.
        4. Apply pool-size limit (if pool data available).
        5. Apply max bankroll fraction cap.
        6. Apply minimum bet threshold.

    .. note::

       Steps 4-6 are **policy** constraints layered on top of the pure
       Kelly math.  The defaults are conservative starting points.

    Args:
        selection_id: Identifier for the selection.
        prob: Estimated win probability in (0, 1).
        odds_decimal: Decimal odds (must be > 1).
        bankroll: Current bankroll in dollars (must be > 0).
        fraction: Kelly fraction multiplier (default 0.25 = quarter-Kelly).
        takeout: Pari-mutuel takeout (default 16 %).
        pool_size: Total win pool in dollars (None if unknown).
        impact_limit: Max odds impact from our bet (default 5 %).
        min_bet: Minimum bet size in dollars (default $2).
        max_fraction: Max fraction of bankroll per bet (default 10 %).

    Returns:
        :class:`KellyBet` with sizing details and constraint flags.

    Raises:
        InvalidProbabilityError: If *prob* is outside [0, 1].
        InvalidOddsError: If *odds_decimal* <= 1.
        InvalidBankrollError: If *bankroll* <= 0.
    """
    _validate_kelly_inputs(prob, odds_decimal, bankroll)

    fk = full_kelly_fraction(prob, odds_decimal, takeout)

    if fk <= 0:
        return KellyBet(
            selection_id=selection_id,
            full_kelly=0.0,
            fractional_kelly=0.0,
            bet_size=0.0,
            edge=prob - 1.0 / odds_decimal,
            expected_roi=0.0,
            pool_limited=False,
            capped=False,
            reason="no edge after friction",
        )

    frac_kelly = fk * fraction
    bet = frac_kelly * bankroll

    pool_limited = False
    if pool_size is not None and pool_size > 0:
        max_pool_bet = pool_size_limit(pool_size, odds_decimal, impact_limit)
        if bet > max_pool_bet:
            bet = max_pool_bet
            pool_limited = True

    capped = False
    max_bet = bankroll * max_fraction
    if bet > max_bet:
        bet = max_bet
        capped = True

    if bet < min_bet:
        return KellyBet(
            selection_id=selection_id,
            full_kelly=fk,
            fractional_kelly=frac_kelly,
            bet_size=0.0,
            edge=prob - 1.0 / odds_decimal,
            expected_roi=expected_roi(prob, odds_decimal, takeout),
            pool_limited=pool_limited,
            capped=capped,
            reason=f"bet ${bet:.2f} below minimum ${min_bet:.2f}",
        )

    bet = round(bet)
    bet = max(min_bet, bet)

    edge = prob - 1.0 / odds_decimal
    roi = expected_roi(prob, odds_decimal, takeout)

    parts = [f"Kelly {fk:.1%} x {fraction:.0%} = {frac_kelly:.2%}"]
    if pool_limited:
        parts.append("pool-limited")
    if capped:
        parts.append("bankroll-capped")
    parts.append(f"edge {edge:.1%}, ROI {roi:+.1%}")

    return KellyBet(
        selection_id=selection_id,
        full_kelly=fk,
        fractional_kelly=frac_kelly,
        bet_size=float(bet),
        edge=edge,
        expected_roi=roi,
        pool_limited=pool_limited,
        capped=capped,
        reason=", ".join(parts),
    )


# ---------------------------------------------------------------------------
# Race-level sizing
# ---------------------------------------------------------------------------


def size_race_bets(
    bets: list[dict],
    bankroll: float,
    fraction: float = DEFAULT_FRACTION,
    takeout: float = DEFAULT_TAKEOUT,
    max_race_exposure: float = 0.15,
) -> list[KellyBet]:
    """Size all bets in a race with per-race exposure cap.

    Args:
        bets: List of dicts with keys ``selection_id``, ``prob``,
              ``odds_decimal``, and optionally ``pool_size``.
        bankroll: Current bankroll in dollars (must be > 0).
        fraction: Kelly fraction multiplier.
        takeout: Pari-mutuel takeout.
        max_race_exposure: Max total fraction of bankroll per race.

    Returns:
        List of :class:`KellyBet`, sorted by ``bet_size`` descending.
        Only includes selections with positive bet sizes.

    Raises:
        InvalidBankrollError: If *bankroll* <= 0.
    """
    if bankroll <= 0:
        raise InvalidBankrollError(f"Bankroll must be positive, got {bankroll}")

    sized = []
    for bet_info in bets:
        kb = compute_kelly_bet(
            selection_id=bet_info["selection_id"],
            prob=bet_info["prob"],
            odds_decimal=bet_info["odds_decimal"],
            bankroll=bankroll,
            fraction=fraction,
            takeout=takeout,
            pool_size=bet_info.get("pool_size"),
        )
        if kb.bet_size > 0:
            sized.append(kb)

    total_exposure = sum(kb.bet_size for kb in sized)
    max_exposure = bankroll * max_race_exposure

    if total_exposure > max_exposure and total_exposure > 0:
        scale = max_exposure / total_exposure
        scaled = []
        for kb in sized:
            new_bet = max(MIN_BET, round(kb.bet_size * scale))
            scaled.append(
                KellyBet(
                    selection_id=kb.selection_id,
                    full_kelly=kb.full_kelly,
                    fractional_kelly=kb.fractional_kelly,
                    bet_size=float(new_bet),
                    edge=kb.edge,
                    expected_roi=kb.expected_roi,
                    pool_limited=kb.pool_limited,
                    capped=True,
                    reason=kb.reason + f", race-exposure scaled {scale:.0%}",
                )
            )
        sized = scaled

    sized.sort(key=lambda kb: -kb.bet_size)
    return sized
