"""Unit tests for `app.core.geo.haversine_m` + `bbox_around`.

The Brandenburger-Tor / 800 m bbox happy path is already asserted in the
`if __name__ == "__main__":` selfcheck at the bottom of `app/core/geo.py`.
These tests deliberately DO NOT duplicate that ground truth — they focus
on edge cases + properties (symmetry, antipode distance, zero radius,
polar-latitude bbox stability) that the selfcheck does not cover.
"""
import math

import pytest

from app.core.geo import bbox_around, haversine_m


# --- Sanity anchors (kept: one happy path + one symmetry property) ---


def test_haversine_happy_path_berlin_landmarks():
    # Brandenburger Tor → Alexanderplatz ≈ 2.4 km. Guards against a
    # unit-conversion regression (km vs m) that a pure-property test
    # would miss.
    d = haversine_m(13.3777, 52.5163, 13.4132, 52.5219)
    assert 2300 < d < 2600, f"expected ~2.4 km, got {d:.0f} m"


def test_haversine_is_symmetric():
    # d(a, b) == d(b, a) — swapping endpoints must not shift the great circle.
    a = haversine_m(13.3777, 52.5163, 13.4132, 52.5219)
    b = haversine_m(13.4132, 52.5219, 13.3777, 52.5163)
    assert math.isclose(a, b, rel_tol=1e-12)


# --- Edge cases the selfcheck does not cover -------------------------


def test_haversine_zero_when_endpoints_coincide():
    # Same point → 0 m exactly. Guards a floating-point drift regression
    # where `math.asin(sqrt(0))` might return a tiny non-zero value.
    assert haversine_m(13.4, 52.5, 13.4, 52.5) == 0.0


def test_haversine_negative_coordinates_supported():
    # Southern hemisphere / western hemisphere (Buenos Aires → Rio de
    # Janeiro ≈ 1970 km). Guards against a `math.radians` sign bug.
    d = haversine_m(-58.38, -34.60, -43.20, -22.91)
    assert 1_900_000 < d < 2_050_000, f"BA→Rio expected ~1.97 Mm, got {d:.0f} m"


def test_haversine_antipode_distance_is_half_earth_circumference():
    # Antipodal points → half the Earth's circumference (≈ 20 015 km).
    # Extreme-value guard against catastrophic cancellation in the formula.
    d = haversine_m(0.0, 0.0, 180.0, 0.0)
    assert 19_900_000 < d < 20_100_000, f"antipode expected ~20 015 km, got {d:.0f} m"


# --- bbox_around edge cases ------------------------------------------


def test_bbox_around_radius_zero_returns_degenerate_bbox():
    # radius=0 → single-point bbox. Guards against a divide-by-zero
    # regression in the longitude scaling factor.
    w, s, e, n = bbox_around(13.4, 52.5, 0)
    assert w == 13.4
    assert e == 13.4
    assert s == 52.5
    assert n == 52.5


def test_bbox_around_near_polar_latitude_stays_finite():
    # cos(89.999°) is ~1.7e-5 which would blow the dlon term up without the
    # `max(0.1, cos(lat))` clamp. Assert the bbox width stays sane at
    # extreme latitudes — this is the whole point of the clamp.
    w, s, e, n = bbox_around(0.0, 89.999, 1000)
    dlon = e - w
    # With cos-lat clamped to 0.1, dlon = 2 * 1000 / (111320 * 0.1) ≈ 0.18°.
    # Without the clamp it would be > 1000°.
    assert 0 < dlon < 1.0, f"polar bbox width blew up: {dlon}°"
    assert n > s


def test_bbox_around_scales_with_radius():
    # Larger radius → larger bbox in both axes. Property, not a magic value.
    w1, s1, e1, n1 = bbox_around(13.4, 52.5, 500)
    w2, s2, e2, n2 = bbox_around(13.4, 52.5, 1500)
    assert (n2 - s2) > (n1 - s1)
    assert (e2 - w2) > (e1 - w1)


@pytest.mark.parametrize("radius", [100, 500, 2000])
def test_bbox_around_is_east_north_positive(radius):
    # Basic ordering invariant: e > w, n > s at any positive radius.
    w, s, e, n = bbox_around(13.4, 52.5, radius)
    assert e > w
    assert n > s
