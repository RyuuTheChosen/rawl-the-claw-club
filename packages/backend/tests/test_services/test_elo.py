"""Unit tests for rawl.services.elo — pure Elo math functions."""
from __future__ import annotations

import math
from unittest.mock import patch

import pytest

from rawl.services.elo import (
    calculate_expected,
    calculate_new_rating,
    get_division,
    get_k_factor,
    seasonal_reset,
)


# ── get_k_factor ────────────────────────────────────────────────

class TestGetKFactor:
    def test_calibration_phase(self):
        """Fewer than 10 matches → calibration K."""
        assert get_k_factor(1200.0, 0) == 40
        assert get_k_factor(1200.0, 9) == 40

    def test_established_phase(self):
        """10+ matches, rating <= 1800 → established K."""
        assert get_k_factor(1200.0, 10) == 20
        assert get_k_factor(1800.0, 50) == 20

    def test_elite_phase(self):
        """10+ matches, rating > 1800 → elite K."""
        assert get_k_factor(1801.0, 10) == 16
        assert get_k_factor(2200.0, 100) == 16

    def test_calibration_takes_priority(self):
        """Even with elite rating, calibration phase wins."""
        assert get_k_factor(2000.0, 5) == 40


# ── calculate_expected ──────────────────────────────────────────

class TestCalculateExpected:
    def test_equal_ratings(self):
        assert calculate_expected(1200.0, 1200.0) == pytest.approx(0.5)

    def test_higher_rated_favoured(self):
        e = calculate_expected(1400.0, 1200.0)
        assert e > 0.5
        assert e < 1.0

    def test_lower_rated_unfavoured(self):
        e = calculate_expected(1000.0, 1200.0)
        assert e < 0.5
        assert e > 0.0

    def test_400_point_gap(self):
        """400 point advantage → ~0.909 expected."""
        e = calculate_expected(1600.0, 1200.0)
        assert e == pytest.approx(1.0 / (1.0 + math.pow(10.0, -1.0)), rel=1e-6)

    def test_symmetry(self):
        """E(A vs B) + E(B vs A) = 1.0."""
        e_a = calculate_expected(1300.0, 1100.0)
        e_b = calculate_expected(1100.0, 1300.0)
        assert e_a + e_b == pytest.approx(1.0)


# ── calculate_new_rating ────────────────────────────────────────

class TestCalculateNewRating:
    def test_winner_gains(self):
        new = calculate_new_rating(1200.0, 1200.0, won=True, matches_played=0)
        assert new > 1200.0

    def test_loser_loses(self):
        new = calculate_new_rating(1200.0, 1200.0, won=False, matches_played=0)
        assert new < 1200.0

    def test_equal_ratings_calibration_win(self):
        """1200 vs 1200, K=40, win → 1200 + 40*(1 - 0.5) = 1220."""
        new = calculate_new_rating(1200.0, 1200.0, won=True, matches_played=0)
        assert new == 1220.0

    def test_equal_ratings_calibration_loss(self):
        """1200 vs 1200, K=40, loss → 1200 + 40*(0 - 0.5) = 1180."""
        new = calculate_new_rating(1200.0, 1200.0, won=False, matches_played=0)
        assert new == 1180.0

    def test_floor_enforced(self):
        """Rating cannot drop below floor (800)."""
        new = calculate_new_rating(800.0, 2000.0, won=False, matches_played=0)
        assert new >= 800.0

    def test_upset_bonus(self):
        """Lower-rated player beating higher-rated gains more."""
        gain_underdog = calculate_new_rating(1000.0, 1400.0, won=True, matches_played=0) - 1000.0
        gain_favourite = calculate_new_rating(1400.0, 1000.0, won=True, matches_played=0) - 1400.0
        assert gain_underdog > gain_favourite

    def test_rating_change_sums_near_zero(self):
        """Winner gain + loser loss ≈ 0 (when same K-factor)."""
        winner_new = calculate_new_rating(1200.0, 1200.0, won=True, matches_played=15)
        loser_new = calculate_new_rating(1200.0, 1200.0, won=False, matches_played=15)
        delta_w = winner_new - 1200.0
        delta_l = loser_new - 1200.0
        assert delta_w + delta_l == pytest.approx(0.0, abs=0.2)


# ── get_division ────────────────────────────────────────────────

class TestGetDivision:
    def test_bronze(self):
        assert get_division(0.0) == "Bronze"
        assert get_division(1199.9) == "Bronze"

    def test_silver(self):
        assert get_division(1200.0) == "Silver"
        assert get_division(1399.9) == "Silver"

    def test_gold(self):
        assert get_division(1400.0) == "Gold"
        assert get_division(1599.9) == "Gold"

    def test_diamond(self):
        assert get_division(1600.0) == "Diamond"
        assert get_division(2500.0) == "Diamond"


# ── seasonal_reset ──────────────────────────────────────────────

class TestSeasonalReset:
    def test_at_baseline(self):
        """1200 stays 1200."""
        assert seasonal_reset(1200.0) == 1200.0

    def test_above_baseline(self):
        """1600 → 1200 + 0.5*(1600-1200) = 1400."""
        assert seasonal_reset(1600.0) == 1400.0

    def test_below_baseline(self):
        """1000 → 1200 + 0.5*(1000-1200) = 1100."""
        assert seasonal_reset(1000.0) == 1100.0

    def test_floor_enforced(self):
        """Very low rating still can't go below floor."""
        assert seasonal_reset(800.0) >= 800.0

    def test_extreme_high(self):
        """2000 → 1600."""
        assert seasonal_reset(2000.0) == 1600.0

    def test_regression_towards_mean(self):
        """All ratings move toward 1200."""
        high = seasonal_reset(1800.0)
        low = seasonal_reset(900.0)
        assert abs(high - 1200.0) < abs(1800.0 - 1200.0)
        assert abs(low - 1200.0) < abs(900.0 - 1200.0)
