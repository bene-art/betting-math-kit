"""Tests for de-vig algorithms."""

import pytest

from betting_math_kit.devig import (
    devig,
    devig_additive,
    devig_multi,
    devig_multiplicative,
    devig_power,
    devig_shin,
    get_vig,
)
from betting_math_kit.exceptions import InvalidOddsError, UnknownMethodError
from betting_math_kit.types import DevigMethod, DevigResult, MultiOutcomeDevigResult

# ===================================================================
# Result type checks
# ===================================================================


class TestResultTypes:
    def test_returns_devig_result(self):
        r = devig(-110, -110)
        assert isinstance(r, DevigResult)

    def test_result_has_method(self):
        r = devig(-110, -110, DevigMethod.POWER)
        assert r.method is DevigMethod.POWER

    def test_result_has_vig(self):
        r = devig(-110, -110)
        assert r.vig == pytest.approx(0.048, rel=0.01)


# ===================================================================
# Multiplicative
# ===================================================================


class TestDevigMultiplicative:
    def test_symmetric_line(self):
        r = devig_multiplicative(-110, -110)
        assert r.fair_home == pytest.approx(0.5, abs=0.001)
        assert r.fair_away == pytest.approx(0.5, abs=0.001)

    def test_sums_to_one(self):
        r = devig_multiplicative(-150, 130)
        assert r.fair_home + r.fair_away == pytest.approx(1.0, abs=1e-10)

    def test_favorite_higher_prob(self):
        r = devig_multiplicative(-200, 170)
        assert r.fair_home > r.fair_away

    def test_heavy_favorite(self):
        r = devig_multiplicative(-500, 400)
        assert r.fair_home > 0.8
        assert r.fair_away < 0.2


# ===================================================================
# Power
# ===================================================================


class TestDevigPower:
    def test_symmetric_line(self):
        r = devig_power(-110, -110)
        assert r.fair_home == pytest.approx(0.5, abs=0.001)

    def test_sums_to_one(self):
        r = devig_power(-300, 250)
        assert r.fair_home + r.fair_away == pytest.approx(1.0, abs=1e-6)

    def test_close_to_multiplicative_for_even(self):
        m = devig_multiplicative(-110, -110)
        p = devig_power(-110, -110)
        assert m.fair_home == pytest.approx(p.fair_home, abs=0.01)

    def test_diverges_from_multiplicative_on_skewed(self):
        """Power and multiplicative diverge on heavily skewed lines."""
        m = devig_multiplicative(-500, 400)
        p = devig_power(-500, 400)
        # Both valid, both sum to 1, but they should differ
        assert m.fair_home != pytest.approx(p.fair_home, abs=0.01)


# ===================================================================
# Additive
# ===================================================================


class TestDevigAdditive:
    def test_symmetric_line(self):
        r = devig_additive(-110, -110)
        assert r.fair_home == pytest.approx(0.5, abs=0.001)

    def test_sums_to_one(self):
        r = devig_additive(-150, 130)
        assert r.fair_home + r.fair_away == pytest.approx(1.0, abs=1e-10)


# ===================================================================
# Shin
# ===================================================================


class TestDevigShin:
    def test_symmetric_line(self):
        r = devig_shin(-110, -110)
        assert r.fair_home == pytest.approx(0.5, abs=0.01)

    def test_sums_to_one(self):
        r = devig_shin(-200, 170)
        assert r.fair_home + r.fair_away == pytest.approx(1.0, abs=1e-6)

    def test_extreme_odds(self):
        r = devig_shin(-10000, 5000)
        assert 0 < r.fair_home < 1
        assert 0 < r.fair_away < 1
        assert r.fair_home + r.fair_away == pytest.approx(1.0, abs=1e-6)


# ===================================================================
# Dispatcher
# ===================================================================


class TestDevigDispatch:
    def test_default_is_multiplicative(self):
        r1 = devig(-110, -110)
        r2 = devig_multiplicative(-110, -110)
        assert r1.fair_home == r2.fair_home

    def test_power_dispatch(self):
        r1 = devig(-150, 130, method=DevigMethod.POWER)
        r2 = devig_power(-150, 130)
        assert r1.fair_home == pytest.approx(r2.fair_home)

    def test_string_method(self):
        r = devig(-110, -110, method="power")
        assert r.method is DevigMethod.POWER

    def test_unknown_method_raises(self):
        with pytest.raises(UnknownMethodError):
            devig(-110, -110, method="bogus")

    def test_enum_method(self):
        r = devig(-110, -110, method=DevigMethod.SHIN)
        assert r.method is DevigMethod.SHIN


# ===================================================================
# Vig
# ===================================================================


class TestGetVig:
    def test_standard_juice(self):
        assert get_vig(-110, -110) == pytest.approx(0.0476, rel=0.01)

    def test_reduced_juice(self):
        assert get_vig(-105, -105) < get_vig(-110, -110)

    def test_no_vig(self):
        assert get_vig(100, 100) == pytest.approx(0.0, abs=1e-10)

    def test_high_vig(self):
        assert get_vig(-120, -120) > get_vig(-110, -110)

    def test_zero_odds_raises(self):
        with pytest.raises(InvalidOddsError):
            get_vig(0, -110)


# ===================================================================
# Validation
# ===================================================================


class TestValidation:
    def test_zero_home_odds_raises(self):
        with pytest.raises(InvalidOddsError):
            devig(0, -110)

    def test_zero_away_odds_raises(self):
        with pytest.raises(InvalidOddsError):
            devig(-110, 0)

    def test_both_zero_raises(self):
        with pytest.raises(InvalidOddsError):
            devig(0, 0)


# ===================================================================
# n-outcome de-vig
# ===================================================================


class TestDevigMulti:
    def test_three_outcomes(self):
        r = devig_multi([200, 300, 150])
        assert isinstance(r, MultiOutcomeDevigResult)
        assert r.n_outcomes == 3
        assert sum(r.fair_probs) == pytest.approx(1.0, abs=1e-6)

    def test_two_outcomes_matches_devig(self):
        r2 = devig(-110, -110)
        rm = devig_multi([-110, -110])
        assert rm.fair_probs[0] == pytest.approx(r2.fair_home, abs=1e-6)
        assert rm.fair_probs[1] == pytest.approx(r2.fair_away, abs=1e-6)

    def test_six_outcomes(self):
        odds = [-200, 300, 500, 800, 1000, 1500]
        r = devig_multi(odds)
        assert r.n_outcomes == 6
        assert sum(r.fair_probs) == pytest.approx(1.0, abs=1e-6)
        # favorite should have highest probability
        assert r.fair_probs[0] == max(r.fair_probs)

    def test_single_outcome_raises(self):
        with pytest.raises(ValueError):
            devig_multi([-110])

    def test_zero_odds_raises(self):
        with pytest.raises(InvalidOddsError):
            devig_multi([-110, 0, 200])

    def test_additive_raises(self):
        with pytest.raises(UnknownMethodError):
            devig_multi([-110, 110], method=DevigMethod.ADDITIVE)

    def test_power_method(self):
        r = devig_multi([-110, -110, 300], method=DevigMethod.POWER)
        assert sum(r.fair_probs) == pytest.approx(1.0, abs=1e-6)

    def test_shin_method(self):
        r = devig_multi([-110, -110, 300], method=DevigMethod.SHIN)
        assert sum(r.fair_probs) == pytest.approx(1.0, abs=1e-6)

    def test_ordering_preserved(self):
        odds = [150, -200, 300]
        r = devig_multi(odds)
        # -200 is the favorite (index 1), should have highest prob
        assert r.fair_probs[1] == max(r.fair_probs)

    def test_vig_positive(self):
        r = devig_multi([-110, -110, 300])
        assert r.vig > 0


# ===================================================================
# Invariants (all methods)
# ===================================================================


class TestInvariants:
    @pytest.mark.parametrize("odds", [-110, -105, -115, -120])
    def test_symmetric_all_methods_equal(self, odds):
        """All methods should agree on symmetric odds."""
        for method in DevigMethod:
            r = devig(odds, odds, method=method)
            assert r.fair_home == pytest.approx(0.5, abs=0.02), (
                f"{method.value} failed for {odds}/{odds}: got {r.fair_home:.4f}"
            )

    @pytest.mark.parametrize(
        "home,away",
        [(-150, 130), (-200, 170), (-300, 250), (-500, 400)],
    )
    def test_all_methods_sum_to_one(self, home, away):
        for method in DevigMethod:
            r = devig(home, away, method=method)
            assert r.fair_home + r.fair_away == pytest.approx(1.0, abs=1e-6), (
                f"{method.value} sums to {r.fair_home + r.fair_away}"
            )

    @pytest.mark.parametrize(
        "home,away",
        [(-150, 130), (-200, 170), (-300, 250)],
    )
    def test_probabilities_bounded(self, home, away):
        for method in DevigMethod:
            r = devig(home, away, method=method)
            assert 0 < r.fair_home < 1
            assert 0 < r.fair_away < 1

    @pytest.mark.parametrize(
        "home,away",
        [(-150, 130), (-200, 170), (-500, 400)],
    )
    def test_favorite_always_has_higher_prob(self, home, away):
        """The favorite (negative odds) should always have higher fair prob."""
        for method in DevigMethod:
            r = devig(home, away, method=method)
            assert r.fair_home > r.fair_away, (
                f"{method.value}: fav {r.fair_home:.4f} <= dog {r.fair_away:.4f}"
            )

    def test_vig_monotone_with_juice(self):
        """More juice => higher vig."""
        v1 = get_vig(-105, -105)
        v2 = get_vig(-110, -110)
        v3 = get_vig(-115, -115)
        v4 = get_vig(-120, -120)
        assert v1 < v2 < v3 < v4
