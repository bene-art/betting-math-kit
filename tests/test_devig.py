"""Tests for de-vig algorithms."""

import pytest

from betting_math_kit.devig import (
    DevigMethod,
    devig,
    devig_additive,
    devig_multiplicative,
    devig_power,
    devig_shin,
    get_vig,
)


class TestDevigMultiplicative:
    def test_symmetric_line(self):
        h, a = devig_multiplicative(-110, -110)
        assert h == pytest.approx(0.5, abs=0.001)
        assert a == pytest.approx(0.5, abs=0.001)

    def test_sums_to_one(self):
        h, a = devig_multiplicative(-150, 130)
        assert h + a == pytest.approx(1.0, abs=1e-10)

    def test_favorite_higher_prob(self):
        h, a = devig_multiplicative(-200, 170)
        assert h > a

    def test_heavy_favorite(self):
        h, a = devig_multiplicative(-500, 400)
        assert h > 0.8
        assert a < 0.2


class TestDevigPower:
    def test_symmetric_line(self):
        h, a = devig_power(-110, -110)
        assert h == pytest.approx(0.5, abs=0.001)
        assert a == pytest.approx(0.5, abs=0.001)

    def test_sums_to_one(self):
        h, a = devig_power(-300, 250)
        assert h + a == pytest.approx(1.0, abs=1e-6)

    def test_close_to_multiplicative_for_even_odds(self):
        m_h, m_a = devig_multiplicative(-110, -110)
        p_h, p_a = devig_power(-110, -110)
        assert m_h == pytest.approx(p_h, abs=0.01)


class TestDevigAdditive:
    def test_symmetric_line(self):
        h, a = devig_additive(-110, -110)
        assert h == pytest.approx(0.5, abs=0.001)

    def test_sums_to_one(self):
        h, a = devig_additive(-150, 130)
        assert h + a == pytest.approx(1.0, abs=1e-10)


class TestDevigShin:
    def test_symmetric_line(self):
        h, a = devig_shin(-110, -110)
        assert h == pytest.approx(0.5, abs=0.01)

    def test_sums_to_one(self):
        h, a = devig_shin(-200, 170)
        assert h + a == pytest.approx(1.0, abs=1e-6)

    def test_fallback_on_pathological_input(self):
        # Very extreme odds should still produce valid probabilities
        h, a = devig_shin(-10000, 5000)
        assert 0 < h < 1
        assert 0 < a < 1
        assert h + a == pytest.approx(1.0, abs=1e-6)


class TestDevigDispatch:
    def test_default_is_multiplicative(self):
        h1, a1 = devig(-110, -110)
        h2, a2 = devig_multiplicative(-110, -110)
        assert h1 == h2
        assert a1 == a2

    def test_power_dispatch(self):
        h1, a1 = devig(-150, 130, method=DevigMethod.POWER)
        h2, a2 = devig_power(-150, 130)
        assert h1 == pytest.approx(h2)

    def test_unknown_method_falls_back(self):
        h, a = devig(-110, -110, method="unknown_method")
        assert h == pytest.approx(0.5, abs=0.001)


class TestGetVig:
    def test_standard_juice(self):
        vig = get_vig(-110, -110)
        assert vig == pytest.approx(0.0476, rel=0.01)

    def test_reduced_juice(self):
        vig = get_vig(-105, -105)
        assert vig < get_vig(-110, -110)

    def test_no_vig(self):
        # Even money with no margin
        vig = get_vig(100, 100)
        assert vig == pytest.approx(0.0, abs=1e-10)

    def test_high_vig(self):
        vig = get_vig(-120, -120)
        assert vig > get_vig(-110, -110)


class TestAllMethodsAgree:
    """All methods should agree on symmetric odds."""

    @pytest.mark.parametrize("odds", [-110, -105, -115, -120])
    def test_symmetric_all_methods(self, odds):
        for method in [
            DevigMethod.MULTIPLICATIVE,
            DevigMethod.POWER,
            DevigMethod.ADDITIVE,
            DevigMethod.SHIN,
        ]:
            h, a = devig(odds, odds, method=method)
            assert h == pytest.approx(0.5, abs=0.02), (
                f"{method} failed for {odds}/{odds}: got {h:.4f}"
            )
