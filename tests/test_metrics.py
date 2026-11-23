"""Tests for calibration and evaluation metrics."""

import pytest

from betting_math_kit.exceptions import InvalidOddsError, InvalidProbabilityError
from betting_math_kit.metrics import (
    brier_score,
    calibration_buckets,
    clv,
    clv_from_odds,
    edge_bucket_analysis,
    expected_calibration_error,
    log_loss,
)

# ===================================================================
# Brier score
# ===================================================================


class TestBrierScore:
    def test_perfect_predictions(self):
        assert brier_score([1.0, 0.0], [1, 0]) == pytest.approx(0.0)

    def test_worst_predictions(self):
        assert brier_score([0.0, 1.0], [1, 0]) == pytest.approx(1.0)

    def test_coin_flip(self):
        assert brier_score([0.5, 0.5], [1, 0]) == pytest.approx(0.25)

    def test_good_model(self):
        assert brier_score([0.9, 0.1], [1, 0]) == pytest.approx(0.01)

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            brier_score([], [])

    def test_length_mismatch_raises(self):
        with pytest.raises(ValueError):
            brier_score([0.5], [1, 0])

    def test_invalid_prob_raises(self):
        with pytest.raises(InvalidProbabilityError):
            brier_score([1.5], [1])

    def test_invalid_outcome_raises(self):
        with pytest.raises(ValueError):
            brier_score([0.5], [2])


# ===================================================================
# Log loss
# ===================================================================


class TestLogLoss:
    def test_good_model(self):
        ll = log_loss([0.9, 0.1], [1, 0])
        assert ll == pytest.approx(0.1054, rel=0.01)

    def test_perfect_predictions(self):
        ll = log_loss([1.0, 0.0], [1, 0])
        assert ll < 0.01  # clamped, not exactly 0

    def test_bad_predictions_high(self):
        ll = log_loss([0.1, 0.9], [1, 0])
        assert ll > 1.0

    def test_coin_flip(self):
        ll = log_loss([0.5, 0.5], [1, 0])
        assert ll == pytest.approx(0.6931, rel=0.01)

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            log_loss([], [])


# ===================================================================
# Calibration
# ===================================================================


class TestCalibrationBuckets:
    def test_two_bins(self):
        buckets = calibration_buckets([0.1, 0.9], [0, 1], n_bins=2)
        assert len(buckets) == 2

    def test_keys_present(self):
        buckets = calibration_buckets([0.5], [1], n_bins=1)
        assert "avg_predicted" in buckets[0]
        assert "avg_actual" in buckets[0]
        assert "gap" in buckets[0]
        assert "count" in buckets[0]

    def test_perfect_calibration(self):
        # 10 predictions at 0.5, half win
        probs = [0.5] * 10
        outcomes = [1, 0, 1, 0, 1, 0, 1, 0, 1, 0]
        buckets = calibration_buckets(probs, outcomes, n_bins=1)
        assert buckets[0]["gap"] == pytest.approx(0.0)

    def test_invalid_n_bins_raises(self):
        with pytest.raises(ValueError):
            calibration_buckets([0.5], [1], n_bins=0)


class TestExpectedCalibrationError:
    def test_perfect_calibration(self):
        probs = [0.5] * 10
        outcomes = [1, 0, 1, 0, 1, 0, 1, 0, 1, 0]
        ece = expected_calibration_error(probs, outcomes, n_bins=1)
        assert ece == pytest.approx(0.0)

    def test_overconfident(self):
        probs = [0.9] * 10
        outcomes = [1, 0, 1, 0, 1, 0, 1, 0, 1, 0]
        ece = expected_calibration_error(probs, outcomes, n_bins=1)
        assert ece > 0.3


# ===================================================================
# CLV
# ===================================================================


class TestCLV:
    def test_positive_clv(self):
        assert clv(0.50, 0.55) == pytest.approx(0.05)

    def test_negative_clv(self):
        assert clv(0.55, 0.50) == pytest.approx(-0.05)

    def test_zero_clv(self):
        assert clv(0.50, 0.50) == pytest.approx(0.0)

    def test_invalid_opening_raises(self):
        with pytest.raises(InvalidProbabilityError):
            clv(-0.1, 0.5)

    def test_invalid_closing_raises(self):
        with pytest.raises(InvalidProbabilityError):
            clv(0.5, 1.5)


class TestCLVFromOdds:
    def test_line_moves_toward_you(self):
        # -110 -> -130 means the line shortened (more likely)
        val = clv_from_odds(-110, -130)
        assert val > 0

    def test_line_moves_away(self):
        val = clv_from_odds(-130, -110)
        assert val < 0

    def test_no_movement(self):
        assert clv_from_odds(-110, -110) == pytest.approx(0.0)

    def test_zero_odds_raises(self):
        with pytest.raises(InvalidOddsError):
            clv_from_odds(0, -110)


# ===================================================================
# Edge bucket analysis
# ===================================================================


class TestEdgeBucketAnalysis:
    def test_basic(self):
        results = edge_bucket_analysis(
            [0.55, 0.60, 0.70],
            [1, 0, 1],
            [0.05, 0.10, 0.20],
            n_bins=2,
        )
        assert len(results) >= 1
        assert all("avg_edge" in r for r in results)
        assert all("win_rate" in r for r in results)

    def test_all_same_edge(self):
        results = edge_bucket_analysis(
            [0.6, 0.6, 0.6],
            [1, 1, 0],
            [0.05, 0.05, 0.05],
        )
        assert len(results) == 1
        assert results[0]["win_rate"] == pytest.approx(2.0 / 3.0)

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            edge_bucket_analysis([], [], [])

    def test_length_mismatch_raises(self):
        with pytest.raises(ValueError):
            edge_bucket_analysis([0.5], [1], [0.05, 0.10])
