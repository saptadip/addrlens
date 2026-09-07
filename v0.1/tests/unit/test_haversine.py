"""Unit tests for `app.core.geo.haversine_m` + `bbox_around`.

Ground truth: the selfcheck block at the bottom of `app/core/geo.py`.
"""
import math

import pytest

from app.core.geo import bbox_around, haversine_m


@pytest.mark.parametrize(
    "lon1,lat1,lon2,lat2,lo,hi",
    [
        # Brandenburger Tor → Alexanderplatz ≈ 2.4 km.
        (13.3777, 52.5163, 13.4132, 52.5219, 2300, 2600),
        # Alexanderplatz → Ostbahnhof ≈ 1.95 km.
        (13.4132, 52.5219, 13.4350, 52.5103, 1800, 2200),
        # Berlin Hbf → Zoologischer Garten ≈ 3.5 km.
        (13.3689, 52.5258, 13.3327, 52.5069, 3000, 4200),
    ],
)
def test_haversine_distances_within_expected_bands(lon1, lat1, lon2, lat2, lo, hi):
    d = haversine_m(lon1, lat1, lon2, lat2)
    assert lo <= d <= hi, f"distance {d:.0f} m outside expected band [{lo}, {hi}]"


def test_haversine_zero_when_endpoints_coincide():
    assert haversine_m(13.4, 52.5, 13.4, 52.5) == 0.0


def test_haversine_is_symmetric():
    # d(a, b) == d(b, a) — a lat/lon swap must not shift the great circle.
    a = haversine_m(13.3777, 52.5163, 13.4132, 52.5219)
    b = haversine_m(13.4132, 52.5219, 13.3777, 52.5163)
    assert math.isclose(a, b, rel_tol=1e-12)


def test_haversine_returns_positive_for_distinct_points():
    d = haversine_m(13.0, 52.0, 13.1, 52.1)
    assert d > 0


def test_bbox_around_symmetric_in_latitude():
    # 800 m ± should extend the bbox symmetrically in lat.
    w, s, e, n = bbox_around(13.4, 52.5, 800)
    assert abs((n - s) - 2 * 800 / 111_320) < 1e-9


def test_bbox_around_east_gt_west_and_north_gt_south():
    w, s, e, n = bbox_around(13.4, 52.5, 500)
    assert e > w
    assert n > s


def test_bbox_around_scales_with_radius():
    _, s1, _, n1 = bbox_around(13.4, 52.5, 500)
    _, s2, _, n2 = bbox_around(13.4, 52.5, 1500)
    # Larger radius → larger bbox height.
    assert (n2 - s2) > (n1 - s1)
