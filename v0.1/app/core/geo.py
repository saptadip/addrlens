"""Great-circle distance + lat/lon bbox helper. Verbatim from phase3/server.py."""
import math


def haversine_m(lon1, lat1, lon2, lat2):
    """Great-circle distance in metres."""
    R = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2 * R * math.asin(math.sqrt(a))


def bbox_around(lon, lat, radius_m):
    """Small lat/lon bbox around a point. Rough, adequate for a WFS filter."""
    dlat = radius_m / 111_320
    dlon = radius_m / (111_320 * max(0.1, math.cos(math.radians(lat))))
    return (lon - dlon, lat - dlat, lon + dlon, lat + dlat)


if __name__ == "__main__":
    # Brandenburger Tor → Alexanderplatz ≈ 2.4 km.
    d = haversine_m(13.3777, 52.5163, 13.4132, 52.5219)
    assert 2300 < d < 2600, f"expected ~2.4 km, got {d:.0f} m"
    # 800m bbox around Berlin centre is symmetric ± ~0.007° lat.
    w, s, e, n = bbox_around(13.4, 52.5, 800)
    assert abs((n - s) - 2 * 800 / 111_320) < 1e-9
    assert e > w and n > s
    print("geo.py selfcheck OK")
