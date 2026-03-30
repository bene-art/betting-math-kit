"""Domain types for betting-math-kit."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Side(Enum):
    """Which side of a two-way market."""
    HOME = "home"
    AWAY = "away"


class DevigMethod(Enum):
    """De-vig algorithm."""
    MULTIPLICATIVE = "multiplicative"
    POWER = "power"
    ADDITIVE = "additive"
    SHIN = "shin"


@dataclass(frozen=True)
class DevigResult:
    """Result of de-vigging a two-sided market.

    Attributes:
        fair_home: Fair probability for the home/first side.
        fair_away: Fair probability for the away/second side.
        method: Which de-vig algorithm was used.
        vig: Original bookmaker margin (overround - 1).
    """
    fair_home: float
    fair_away: float
    method: DevigMethod
    vig: float

    def __post_init__(self) -> None:
        # Sanity: probabilities should sum to ~1
        total = self.fair_home + self.fair_away
        if abs(total - 1.0) > 1e-6:
            raise ValueError(
                f"Fair probabilities sum to {total:.6f}, expected ~1.0"
            )


@dataclass(frozen=True)
class MultiOutcomeDevigResult:
    """Result of de-vigging a multi-outcome market.

    Attributes:
        fair_probs: Fair probability for each outcome (same order as input).
        method: Which de-vig algorithm was used.
        vig: Original bookmaker margin.
        n_outcomes: Number of outcomes.
    """
    fair_probs: tuple[float, ...]
    method: DevigMethod
    vig: float
    n_outcomes: int

    def __post_init__(self) -> None:
        total = sum(self.fair_probs)
        if abs(total - 1.0) > 1e-6:
            raise ValueError(
                f"Fair probabilities sum to {total:.6f}, expected ~1.0"
            )


@dataclass(frozen=True)
class EdgeResult:
    """Result of a calibrated edge calculation.

    Attributes:
        model_prob: Your model's probability for the pick.
        implied_prob: Raw implied probability (includes vig).
        fair_prob: De-vigged fair probability.
        raw_edge: Edge vs implied probability (overstated due to vig).
        true_edge: Edge vs fair probability (correct measure).
        pick: Which side was evaluated.
        method: De-vig method used.
    """
    model_prob: float
    implied_prob: float
    fair_prob: float
    raw_edge: float
    true_edge: float
    pick: Side
    method: DevigMethod
