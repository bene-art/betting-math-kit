"""Tests for odds conversion, edge calculation, and fixed-odds Kelly."""

import pytest

from betting_math_kit.exceptions import InvalidOddsError, InvalidProbabilityError
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
from betting_math_kit.types import DevigMethod, Side


# ===================================================================
# Odds conversion
# ===================================================================


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

    def test_zero_raises(self):
        with pytest.raises(InvalidOddsError):
            american_to_decimal(0)


class TestDecimalToAmerican:
    def test_even_money(self):
        assert decimal_to_american(2.0) == 100

    def test_favorite(self):
        assert decimal_to_american(1.5) == -200

    def test_underdog(self):
        assert decimal_to_american(2.5) == 150

    def test_invalid_low(self):
        with pytest.raises(InvalidOddsError):
            decimal_to_american(1.0)

    def test_invalid_negative(self):
        with pytest.raises(InvalidOddsError):
            decimal_to_american(0.5)


class TestImpliedProb:
    def test_even_money(self):
        assert decimal_to_implied_prob(2.0) == 0.5

    def test_favorite(self):
        assert decimal_to_implied_prob(1.5) == pytest.approx(0.6667, rel=1e-3)

    def test_invalid_decimal_odds(self):
        with pytest.raises(InvalidOddsError):
            decimal_to_implied_prob(1.0)

    def test_round_trip(self):
        prob = 0.6
        decimal = implied_prob_to_decimal(prob)
        assert decimal_to_implied_prob(decimal) == pytest.approx(prob)

    def test_zero_prob_raises(self):
        with pytest.raises(InvalidProbabilityError):
            implied_prob_to_decimal(0.0)

    def test_negative_prob_raises(self):
        with pytest.raises(InvalidProbabilityError):
            implied_prob_to_decimal(-0.1)

    def test_over_one_raises(self):
        with pytest.raises(InvalidProbabilityError):
            implied_prob_to_decimal(1.1)


# ===================================================================
# Round-trip invariants
# ===================================================================


class TestRoundTrips:
    @pytest.mark.parametrize("odds", [-500, -200, -110, 100, 150, 300, 1000])
    def test_american_round_trip(self, odds):
        """american -> decimal -> american should be close (rounding ok)."""
        decimal = american_to_decimal(odds)
        back = decimal_to_american(decimal)
        assert abs(back - odds) <= 1  # rounding tolerance

    @pytest.mark.parametrize("prob", [0.1, 0.25, 0.5, 0.75, 0.9])
    def test_prob_round_trip(self, prob):
        decimal = implied_prob_to_decimal(prob)
        back = decimal_to_implied_prob(decimal)
        assert back == pytest.approx(prob)


# ===================================================================
# Edge calculation
# ===================================================================


class TestCalculateEdge:
    def test_no_edge(self):
        edge = calculate_edge(0.5, 100)
        assert edge == pytest.approx(0.0, abs=1e-6)

    def test_positive_edge(self):
        assert calculate_edge(0.60, -110) > 0

    def test_negative_edge(self):
        assert calculate_edge(0.40, -110) < 0

    def test_invalid_prob_raises(self):
        with pytest.raises(InvalidProbabilityError):
            calculate_edge(1.5, -110)

    def test_negative_prob_raises(self):
        with pytest.raises(InvalidProbabilityError):
            calculate_edge(-0.1, -110)

    def test_zero_odds_raises(self):
        with pytest.raises(InvalidOddsError):
            calculate_edge(0.5, 0)


class TestCalculateEdgeCalibrated:
    def test_symmetric_line(self):
        r = calculate_edge_calibrated(0.60, -110, -110)
        assert r.fair_prob == pytest.approx(0.5, abs=0.01)
        assert r.true_edge == pytest.approx(0.10, abs=0.01)
        assert r.raw_edge < r.true_edge

    def test_away_pick(self):
        r = calculate_edge_calibrated(0.45, -150, 130, pick=Side.AWAY)
        assert r.fair_prob < 0.5
        assert r.true_edge > 0
        assert r.pick is Side.AWAY

    def test_string_pick(self):
        r = calculate_edge_calibrated(0.60, -110, -110, pick="home")
        assert r.pick is Side.HOME

    def test_string_method(self):
        r = calculate_edge_calibrated(
            0.60, -110, -110, method="power"
        )
        assert r.method is DevigMethod.POWER

    def test_returns_edge_result(self):
        r = calculate_edge_calibrated(0.60, -110, -110)
        assert hasattr(r, "model_prob")
        assert hasattr(r, "true_edge")
        assert hasattr(r, "fair_prob")
        assert r.model_prob == 0.60

    def test_invalid_prob_raises(self):
        with pytest.raises(InvalidProbabilityError):
            calculate_edge_calibrated(1.5, -110, -110)

    def test_true_edge_gt_raw_edge_on_vigged_line(self):
        """True edge should be larger than raw edge when there is vig."""
        r = calculate_edge_calibrated(0.60, -110, -110)
        assert r.true_edge > r.raw_edge


# ===================================================================
# Kelly (fixed-odds)
# ===================================================================


class TestKellyFraction:
    def test_no_edge(self):
        assert kelly_fraction(0.50, 100) == 0.0

    def test_small_edge(self):
        frac = kelly_fraction(0.55, -110)
        assert 0 < frac < 0.25

    def test_large_edge_capped(self):
        assert kelly_fraction(0.80, 150) == 0.25

    def test_negative_edge(self):
        assert kelly_fraction(0.30, -200) == 0.0

    def test_invalid_prob_raises(self):
        with pytest.raises(InvalidProbabilityError):
            kelly_fraction(1.5, -110)

    def test_zero_odds_raises(self):
        with pytest.raises(InvalidOddsError):
            kelly_fraction(0.5, 0)

    def test_monotone_with_edge(self):
        """Higher model prob => larger Kelly fraction (for same odds)."""
        f1 = kelly_fraction(0.55, -110)
        f2 = kelly_fraction(0.60, -110)
        f3 = kelly_fraction(0.65, -110)
        assert f1 <= f2 <= f3


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

    def test_string_inputs(self):
        stake, _, _, bet = kelly_calibrated(
            0.60, -110, -110, pick="home", method="multiplicative"
        )
        assert bet is True
