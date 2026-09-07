"""Unit tests for `Index.nearest_station` — the connectivity helper.

The function is a pure list-scan; instantiating the full `Index` boots
15 s of live WFS, so we test the method as an unbound function via
`Index.nearest_station.__func__` — no `self` state is read (the
implementation only uses its `points` argument).
"""
import math

from app.core.index import Index


def _nearest(points, lon, lat):
    """Call the unbound method — `self` is unused by nearest_station."""
    return Index.nearest_station(None, points, lon, lat)


def test_nearest_station_empty_returns_none():
    assert _nearest([], 13.4, 52.5) is None


def test_nearest_station_single_point_returned_with_distance():
    pt = {"name": "S Alexanderplatz", "lat": 52.5219, "lon": 13.4132}
    r = _nearest([pt], 13.4132, 52.5219)
    assert r is not None
    assert r["name"] == "S Alexanderplatz"
    # Same point → distance ≈ 0.
    assert r["distance_m"] == 0


def test_nearest_station_picks_closest_of_many():
    # Query point near Alexanderplatz.
    query_lon, query_lat = 13.4132, 52.5219
    points = [
        {"name": "S Ostbahnhof",   "lat": 52.5103, "lon": 13.4351},   # ~2.7 km
        {"name": "S Alexanderplatz","lat": 52.5219, "lon": 13.4132},  # 0 m
        {"name": "U Zoo",           "lat": 52.5069, "lon": 13.3327},  # ~5 km
    ]
    r = _nearest(points, query_lon, query_lat)
    assert r["name"] == "S Alexanderplatz"


def test_nearest_station_carries_original_keys_through():
    # Extra keys on the winning point must survive the spread.
    pt = {"name": "Test", "lat": 52.5, "lon": 13.4, "mode": "S", "extra": 42}
    r = _nearest([pt], 13.4, 52.5)
    assert r["mode"] == "S"
    assert r["extra"] == 42
    assert "distance_m" in r


def test_nearest_station_distance_is_int():
    # distance_m is always rounded to int by the implementation.
    r = _nearest(
        [{"name": "X", "lat": 52.5163, "lon": 13.3777}],
        13.4132, 52.5219,
    )
    assert isinstance(r["distance_m"], int)
    # And roughly matches haversine.
    assert 2000 < r["distance_m"] < 3000
