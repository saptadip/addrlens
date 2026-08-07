"""Generic WFS helpers — verbatim behaviour ports from phase3/server.py.

Ship B: `noise_at()` takes a `CityConfig` (was Berlin-hardcoded). `wfs()` and
`bod_polygon_features()` were already city-agnostic; unchanged.

ponytail: module-level caches keyed by (rounded lon/lat) + threading.Lock,
same as phase3. Cache abstraction (Redis adapter) lands in Ship D step 7.
"""
import json
import threading
import urllib.parse
import urllib.request

from shapely.geometry import Point, shape

from app.cities.base import CityConfig
from app.core.geo import bbox_around, haversine_m


def wfs(base, **kw):
    kw.setdefault("service", "WFS")
    kw.setdefault("version", "2.0.0")
    kw.setdefault("request", "GetFeature")
    kw.setdefault("outputFormat", "application/json")
    kw.setdefault("srsName", "EPSG:4326")   # always WGS84 lon,lat
    url = base + "?" + urllib.parse.urlencode(kw)
    return json.loads(urllib.request.urlopen(url, timeout=60).read())


def cql_esc(s):
    return s.replace("'", "''")


# -- BOD polygon features (per-request bbox WFS, cached) ---------------------

_bod_cache, _bod_lock = {}, threading.Lock()


def bod_polygon_features(base, type_name, lon, lat, radius_m=800,
                         *, output_format="application/json"):
    """Query a WFS polygon layer within a bbox. Returns list of
    {name, lat (centroid), lon (centroid), distance_m, area_m2, props, source}.

    ponytail: centroid + haversine, not nearest-boundary-point. Ceiling: for
    very large polygons (e.g., Tiergarten) the centroid can be 500m+ from the
    nearest edge; upgrade path is a projected CRS + shapely.distance."""
    key = (base, type_name, round(lon, 4), round(lat, 4), radius_m)
    with _bod_lock:
        if key in _bod_cache: return _bod_cache[key]
    minx, miny, maxx, maxy = bbox_around(lon, lat, radius_m)
    try:
        d = wfs(base, typeNames=type_name, count=200,
                bbox=f"{minx},{miny},{maxx},{maxy},EPSG:4326",
                outputFormat=output_format)
    except Exception as e:
        return [{"_error": str(e)}]
    out = []
    for f in d.get("features", []):
        g = f.get("geometry")
        if not g: continue
        try:
            geom = shape(g)
            c = geom.centroid
            cx, cy = c.x, c.y
        except Exception:
            continue
        dist = haversine_m(lon, lat, cx, cy)
        if dist > radius_m: continue        # centroid outside radius (bbox is looser)
        props = f.get("properties") or {}
        name = (props.get("namenr") or "").strip() or (props.get("planname") or "").strip() \
               or props.get("objartname") or "—"
        out.append({"name": name, "lat": cy, "lon": cx, "distance_m": round(dist),
                    "area_m2": props.get("katasterfl") or props.get("nettospfl"),
                    "props": props, "source": "bod"})
    out.sort(key=lambda x: x["distance_m"])
    with _bod_lock:
        _bod_cache[key] = out
    return out


# -- Façade-level noise ------------------------------------------------------

_noise_cache, _noise_lock = {}, threading.Lock()


def noise_at(cfg: CityConfig, lon, lat, search_radius_m=100):
    """Nearest façade point from the strategic noise map. Returns L_DEN / L_N
    per source (road, rail, aircraft, total in dB), distance to that point,
    and provenance — or {'unavailable': True} if no façade point exists
    within a reasonable radius. Expands bbox once if the first is empty.

    ponytail: nearest-point lookup, not spatial interpolation. Ceiling: for
    a Neubau where the nearest façade point is 40m across the block, we
    report that neighbour's number as a proxy — good enough for a street-
    quiet-vs-loud read; upgrade path is per-building geometry match."""
    if not (cfg.noise_wfs_url and cfg.noise_layer):
        return {"unavailable": True, "reason": f"noise map not configured for {cfg.display_name}"}

    key = (cfg.slug, round(lon, 5), round(lat, 5))
    with _noise_lock:
        if key in _noise_cache: return _noise_cache[key]

    def _query(radius):
        minx, miny, maxx, maxy = bbox_around(lon, lat, radius)
        try:
            d = wfs(cfg.noise_wfs_url, typeNames=cfg.noise_layer, count=500,
                    bbox=f"{minx},{miny},{maxx},{maxy},EPSG:4326",
                    outputFormat=cfg.wfs_output_format)
        except Exception as e:
            return None, str(e)
        return d.get("features", []), None

    feats, err = _query(search_radius_m)
    if err:
        return {"unavailable": True, "error": err[:200]}
    if not feats:
        feats, err = _query(search_radius_m * 3)  # ~300m fallback
        if err:
            return {"unavailable": True, "error": err[:200]}
    if not feats:
        return {"unavailable": True,
                "reason": "No façade measurement within 300 m (likely outside dense residential coverage)."}

    nearest, nearest_d = None, float("inf")
    for f in feats:
        g = f.get("geometry")
        if not g or g.get("type") != "Point": continue
        cx, cy = g["coordinates"]
        d = haversine_m(lon, lat, cx, cy)
        if d < nearest_d: nearest, nearest_d = f, d

    p = nearest["properties"]
    fm = cfg.noise_field_map
    out = {
        "unavailable": False,
        "distance_m": round(nearest_d),
        "l_den": {                        # 24h day-evening-night weighted
            "total": p.get(fm["total_den"]),
            "road":  p.get(fm["road_den"]),
            "rail":  p.get(fm["rail_den"]),
            "air":   p.get(fm["air_den"]),
        },
        "l_night": {                      # 22:00–06:00
            "total": p.get(fm["total_n"]),
            "road":  p.get(fm["road_n"]),
            "rail":  p.get(fm["rail_n"]),
            "air":   p.get(fm["air_n"]),
        },
        "provenance": cfg.attribution["noise"],
    }
    with _noise_lock:
        _noise_cache[key] = out
    return out


# -- Phase 2: Umweltatlas Air Quality + Summer Heat --------------------------

_air_cache, _air_lock   = {}, threading.Lock()
_heat_cache, _heat_lock = {}, threading.Lock()


def air_quality_at(cfg: CityConfig, lon, lat, search_radius_m=150):
    """Nearest per-street NO2 baseline (2020) from the Luftreinhalteplan
    trend scenario. Feature is a LineString per road segment; we pick the
    segment whose midpoint is closest to the address. Same expand-once
    fallback as noise_at.

    ponytail: midpoint-of-segment as the distance proxy — a segment of 200 m
    on the far side of your building could be closer at the midpoint than
    a shorter one directly outside. Good enough for a "how loud/dirty is
    the street I'm on" read; upgrade path is per-line distance.
    """
    if not (cfg.air_wfs_url and cfg.air_layer):
        return {"unavailable": True, "reason": f"air-quality map not configured for {cfg.display_name}"}
    key = (cfg.slug, round(lon, 5), round(lat, 5))
    with _air_lock:
        if key in _air_cache: return _air_cache[key]

    def _query(radius):
        minx, miny, maxx, maxy = bbox_around(lon, lat, radius)
        try:
            d = wfs(cfg.air_wfs_url, typeNames=cfg.air_layer, count=200,
                    bbox=f"{minx},{miny},{maxx},{maxy},EPSG:4326",
                    outputFormat=cfg.wfs_output_format)
        except Exception as e:
            return None, str(e)
        return d.get("features", []), None

    feats, err = _query(search_radius_m)
    if err:
        return {"unavailable": True, "error": err[:200]}
    if not feats:
        feats, err = _query(search_radius_m * 3)   # ~450 m fallback
        if err:
            return {"unavailable": True, "error": err[:200]}
    if not feats:
        return {"unavailable": True,
                "reason": "No monitored road segment within 450 m (this address is off the modelled network)."}

    def _midpoint(coords):
        # A LineString may have many vertices — midpoint of the polyline in
        # index space is a fine cheap proxy for the segment's "middle".
        n = len(coords)
        if n == 0: return None
        m = coords[n // 2]
        return m[0], m[1]

    nearest, nearest_d = None, float("inf")
    for f in feats:
        g = f.get("geometry")
        if not g: continue
        coords = g.get("coordinates") or []
        if g.get("type") == "MultiLineString":
            # flatten one level
            coords = [c for part in coords for c in part]
        elif g.get("type") != "LineString":
            continue
        mid = _midpoint(coords)
        if not mid: continue
        d = haversine_m(lon, lat, mid[0], mid[1])
        if d < nearest_d: nearest, nearest_d = f, d

    if nearest is None:
        return {"unavailable": True, "reason": "No LineString feature returned."}

    p = nearest["properties"] or {}
    fm = cfg.air_field_map
    def _f(k):
        v = p.get(fm[k])
        try: return float(v) if v not in (None, "") else None
        except (ValueError, TypeError): return None
    out = {
        "unavailable": False,
        "distance_m":  round(nearest_d),
        "street":      p.get(fm["street"]),
        "no2_ugm3":    _f("no2"),        # µg/m³ annual mean (EU limit 40)
        "index_2020":  _f("index"),      # combined NO2 + PM10, ~0 clean … ~1 heavily loaded
        "traffic_day": _f("traffic"),    # cars/day on this segment
        "length_m":    _f("length"),
        "year":        2020,
        "provenance":  cfg.attribution.get("air", ""),
    }
    with _air_lock:
        _air_cache[key] = out
    return out


def summer_heat_at(cfg: CityConfig, lon, lat, search_radius_m=60):
    """Per-block PET (Physiologisch Äquivalente Temperatur) day-time
    bioclimate classification for residential areas (Klimabewertung 2022).
    Bbox query + point-in-polygon on the returned features."""
    if not (cfg.heat_wfs_url and cfg.heat_layer):
        return {"unavailable": True, "reason": f"summer-heat map not configured for {cfg.display_name}"}
    key = (cfg.slug, round(lon, 5), round(lat, 5))
    with _heat_lock:
        if key in _heat_cache: return _heat_cache[key]

    def _query(radius):
        minx, miny, maxx, maxy = bbox_around(lon, lat, radius)
        try:
            d = wfs(cfg.heat_wfs_url, typeNames=cfg.heat_layer, count=50,
                    bbox=f"{minx},{miny},{maxx},{maxy},EPSG:4326",
                    outputFormat=cfg.wfs_output_format)
        except Exception as e:
            return None, str(e)
        return d.get("features", []), None

    feats, err = _query(search_radius_m)
    if err:
        return {"unavailable": True, "error": err[:200]}
    if not feats:
        feats, err = _query(search_radius_m * 5)   # ~300 m fallback
        if err:
            return {"unavailable": True, "error": err[:200]}
    if not feats:
        return {"unavailable": True,
                "reason": "No residential heat-classification polygon within 300 m (address off the modelled area)."}

    pt = Point(lon, lat)
    fm = cfg.heat_field_map
    inside = None
    nearest, nearest_d = None, float("inf")
    for f in feats:
        g = f.get("geometry")
        if not g: continue
        try:
            geom = shape(g)
        except Exception:
            continue
        if geom.contains(pt):
            inside = f["properties"]
            break
        # Track fallback: nearest polygon centroid (haversine) if no containment
        c = geom.centroid
        d = haversine_m(lon, lat, c.x, c.y)
        if d < nearest_d: nearest, nearest_d = f["properties"], d

    props = inside or nearest
    if not props:
        return {"unavailable": True, "reason": "No usable polygon geometry."}
    day_class = (props.get(fm["day_class"]) or "").strip() or None
    out = {
        "unavailable": False,
        "day_class":   day_class,
        "inside":      inside is not None,
        "distance_m":  0 if inside is not None else round(nearest_d),
        "year":        2022,
        "provenance":  cfg.attribution.get("heat", ""),
    }
    with _heat_lock:
        _heat_cache[key] = out
    return out


if __name__ == "__main__":
    # Pure asserts only — no network in the module selfcheck.
    assert cql_esc("O'Neil") == "O''Neil"
    # bod_polygon_features stubbed via monkey-patch: verify cache path + centroid math.
    import app.core.wfs as m
    calls = []
    def _fake_wfs(base, **kw):
        calls.append((base, kw))
        return {"features": [{
            "geometry": {"type": "Polygon", "coordinates": [[
                [13.4, 52.5], [13.402, 52.5], [13.402, 52.502], [13.4, 52.502], [13.4, 52.5]]]},
            "properties": {"namenr": "Test Park", "katasterfl": 5000, "bezirkname": "Mitte"},
        }]}
    real_wfs = m.wfs
    m.wfs = _fake_wfs
    try:
        # Clear cache so a fresh key hits our fake. Call through m. because
        # `python -m app.core.wfs` runs the file as __main__ and the import
        # above loads it a SECOND time under its real name — the monkey-patch
        # only takes on that second copy.
        m._bod_cache.clear()
        got = m.bod_polygon_features("http://x", "layer:a", 13.401, 52.501, radius_m=800)
        assert len(got) == 1 and got[0]["name"] == "Test Park", got
        assert got[0]["source"] == "bod"
        assert got[0]["area_m2"] == 5000
        # Second call same key hits cache — no additional _fake_wfs call.
        n = len(calls)
        m.bod_polygon_features("http://x", "layer:a", 13.401, 52.501, radius_m=800)
        assert len(calls) == n, "cache miss on repeat call"
    finally:
        m.wfs = real_wfs
        m._bod_cache.clear()
    print("wfs.py selfcheck OK")
