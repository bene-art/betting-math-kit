"""Tests for Monte Carlo bankroll simulation."""

import pytest

from betting_math_kit.exceptions import InvalidBankrollError, InvalidOddsError
from betting_math_kit.simulation import (
    SimulationResult,
    optimal_fraction_search,
    risk_of_ruin,
    simulate_bankroll,
)

# ===================================================================
# simulate_bankroll
# ===================================================================


class TestSimulateBankroll:
    def test_returns_simulation_result(self):
        r = simulate_bankroll(0.05, 2.0, 0.25, n_bets=100, n_trials=100, seed=42)
        assert isinstance(r, SimulationResult)

    def test_deterministic_with_seed(self):
        r1 = simulate_bankroll(0.05, 2.0, 0.25, n_bets=100, n_trials=100, seed=42)
        r2 = simulate_bankroll(0.05, 2.0, 0.25, n_bets=100, n_trials=100, seed=42)
        assert r1.median_final == r2.median_final
        assert r1.ruin_rate == r2.ruin_rate

    def test_positive_edge_grows_bankroll(self):
        r = simulate_bankroll(0.10, 2.0, 0.25, n_bets=500, n_trials=500, seed=1)
        assert r.median_final > 1000.0  # started at 1000

    def test_ruin_rate_bounded(self):
        r = simulate_bankroll(0.05, 2.0, 0.25, n_bets=100, n_trials=100, seed=42)
        assert 0.0 <= r.ruin_rate <= 1.0

    def test_percentiles_ordered(self):
        r = simulate_bankroll(0.05, 2.0, 0.25, n_bets=100, n_trials=500, seed=42)
        assert r.p5_final <= r.median_final <= r.p95_final

    def test_frozen_dataclass(self):
        r = simulate_bankroll(0.05, 2.0, 0.25, n_bets=10, n_trials=10, seed=42)
        with pytest.raises(AttributeError):
            r.ruin_rate = 0.5

    # Validation
    def test_zero_edge_raises(self):
        with pytest.raises(ValueError):
            simulate_bankroll(0.0, 2.0, 0.25)

    def test_negative_edge_raises(self):
        with pytest.raises(ValueError):
            simulate_bankroll(-0.05, 2.0, 0.25)

    def test_invalid_odds_raises(self):
        with pytest.raises(InvalidOddsError):
            simulate_bankroll(0.05, 1.0, 0.25)

    def test_zero_fraction_raises(self):
        with pytest.raises(ValueError):
            simulate_bankroll(0.05, 2.0, 0.0)

    def test_zero_bankroll_raises(self):
        with pytest.raises(InvalidBankrollError):
            simulate_bankroll(0.05, 2.0, 0.25, bankroll=0.0)

    def test_zero_n_bets_raises(self):
        with pytest.raises(ValueError):
            simulate_bankroll(0.05, 2.0, 0.25, n_bets=0)

    def test_zero_n_trials_raises(self):
        with pytest.raises(ValueError):
            simulate_bankroll(0.05, 2.0, 0.25, n_trials=0)


# ===================================================================
# risk_of_ruin
# ===================================================================


class TestRiskOfRuin:
    def test_returns_float(self):
        r = risk_of_ruin(0.05, 2.0, 0.25, n_bets=100, n_trials=100, seed=42)
        assert isinstance(r, float)
        assert 0.0 <= r <= 1.0

    def test_high_fraction_higher_ruin(self):
        low = risk_of_ruin(0.05, 2.0, 0.10, n_bets=200, n_trials=500, seed=42)
        high = risk_of_ruin(0.05, 2.0, 0.90, n_bets=200, n_trials=500, seed=42)
        assert high >= low


# ===================================================================
# optimal_fraction_search
# ===================================================================


class TestOptimalFractionSearch:
    def test_returns_dict(self):
        results = optimal_fraction_search(
            0.05, 2.0, fractions=[0.1, 0.25], n_bets=50, n_trials=50, seed=42
        )
        assert isinstance(results, dict)
        assert 0.1 in results
        assert 0.25 in results

    def test_all_values_are_simulation_results(self):
        results = optimal_fraction_search(
            0.05, 2.0, fractions=[0.1, 0.25], n_bets=50, n_trials=50, seed=42
        )
        for v in results.values():
            assert isinstance(v, SimulationResult)

    def test_zero_edge_raises(self):
        with pytest.raises(ValueError):
            optimal_fraction_search(0.0, 2.0)

    def test_invalid_odds_raises(self):
        with pytest.raises(InvalidOddsError):
            optimal_fraction_search(0.05, 1.0)

    def test_default_fractions(self):
        results = optimal_fraction_search(0.05, 2.0, n_bets=10, n_trials=10, seed=42)
        assert len(results) == 8  # default list has 8 entries
