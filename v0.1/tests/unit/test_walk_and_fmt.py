"""Unit tests for the two smallest scoring primitives.

`_walk_minutes` (haversine → walk minutes) and `_fmt_dist` (metre → rule
label). Both live in `app.core.scoring.constants`.

The 62 m/min calibration + the 400 m / 1 km / 1.5 km / 2.5 km happy paths
are already asserted in the `if __name__ == "__main__":` selfcheck at the
bottom of `app/core/scoring/constants.py`. These tests focus on
tier-boundary cases and monotonicity properties that the selfcheck does
not cover — every case here earns its keep by exercising a code path the
selfcheck does not.
"""
import pytest

from app.core.scoring.constants import _fmt_dist, _walk_minutes


# --- _walk_minutes: sanity + edge-case coverage ---------------------


def test_walk_minutes_happy_path():
    # 62 m at the calibrated 62 m/min speed → exactly 1 min. One sanity
    # anchor guarding against a units-per-minute regression.
    assert _walk_minutes(62) == pytest.approx(1.0)


def test_walk_minutes_zero_input_returns_zero():
    # Standing on the amenity → 0 minutes. Guards against a division
    # regression that would surface as NaN or a tiny non-zero float.
    assert _walk_minutes(0) == 0.0


def test_walk_minutes_negative_input_returns_negative():
    # `_walk_minutes` is a pure linear helper — it does NOT clamp or
    # raise on negative input (callers pass haversine output which is
    # always ≥ 0). Pinning current behaviour so a future "safer" clamp
    # is a deliberate opt-in, not an accidental drift.
    assert _walk_minutes(-100) < 0


def test_walk_minutes_monotone():
    # Farther distances → longer walks. Trivial but guards accidental
    # sign flips in the divisor.
    assert _walk_minutes(100) < _walk_minutes(200) < _walk_minutes(500)


# --- _fmt_dist: tier-boundary + edge-case coverage ------------------


@pytest.mark.parametrize(
    "metres,expected",
    [
        # Exact 1 km boundary — must switch from `Nm` to `Nkm` format.
        (999,  "999m"),
        (1000, "1km"),
        (1001, "1.001km"),
    ],
)
def test_fmt_dist_km_boundary(metres, expected):
    assert _fmt_dist(metres) == expected


def test_fmt_dist_small_metres_stay_in_metres():
    # Sub-kilometre thresholds must render with no space and no
    # trailing zero. Guards against locale-dependent float formatting.
    assert _fmt_dist(400) == "400m"
    assert _fmt_dist(50) == "50m"


def test_fmt_dist_large_km_uses_g_format():
    # `:g` trims trailing zeros — 10 000 m → "10km" (not "10.0km").
    assert _fmt_dist(10000) == "10km"
    assert _fmt_dist(15500) == "15.5km"


def test_fmt_dist_negative_metres_treated_as_metres():
    # `_fmt_dist` does not validate input — it renders whatever integer
    # it gets in the metres branch (negative < 1000). Pinning current
    # behaviour so a future guard is a deliberate opt-in.
    assert _fmt_dist(-100) == "-100m"
