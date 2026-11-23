"""
Calibration and evaluation metrics for sports betting models.

Pure-Python functions for measuring prediction quality, calibration,
closing line value, and edge-bucket analysis. Zero dependencies.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from .exceptions import InvalidProbabilityError
from .odds import american_to_decimal, decimal_to_implied_prob

# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _validate_prob_list(probs: list[float], name: str = "probs") -> None:
    """Raise InvalidProbabilityError if any value is outside [0, 1]."""
    for i, p in enumerate(probs):
        if p < 0.0 or p > 1.0:
            raise InvalidProbabilityError(
                f"{name}[{i}] must be between 0 and 1, got {p}"
            )


def _validate_outcome_list(outcomes: list[int]) -> None:
    """Raise ValueError if any outcome is not 0 or 1."""
    for i, o in enumerate(outcomes):
        if o not in (0, 1):
            raise ValueError(f"outcomes[{i}] must be 0 or 1, got {o}")


def _validate_matched_lengths(
    a: Sequence[object],
    b: Sequence[object],
    name_a: str = "probs",
    name_b: str = "outcomes",
) -> None:
    """Raise ValueError if two lists differ in length."""
    if len(a) != len(b):
        raise ValueError(
            f"{name_a} and {name_b} must have the same length, "
            f"got {len(a)} and {len(b)}"
        )


def _validate_nonempty(lst: Sequence[object], name: str = "probs") -> None:
    """Raise ValueError if list is empty."""
    if not lst:
        raise ValueError(f"{name} must not be empty")


# ---------------------------------------------------------------------------
# Scoring metrics
# ---------------------------------------------------------------------------


def brier_score(probs: list[float], outcomes: list[int]) -> float:
    """Mean squared error between predicted probabilities and outcomes.

    Lower is better. For binary predictions the range is [0, 2], though
    well-calibrated models will score well below 0.25.

    Args:
        probs: Predicted probabilities, each in [0, 1].
        outcomes: Binary outcomes (0 or 1), same length as *probs*.

    Returns:
        Brier score (mean squared error).

    Raises:
        InvalidProbabilityError: If any probability is outside [0, 1].
        ValueError: If lists differ in length or are empty.

    Examples:
        >>> round(brier_score([0.9, 0.1], [1, 0]), 2)
        0.01
        >>> brier_score([0.5, 0.5], [1, 0])
        0.25
    """
    _validate_nonempty(probs, "probs")
    _validate_matched_lengths(probs, outcomes)
    _validate_prob_list(probs)
    _validate_outcome_list(outcomes)

    n = len(probs)
    total = 0.0
    for p, y in zip(probs, outcomes, strict=False):
        total += (p - y) ** 2
    return total / n


def log_loss(
    probs: list[float],
    outcomes: list[int],
    eps: float = 1e-15,
) -> float:
    """Negative log-likelihood per prediction (cross-entropy loss).

    Probabilities are clamped to [eps, 1 - eps] to avoid log(0).

    Args:
        probs: Predicted probabilities, each in [0, 1].
        outcomes: Binary outcomes (0 or 1), same length as *probs*.
        eps: Clamp bound to prevent log(0). Defaults to ``1e-15``.

    Returns:
        Mean negative log-likelihood (lower is better).

    Raises:
        InvalidProbabilityError: If any probability is outside [0, 1].
        ValueError: If lists differ in length or are empty.

    Examples:
        >>> round(log_loss([0.9, 0.1], [1, 0]), 4)
        0.1054
    """
    _validate_nonempty(probs, "probs")
    _validate_matched_lengths(probs, outcomes)
    _validate_prob_list(probs)
    _validate_outcome_list(outcomes)

    n = len(probs)
    total = 0.0
    for p, y in zip(probs, outcomes, strict=False):
        p_clamped = max(eps, min(p, 1.0 - eps))
        if y == 1:
            total += -math.log(p_clamped)
        else:
            total += -math.log(1.0 - p_clamped)
    return total / n


# ---------------------------------------------------------------------------
# Calibration
# ---------------------------------------------------------------------------


def calibration_buckets(
    probs: list[float],
    outcomes: list[int],
    n_bins: int = 10,
) -> list[dict]:
    """Bin predictions into equal-width buckets and report calibration.

    Args:
        probs: Predicted probabilities, each in [0, 1].
        outcomes: Binary outcomes (0 or 1), same length as *probs*.
        n_bins: Number of equal-width bins. Defaults to 10.

    Returns:
        List of dicts (one per non-empty bin) with keys:

        - ``bin_lower``: Lower bound of the bin (inclusive).
        - ``bin_upper``: Upper bound of the bin (exclusive, except last).
        - ``count``: Number of predictions in the bin.
        - ``avg_predicted``: Mean predicted probability in the bin.
        - ``avg_actual``: Observed win rate in the bin.
        - ``gap``: ``avg_predicted - avg_actual`` (positive = overconfident).

    Raises:
        InvalidProbabilityError: If any probability is outside [0, 1].
        ValueError: If lists differ in length or are empty,
            or *n_bins* < 1.

    Examples:
        >>> buckets = calibration_buckets([0.1, 0.9], [0, 1], n_bins=2)
        >>> len(buckets)
        2
        >>> buckets[0]["avg_predicted"]
        0.1
    """
    _validate_nonempty(probs, "probs")
    _validate_matched_lengths(probs, outcomes)
    _validate_prob_list(probs)
    _validate_outcome_list(outcomes)
    if n_bins < 1:
        raise ValueError(f"n_bins must be >= 1, got {n_bins}")

    bin_width = 1.0 / n_bins

    # Accumulate per-bin sums
    bin_pred_sums: list[float] = [0.0] * n_bins
    bin_outcome_sums: list[float] = [0.0] * n_bins
    bin_counts: list[int] = [0] * n_bins

    for p, y in zip(probs, outcomes, strict=False):
        idx = int(p / bin_width)
        # Clamp p == 1.0 into the last bin
        if idx >= n_bins:
            idx = n_bins - 1
        bin_pred_sums[idx] += p
        bin_outcome_sums[idx] += y
        bin_counts[idx] += 1

    result: list[dict] = []
    for i in range(n_bins):
        if bin_counts[i] == 0:
            continue
        avg_pred = bin_pred_sums[i] / bin_counts[i]
        avg_actual = bin_outcome_sums[i] / bin_counts[i]
        result.append(
            {
                "bin_lower": round(i * bin_width, 10),
                "bin_upper": round((i + 1) * bin_width, 10),
                "count": bin_counts[i],
                "avg_predicted": avg_pred,
                "avg_actual": avg_actual,
                "gap": avg_pred - avg_actual,
            }
        )
    return result


def expected_calibration_error(
    probs: list[float],
    outcomes: list[int],
    n_bins: int = 10,
) -> float:
    """Expected Calibration Error (ECE).

    Weighted average of ``|accuracy - confidence|`` across equal-width
    bins. Lower is better; 0.0 means perfectly calibrated.

    Args:
        probs: Predicted probabilities, each in [0, 1].
        outcomes: Binary outcomes (0 or 1), same length as *probs*.
        n_bins: Number of equal-width bins. Defaults to 10.

    Returns:
        ECE value (lower is better).

    Raises:
        InvalidProbabilityError: If any probability is outside [0, 1].
        ValueError: If lists differ in length or are empty,
            or *n_bins* < 1.

    Examples:
        >>> round(expected_calibration_error([0.9, 0.1], [1, 0], n_bins=2), 1)
        0.1
    """
    buckets = calibration_buckets(probs, outcomes, n_bins)
    n = len(probs)
    ece = 0.0
    for b in buckets:
        weight = b["count"] / n
        ece += weight * abs(b["avg_actual"] - b["avg_predicted"])
    return ece


# ---------------------------------------------------------------------------
# Closing Line Value
# ---------------------------------------------------------------------------


def clv(opening_prob: float, closing_prob: float) -> float:
    """Closing Line Value from implied probabilities.

    Measures how much the line moved in your favor between open and
    close. Positive means you beat the closing line.

    Args:
        opening_prob: Implied probability at time of bet, in [0, 1].
        closing_prob: Implied probability at market close, in [0, 1].

    Returns:
        CLV as ``closing_prob - opening_prob``. Positive = good.

    Raises:
        InvalidProbabilityError: If either probability is outside [0, 1].

    Examples:
        >>> round(clv(0.50, 0.55), 2)
        0.05
        >>> round(clv(0.55, 0.50), 2)
        -0.05
    """
    if opening_prob < 0.0 or opening_prob > 1.0:
        raise InvalidProbabilityError(
            f"opening_prob must be between 0 and 1, got {opening_prob}"
        )
    if closing_prob < 0.0 or closing_prob > 1.0:
        raise InvalidProbabilityError(
            f"closing_prob must be between 0 and 1, got {closing_prob}"
        )
    return closing_prob - opening_prob


def clv_from_odds(opening_odds: int, closing_odds: int) -> float:
    """Closing Line Value from American odds.

    Converts both lines to implied probabilities, then computes CLV.

    Args:
        opening_odds: American odds at time of bet (e.g. -110, +150).
        closing_odds: American odds at market close.

    Returns:
        CLV as ``closing_implied - opening_implied``. Positive = good.

    Raises:
        InvalidOddsError: If either odds value is 0.

    Examples:
        >>> round(clv_from_odds(-110, -130), 4)
        0.0414
    """
    opening_dec = american_to_decimal(opening_odds)
    closing_dec = american_to_decimal(closing_odds)
    opening_prob = decimal_to_implied_prob(opening_dec)
    closing_prob = decimal_to_implied_prob(closing_dec)
    return closing_prob - opening_prob


# ---------------------------------------------------------------------------
# Edge-bucket analysis
# ---------------------------------------------------------------------------


def edge_bucket_analysis(
    probs: list[float],
    outcomes: list[int],
    edges: list[float],
    n_bins: int = 5,
) -> list[dict]:
    """Group predictions by predicted edge and report performance.

    Useful for answering "do my higher-edge bets actually win more?"

    Args:
        probs: Predicted probabilities, each in [0, 1].
        outcomes: Binary outcomes (0 or 1), same length as *probs*.
        edges: Predicted edge for each bet (e.g. model_prob - fair_prob).
            Same length as *probs*.
        n_bins: Number of equal-width edge bins. Defaults to 5.

    Returns:
        List of dicts (one per non-empty bin) with keys:

        - ``bin_lower``: Lower edge bound (inclusive).
        - ``bin_upper``: Upper edge bound (exclusive, except last).
        - ``count``: Number of bets in the bin.
        - ``avg_edge``: Mean predicted edge in the bin.
        - ``win_rate``: Observed win rate in the bin.
        - ``expected_win_rate``: Mean predicted probability in the bin.

    Raises:
        InvalidProbabilityError: If any probability is outside [0, 1].
        ValueError: If list lengths differ, lists are empty,
            or *n_bins* < 1.

    Examples:
        >>> results = edge_bucket_analysis(
        ...     [0.55, 0.60, 0.70],
        ...     [1, 0, 1],
        ...     [0.05, 0.10, 0.20],
        ...     n_bins=2,
        ... )
        >>> len(results) >= 1
        True
    """
    _validate_nonempty(probs, "probs")
    _validate_matched_lengths(probs, outcomes)
    _validate_matched_lengths(probs, edges, "probs", "edges")
    _validate_prob_list(probs)
    _validate_outcome_list(outcomes)
    if n_bins < 1:
        raise ValueError(f"n_bins must be >= 1, got {n_bins}")

    # Determine edge range
    min_edge = min(edges)
    max_edge = max(edges)

    # Handle degenerate case: all edges identical
    if max_edge == min_edge:
        total_wins = sum(outcomes)
        n = len(probs)
        return [
            {
                "bin_lower": min_edge,
                "bin_upper": max_edge,
                "count": n,
                "avg_edge": min_edge,
                "win_rate": total_wins / n,
                "expected_win_rate": sum(probs) / n,
            }
        ]

    bin_width = (max_edge - min_edge) / n_bins

    # Accumulators
    bin_edge_sums: list[float] = [0.0] * n_bins
    bin_prob_sums: list[float] = [0.0] * n_bins
    bin_outcome_sums: list[float] = [0.0] * n_bins
    bin_counts: list[int] = [0] * n_bins

    for p, y, e in zip(probs, outcomes, edges, strict=False):
        idx = int((e - min_edge) / bin_width)
        if idx >= n_bins:
            idx = n_bins - 1
        bin_edge_sums[idx] += e
        bin_prob_sums[idx] += p
        bin_outcome_sums[idx] += y
        bin_counts[idx] += 1

    result: list[dict] = []
    for i in range(n_bins):
        if bin_counts[i] == 0:
            continue
        count = bin_counts[i]
        result.append(
            {
                "bin_lower": round(min_edge + i * bin_width, 10),
                "bin_upper": round(min_edge + (i + 1) * bin_width, 10),
                "count": count,
                "avg_edge": bin_edge_sums[i] / count,
                "win_rate": bin_outcome_sums[i] / count,
                "expected_win_rate": bin_prob_sums[i] / count,
            }
        )
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    "brier_score",
    "log_loss",
    "expected_calibration_error",
    "calibration_buckets",
    "clv",
    "clv_from_odds",
    "edge_bucket_analysis",
]
