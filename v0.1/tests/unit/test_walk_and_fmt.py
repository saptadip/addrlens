"""Unit tests for the two smallest scoring primitives:
`_walk_minutes` (haversine → walk minutes) and `_fmt_dist` (metre → rule
label). Both live in `app.core.scoring.constants`.

Ground truth: the selfcheck at the bottom of `app/core/scoring/constants.py`.
"""
import pytest

from app.core.scoring.constants import _fmt_dist, _walk_minutes


@pytest.mark.parametrize(
    "metres,expected_min",
    [
        (0,   0.0),
        (62,  1.0),          # exactly 1 minute at the calibrated 62 m/min speed
        (124, 2.0),
        (930, 15.0),
    ],
)
def test_walk_minutes_scales_linearly(metres, expected_min):
    assert abs(_walk_minutes(metres) - expected_min) < 1e-9


def test_walk_minutes_monotone():
    # Farther distances → longer walks. Trivial but guards accidental sign flips.
    assert _walk_minutes(100) < _walk_minutes(200) < _walk_minutes(500)


@pytest.mark.parametrize(
    "metres,expected",
    [
        (400,  "400m"),
        (999,  "999m"),
        (1000, "1km"),
        (1500, "1.5km"),
        (2500, "2.5km"),
        (10000, "10km"),
    ],
)
def test_fmt_dist_format(metres, expected):
    assert _fmt_dist(metres) == expected
