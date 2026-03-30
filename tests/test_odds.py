"""Tests for odds conversion and edge calculation."""

import pytest

from betting_math_kit.odds import (
    american_to_decimal,
    calculate_edge,
    calculate_edge_calibrated,
    decimal_to_american,
    decimal_to_implied_prob,
    implied_prob_to_decimal,
    kelly_calibrated,
    kelly_fraction,
)


# ---------------------------------------------------------------------------
# Odds conversion
# ---------------------------------------------------------------------------


class TestAmericanToDecimal:
    def test_even_money(self):
        assert american_to_decimal(100) == 2.0

    def test_favorite(self):
        assert american_to_decimal(-200) == pytest.approx(1.5)

    def test_underdog(self):
        assert american_to_decimal(150) == 2.5

    def test_heavy_favorite(self):
        assert american_to_decimal(-500) == pytest.approx(1.2)

    def test_standard_juice(self):
        assert american_to_decimal(-110) == pytest.approx(1.9091, rel=1e-3)


class TestDecimalToAmerican:
    def test_even_money(self):
        assert decimal_to_american(2.0) == 100

    def test_favorite(self):
        assert decimal_to_american(1.5) == -200

    def test_underdog(self):
        assert decimal_to_american(2.5) == 150


class TestImpliedProb:
    def test_even_money(self):
        assert decimal_to_implied_prob(2.0) == 0.5

    def test_favorite(self):
        assert decimal_to_implied_prob(1.5) == pytest.approx(0.6667, rel=1e-3)

    def test_round_trip(self):
        prob = 0.6
        decimal = implied_prob_to_decimal(prob)
        assert decimal_to_implied_prob(decimal) == pytest.approx(prob)

    def test_zero_prob_raises(self):
        with pytest.raises(ValueError):
            implied_prob_to_decimal(0.0)

    def test_negative_prob_raises(self):
        with pytest.raises(ValueError):
            implied_prob_to_decimal(-0.1)


# ---------------------------------------------------------------------------
# Edge
# ---------------------------------------------------------------------------


class TestCalculateEdge:
    def test_no_edge(self):
        # Model matches implied prob
        edge = calculate_edge(0.5, 100)
        assert edge == pytest.approx(0.0, abs=1e-6)

    def test_positive_edge(self):
        edge = calculate_edge(0.60, -110)
        assert edge > 0

    def test_negative_edge(self):
        edge = calculate_edge(0.40, -110)
        assert edge < 0


class TestCalculateEdgeCalibrated:
    def test_symmetric_line(self):
        true_edge, fair, raw = calculate_edge_calibrated(0.60, -110, -110)
        assert fair == pytest.approx(0.5, abs=0.01)
        assert true_edge == pytest.approx(0.10, abs=0.01)
        assert raw < true_edge  # raw edge is smaller (includes vig)

    def test_away_pick(self):
        true_edge, fair, _ = calculate_edge_calibrated(
            0.45, -150, 130, pick="away"
        )
        assert fair < 0.5  # away is the underdog
        assert true_edge > 0  # model says 45% vs ~41% fair


# ---------------------------------------------------------------------------
# Kelly
# ---------------------------------------------------------------------------


class TestKellyFraction:
    def test_no_edge(self):
        assert kelly_fraction(0.50, 100) == 0.0

    def test_small_edge(self):
        frac = kelly_fraction(0.55, -110)
        assert 0 < frac < 0.25

    def test_large_edge(self):
        frac = kelly_fraction(0.80, 150)
        assert frac == 0.25  # capped

    def test_negative_edge(self):
        assert kelly_fraction(0.30, -200) == 0.0


class TestKellyCalibrated:
    def test_strong_edge_bets(self):
        stake, edge, fair, should_bet = kelly_calibrated(0.60, -110, -110)
        assert should_bet is True
        assert stake > 0
        assert edge > 0.03

    def test_weak_edge_passes(self):
        stake, edge, fair, should_bet = kelly_calibrated(0.52, -110, -110)
        assert should_bet is False
        assert stake == 0.0

    def test_max_stake_cap(self):
        stake, _, _, should_bet = kelly_calibrated(
            0.90, -110, -110, max_stake=0.02
        )
        assert should_bet is True
        assert stake <= 0.02
