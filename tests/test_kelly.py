"""Tests for pari-mutuel Kelly criterion."""

import pytest

from betting_math_kit.exceptions import (
    InvalidBankrollError,
    InvalidOddsError,
    InvalidProbabilityError,
)
from betting_math_kit.kelly import (
    KellyBet,
    compute_kelly_bet,
    expected_roi,
    full_kelly_fraction,
    pool_size_limit,
    size_race_bets,
)


# ===================================================================
# full_kelly_fraction
# ===================================================================


class TestFullKellyFraction:
    def test_positive_edge(self):
        fk = full_kelly_fraction(0.30, 5.0, takeout=0.0)
        assert fk > 0

    def test_no_edge(self):
        fk = full_kelly_fraction(0.20, 5.0, takeout=0.0)
        assert fk == 0.0

    def test_takeout_reduces_kelly(self):
        fk_no = full_kelly_fraction(0.30, 5.0, takeout=0.0)
        fk_with = full_kelly_fraction(0.30, 5.0, takeout=0.16)
        assert fk_with < fk_no

    def test_prob_zero(self):
        assert full_kelly_fraction(0.0, 5.0) == 0.0

    def test_prob_one(self):
        assert full_kelly_fraction(1.0, 5.0) == 0.0

    def test_never_negative(self):
        assert full_kelly_fraction(0.01, 2.0) == 0.0

    def test_monotone_with_prob(self):
        """Higher prob => higher Kelly (for same odds)."""
        f1 = full_kelly_fraction(0.25, 5.0, takeout=0.0)
        f2 = full_kelly_fraction(0.30, 5.0, takeout=0.0)
        f3 = full_kelly_fraction(0.35, 5.0, takeout=0.0)
        assert f1 <= f2 <= f3

    def test_monotone_with_odds(self):
        """Higher odds => higher Kelly (for same prob with edge)."""
        f1 = full_kelly_fraction(0.30, 4.0, takeout=0.0)
        f2 = full_kelly_fraction(0.30, 5.0, takeout=0.0)
        f3 = full_kelly_fraction(0.30, 6.0, takeout=0.0)
        assert f1 <= f2 <= f3

    # Validation
    def test_invalid_prob_negative(self):
        with pytest.raises(InvalidProbabilityError):
            full_kelly_fraction(-0.1, 5.0)

    def test_invalid_prob_over_one(self):
        with pytest.raises(InvalidProbabilityError):
            full_kelly_fraction(1.5, 5.0)

    def test_invalid_odds(self):
        with pytest.raises(InvalidOddsError):
            full_kelly_fraction(0.5, 1.0)


# ===================================================================
# pool_size_limit
# ===================================================================


class TestPoolSizeLimit:
    def test_basic(self):
        assert pool_size_limit(100_000, 20.0, 0.05) == pytest.approx(250.0)

    def test_small_pool(self):
        assert pool_size_limit(1000, 10.0, 0.05) == pytest.approx(5.0)

    def test_invalid_inputs(self):
        assert pool_size_limit(0, 5.0) == 0.0
        assert pool_size_limit(100_000, 1.0) == 0.0
        assert pool_size_limit(100_000, 5.0, 0.0) == 0.0


# ===================================================================
# expected_roi
# ===================================================================


class TestExpectedROI:
    def test_positive_roi(self):
        roi = expected_roi(0.40, 4.0, takeout=0.0)
        assert roi > 0

    def test_negative_roi(self):
        roi = expected_roi(0.10, 4.0, takeout=0.16)
        assert roi < 0

    def test_takeout_reduces_roi(self):
        roi_no = expected_roi(0.35, 4.0, takeout=0.0)
        roi_with = expected_roi(0.35, 4.0, takeout=0.16)
        assert roi_with < roi_no


# ===================================================================
# compute_kelly_bet
# ===================================================================


class TestComputeKellyBet:
    def test_no_edge(self):
        kb = compute_kelly_bet(1, 0.10, 5.0, 1000.0)
        assert kb.bet_size == 0.0
        assert "no edge" in kb.reason

    def test_positive_edge(self):
        kb = compute_kelly_bet(1, 0.40, 5.0, 10000.0, takeout=0.0)
        assert kb.bet_size > 0
        assert kb.edge > 0

    def test_pool_limiting(self):
        kb = compute_kelly_bet(
            1, 0.50, 3.0, 100000.0,
            fraction=1.0, takeout=0.0,
            pool_size=1000, impact_limit=0.05,
        )
        assert kb.pool_limited is True

    def test_bankroll_cap(self):
        kb = compute_kelly_bet(
            1, 0.90, 2.0, 1000.0,
            fraction=1.0, takeout=0.0, max_fraction=0.05,
        )
        assert kb.capped is True
        assert kb.bet_size <= 1000 * 0.05 + 1

    def test_below_minimum(self):
        kb = compute_kelly_bet(
            1, 0.30, 5.0, 10.0,
            fraction=0.01, takeout=0.16, min_bet=2.0,
        )
        assert kb.bet_size == 0.0
        assert "below minimum" in kb.reason

    def test_frozen_dataclass(self):
        kb = compute_kelly_bet(1, 0.40, 5.0, 10000.0, takeout=0.0)
        with pytest.raises(AttributeError):
            kb.bet_size = 999

    def test_bet_never_exceeds_bankroll_cap(self):
        """Invariant: bet_size <= bankroll * max_fraction (+ rounding)."""
        for prob in [0.3, 0.5, 0.7, 0.9]:
            for odds in [2.0, 5.0, 10.0, 20.0]:
                kb = compute_kelly_bet(
                    1, prob, odds, 10000.0,
                    fraction=0.5, takeout=0.0, max_fraction=0.10,
                )
                if kb.bet_size > 0:
                    assert kb.bet_size <= 10000.0 * 0.10 + 1

    # Validation
    def test_invalid_prob(self):
        with pytest.raises(InvalidProbabilityError):
            compute_kelly_bet(1, 1.5, 5.0, 1000.0)

    def test_invalid_odds(self):
        with pytest.raises(InvalidOddsError):
            compute_kelly_bet(1, 0.5, 0.5, 1000.0)

    def test_invalid_bankroll(self):
        with pytest.raises(InvalidBankrollError):
            compute_kelly_bet(1, 0.5, 5.0, 0.0)

    def test_negative_bankroll(self):
        with pytest.raises(InvalidBankrollError):
            compute_kelly_bet(1, 0.5, 5.0, -100.0)


# ===================================================================
# size_race_bets
# ===================================================================


class TestSizeRaceBets:
    def test_empty_input(self):
        assert size_race_bets([], 1000.0) == []

    def test_filters_no_edge(self):
        bets = [
            {"selection_id": 1, "prob": 0.05, "odds_decimal": 5.0},
            {"selection_id": 2, "prob": 0.05, "odds_decimal": 5.0},
        ]
        assert len(size_race_bets(bets, 1000.0)) == 0

    def test_sorts_descending(self):
        bets = [
            {"selection_id": 1, "prob": 0.40, "odds_decimal": 5.0},
            {"selection_id": 2, "prob": 0.50, "odds_decimal": 3.0},
        ]
        result = size_race_bets(bets, 10000.0, takeout=0.0)
        if len(result) >= 2:
            assert result[0].bet_size >= result[1].bet_size

    def test_race_exposure_cap(self):
        bets = [
            {"selection_id": i, "prob": 0.60, "odds_decimal": 3.0}
            for i in range(5)
        ]
        result = size_race_bets(
            bets, 10000.0, fraction=0.5, takeout=0.0,
            max_race_exposure=0.10,
        )
        total = sum(kb.bet_size for kb in result)
        assert total <= 10000 * 0.10 + len(result)

    def test_with_pool_size(self):
        bets = [
            {
                "selection_id": 1,
                "prob": 0.50,
                "odds_decimal": 3.0,
                "pool_size": 500,
            },
        ]
        result = size_race_bets(bets, 100000.0, takeout=0.0)
        if result:
            assert result[0].pool_limited is True

    def test_invalid_bankroll(self):
        with pytest.raises(InvalidBankrollError):
            size_race_bets([], 0.0)

    def test_negative_bankroll(self):
        with pytest.raises(InvalidBankrollError):
            size_race_bets([], -100.0)
