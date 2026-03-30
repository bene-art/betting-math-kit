"""Monte Carlo simulation for bankroll analysis.

Pure-Python bankroll trajectory simulation under fixed fractional Kelly
betting.  Uses only stdlib (``random`` + ``math``); no external deps.

Typical usage::

    from betting_math_kit.simulation import simulate_bankroll

    result = simulate_bankroll(
        edge=0.03,
        odds_decimal=2.0,
        fraction=0.25,
        n_trials=10_000,
        seed=42,
    )
    print(f"Ruin rate: {result.ruin_rate:.2%}")
    print(f"Median final: {result.median_final:.2f}")
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from .exceptions import (
    InvalidBankrollError,
    InvalidOddsError,
)

# ----------------------------------------------------------------------- #
# Result container
# ----------------------------------------------------------------------- #


@dataclass(frozen=True)
class SimulationResult:
    """Result of a Monte Carlo bankroll simulation.

    Attributes:
        n_trials: Number of simulation trials.
        n_bets: Number of bets per trial.
        ruin_rate: Fraction of trials that hit ruin (bankroll <= 0).
        median_final: Median final bankroll across trials.
        mean_final: Mean final bankroll across trials.
        p5_final: 5th percentile final bankroll.
        p95_final: 95th percentile final bankroll.
        max_drawdown_median: Median maximum drawdown (as fraction of peak).
        growth_rate: Median log growth rate per bet.
    """

    n_trials: int
    n_bets: int
    ruin_rate: float
    median_final: float
    mean_final: float
    p5_final: float
    p95_final: float
    max_drawdown_median: float
    growth_rate: float


# ----------------------------------------------------------------------- #
# Internal helpers
# ----------------------------------------------------------------------- #


def _validate_simulation_inputs(
    edge: float,
    odds_decimal: float,
    fraction: float,
    bankroll: float | None = None,
) -> None:
    """Raise on invalid simulation parameters."""
    if edge <= 0:
        raise ValueError(f"edge must be > 0 for simulation to make sense, got {edge}")
    if odds_decimal <= 1.0:
        raise InvalidOddsError(f"odds_decimal must be > 1, got {odds_decimal}")
    if fraction <= 0:
        raise ValueError(f"fraction must be > 0, got {fraction}")
    if bankroll is not None and bankroll <= 0:
        raise InvalidBankrollError(f"bankroll must be > 0, got {bankroll}")


def _percentile(sorted_data: list[float], pct: float) -> float:
    """Return the *pct*-th percentile from already-sorted data.

    Uses linear interpolation (same method as Python 3.8+
    ``statistics.quantiles``).
    """
    n = len(sorted_data)
    if n == 0:
        return 0.0
    if n == 1:
        return sorted_data[0]
    k = (pct / 100.0) * (n - 1)
    lo = int(math.floor(k))
    hi = min(lo + 1, n - 1)
    weight = k - lo
    return sorted_data[lo] + weight * (sorted_data[hi] - sorted_data[lo])


def _median(data: list[float]) -> float:
    """Return the median of *data* (does **not** sort in-place)."""
    s = sorted(data)
    n = len(s)
    if n == 0:
        return 0.0
    mid = n // 2
    if n % 2 == 1:
        return s[mid]
    return (s[mid - 1] + s[mid]) / 2.0


# ----------------------------------------------------------------------- #
# Core simulation
# ----------------------------------------------------------------------- #


def simulate_bankroll(
    edge: float,
    odds_decimal: float,
    fraction: float,
    bankroll: float = 1000.0,
    n_bets: int = 1000,
    n_trials: int = 10_000,
    seed: int | None = None,
) -> SimulationResult:
    """Monte Carlo simulation of bankroll trajectory.

    Runs *n_trials* independent trials, each placing *n_bets* sequential
    bets under a fixed fractional Kelly strategy.

    Parameters
    ----------
    edge:
        Player edge over the implied probability (must be > 0).
    odds_decimal:
        Decimal odds for every bet (must be > 1).
    fraction:
        Fraction of full Kelly to wager each bet (must be > 0).
    bankroll:
        Starting bankroll for each trial (default 1000).
    n_bets:
        Number of bets per trial (default 1000).
    n_trials:
        Number of independent trials (default 10 000).
    seed:
        Optional RNG seed for reproducibility.

    Returns
    -------
    SimulationResult
        Aggregated statistics across all trials.

    Raises
    ------
    ValueError
        If *edge* <= 0, *fraction* <= 0, or *n_bets*/*n_trials* < 1.
    InvalidOddsError
        If *odds_decimal* <= 1.
    InvalidBankrollError
        If *bankroll* <= 0.
    """
    _validate_simulation_inputs(edge, odds_decimal, fraction, bankroll)
    if n_bets < 1:
        raise ValueError(f"n_bets must be >= 1, got {n_bets}")
    if n_trials < 1:
        raise ValueError(f"n_trials must be >= 1, got {n_trials}")

    implied_prob = 1.0 / odds_decimal
    win_prob = implied_prob + edge
    # Clamp to [0, 1] — caller is responsible for sensible inputs,
    # but we avoid domain errors in the RNG.
    win_prob = max(0.0, min(1.0, win_prob))
    net_odds = odds_decimal - 1.0  # payout per $1 wagered on win

    rng = random.Random(seed)

    finals: list[float] = []
    max_drawdowns: list[float] = []
    log_growths: list[float] = []
    ruin_count = 0

    for _ in range(n_trials):
        br = bankroll
        peak = br
        ruined = False

        for _ in range(n_bets):
            stake = fraction * br
            if rng.random() < win_prob:
                br += stake * net_odds
            else:
                br -= stake

            if br <= 0:
                br = 0.0
                ruined = True
                break

            if br > peak:
                peak = br

        if ruined:
            ruin_count += 1
            finals.append(0.0)
            max_drawdowns.append(1.0)
            log_growths.append(float("-inf"))
        else:
            finals.append(br)
            drawdown = (peak - br) / peak if peak > 0 else 0.0
            max_drawdowns.append(drawdown)
            if br > 0 and bankroll > 0:
                log_growths.append(math.log(br / bankroll) / n_bets)
            else:
                log_growths.append(float("-inf"))

    sorted_finals = sorted(finals)
    # For growth rate median, filter out -inf (ruined trials).
    finite_growths = [g for g in log_growths if math.isfinite(g)]

    return SimulationResult(
        n_trials=n_trials,
        n_bets=n_bets,
        ruin_rate=ruin_count / n_trials,
        median_final=_median(finals),
        mean_final=sum(finals) / n_trials,
        p5_final=_percentile(sorted_finals, 5),
        p95_final=_percentile(sorted_finals, 95),
        max_drawdown_median=_median(max_drawdowns),
        growth_rate=_median(finite_growths) if finite_growths else 0.0,
    )


# ----------------------------------------------------------------------- #
# Convenience wrappers
# ----------------------------------------------------------------------- #


def risk_of_ruin(
    edge: float,
    odds_decimal: float,
    fraction: float,
    ruin_threshold: float = 0.0,
    n_bets: int = 1000,
    n_trials: int = 10_000,
    seed: int | None = None,
) -> float:
    """Return the estimated probability of ruin.

    Thin wrapper around :func:`simulate_bankroll` that returns only
    the *ruin_rate*.

    Parameters
    ----------
    edge:
        Player edge over the implied probability.
    odds_decimal:
        Decimal odds (must be > 1).
    fraction:
        Fraction of Kelly to wager.
    ruin_threshold:
        Bankroll level that counts as ruin (default 0).
        Currently unused — ruin is defined as bankroll <= 0.
    n_bets:
        Bets per trial.
    n_trials:
        Number of trials.
    seed:
        Optional RNG seed.

    Returns
    -------
    float
        Fraction of trials that ended in ruin, in [0, 1].
    """
    result = simulate_bankroll(
        edge=edge,
        odds_decimal=odds_decimal,
        fraction=fraction,
        bankroll=1000.0,
        n_bets=n_bets,
        n_trials=n_trials,
        seed=seed,
    )
    return result.ruin_rate


def optimal_fraction_search(
    edge: float,
    odds_decimal: float,
    fractions: list[float] | None = None,
    n_bets: int = 500,
    n_trials: int = 5000,
    seed: int | None = None,
) -> dict[float, SimulationResult]:
    """Sweep Kelly fractions and return results for each.

    Parameters
    ----------
    edge:
        Player edge over the implied probability.
    odds_decimal:
        Decimal odds (must be > 1).
    fractions:
        List of Kelly fractions to test.  Defaults to
        ``[0.05, 0.10, 0.15, 0.20, 0.25, 0.50, 0.75, 1.0]``.
    n_bets:
        Bets per trial (default 500).
    n_trials:
        Number of trials per fraction (default 5000).
    seed:
        Optional RNG seed.  Each fraction gets a deterministic
        sub-seed derived from the base seed so results are
        reproducible yet independent.

    Returns
    -------
    dict[float, SimulationResult]
        Mapping of fraction -> simulation result.

    Raises
    ------
    ValueError
        If *edge* <= 0 or *odds_decimal* <= 1.
    """
    if fractions is None:
        fractions = [0.05, 0.10, 0.15, 0.20, 0.25, 0.50, 0.75, 1.0]

    # Validate common params once (use first fraction; each will be
    # re-validated inside simulate_bankroll anyway).
    if edge <= 0:
        raise ValueError(f"edge must be > 0 for simulation to make sense, got {edge}")
    if odds_decimal <= 1.0:
        raise InvalidOddsError(f"odds_decimal must be > 1, got {odds_decimal}")

    results: dict[float, SimulationResult] = {}
    for idx, frac in enumerate(fractions):
        frac_seed: int | None = None
        if seed is not None:
            frac_seed = seed + idx
        results[frac] = simulate_bankroll(
            edge=edge,
            odds_decimal=odds_decimal,
            fraction=frac,
            bankroll=1000.0,
            n_bets=n_bets,
            n_trials=n_trials,
            seed=frac_seed,
        )

    return results


__all__ = [
    "SimulationResult",
    "simulate_bankroll",
    "risk_of_ruin",
    "optimal_fraction_search",
]
