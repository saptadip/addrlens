"""Generic WFS helpers — verbatim behaviour ports from phase3/server.py.

Ship B: `noise_at()` takes a `CityConfig` (was Berlin-hardcoded). `wfs()` and
`bod_polygon_features()` were already city-agnostic; unchanged.

Ship D step 1: `wfs()` moved off stdlib `urllib.request` onto a shared
`httpx.Client` with granular timeouts (connect/read/write/pool), a bounded
keep-alive pool, and single-shot retry on transient failures (network errors
+ 502/503/504). All timeouts and the retry count are env-tunable; defaults
match "fail fast, don't wedge a worker for a minute" — one wedged read
plus one retry now caps a `wfs()` call at roughly 30 s wall-clock instead
of the old single-shot 60 s socket timeout.

Ship D step 2: the four per-function unbounded `dict` caches
(`_bod_cache`, `_noise_cache`, `_air_cache`, `_heat_cache`) that lived in
this file were replaced by the shared `app.core.cache.HOT_PATH`
`TTLCache` (default 4096 entries × 1-hour TTL, env-tunable via
`APP_CACHE_SIZE` / `APP_CACHE_TTL_S`). Namespaced keys keep the
per-dataset behaviour unchanged. Prior to this the caches grew for the
process lifetime — a slow leak on any long-running deployment.

ponytail: single-process TTLCache is the right shape for the current
one-instance-per-city deployment. A Redis-backed shared cache would let
multiple replicas share hits; upgrade path lives in
`app.core.cache.NamedCache` — swap the underlying dict for a Redis
adapter without touching callers.
"""
import json
import os
import threading
import time
import urllib.parse

import httpx
from shapely.geometry import Point, shape

from app.cities.base import CityConfig
from app.core.cache import HOT_PATH as _cache
from app.core.geo import bbox_around, haversine_m


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


# Timeouts and retry knobs. Negative values are clamped to a small positive
# floor so a misconfigured env var fails at import (or is quietly corrected)
# rather than blowing up inside `httpx.Timeout` on the first request.
_TIMEOUT_FLOOR_S   = 0.001
_CONNECT_TIMEOUT_S = max(_TIMEOUT_FLOOR_S, _env_float("WFS_CONNECT_TIMEOUT_S", 5.0))
_READ_TIMEOUT_S    = max(_TIMEOUT_FLOOR_S, _env_float("WFS_READ_TIMEOUT_S",   15.0))
_WRITE_TIMEOUT_S   = max(_TIMEOUT_FLOOR_S, _env_float("WFS_WRITE_TIMEOUT_S",   5.0))
_POOL_TIMEOUT_S    = max(_TIMEOUT_FLOOR_S, _env_float("WFS_POOL_TIMEOUT_S",    5.0))
_RETRIES           = max(0, _env_int("WFS_RETRIES", 1))
_RETRY_BACKOFF_S   = max(0.0, _env_float("WFS_RETRY_BACKOFF_S", 0.5))
_MAX_KEEPALIVE     = max(1, _env_int("WFS_MAX_KEEPALIVE", 8))
_MAX_CONNECTIONS   = max(1, _env_int("WFS_MAX_CONNECTIONS", 16))
_RETRY_STATUS      = frozenset({502, 503, 504})
_USER_AGENT        = "berlin-address-intelligence/v0.1 (+wfs client)"


_client: httpx.Client | None = None
_client_lock = threading.Lock()


def _build_client() -> httpx.Client:
    return httpx.Client(
        timeout=httpx.Timeout(
            connect=_CONNECT_TIMEOUT_S,
            read=_READ_TIMEOUT_S,
            write=_WRITE_TIMEOUT_S,
            pool=_POOL_TIMEOUT_S,
        ),
        limits=httpx.Limits(
            max_keepalive_connections=_MAX_KEEPALIVE,
            max_connections=_MAX_CONNECTIONS,
        ),
        headers={"User-Agent": _USER_AGENT},
        follow_redirects=True,
    )


def _get_client() -> httpx.Client:
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                _client = _build_client()
    return _client


def wfs(base, **kw):
    kw.setdefault("service", "WFS")
    kw.setdefault("version", "2.0.0")
    kw.setdefault("request", "GetFeature")
    kw.setdefault("outputFormat", "application/json")
    kw.setdefault("srsName", "EPSG:4326")   # always WGS84 lon,lat
    url = base + "?" + urllib.parse.urlencode(kw)
    client = _get_client()
    attempts = _RETRIES + 1
    for attempt in range(attempts):
        try:
            r = client.get(url)
        except (httpx.TimeoutException, httpx.NetworkError):
            if attempt + 1 >= attempts:
                raise
            time.sleep(_RETRY_BACKOFF_S * (attempt + 1))
            continue
        if r.status_code in _RETRY_STATUS and attempt + 1 < attempts:
            time.sleep(_RETRY_BACKOFF_S * (attempt + 1))
            continue
        r.raise_for_status()
        return r.json()
    # Unreachable: loop either returns or re-raises the last exception.
    raise RuntimeError("wfs retry loop exited without a response")


def cql_esc(s):
    return s.replace("'", "''")


# -- BOD polygon features (per-request bbox WFS, cached) ---------------------


def bod_polygon_features(base, type_name, lon, lat, radius_m=800,
                         *, output_format="application/json"):
    """Query a WFS polygon layer within a bbox. Returns list of
    {name, lat (centroid), lon (centroid), distance_m, area_m2, props, source}.

    ponytail: centroid + haversine, not nearest-boundary-point. Ceiling: for
    very large polygons (e.g., Tiergarten) the centroid can be 500m+ from the
    nearest edge; upgrade path is a projected CRS + shapely.distance."""
    key = ("bod", base, type_name, round(lon, 4), round(lat, 4), radius_m)
    hit = _cache.get(key)
    if hit is not None:
        return hit
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
    _cache.set(key, out)
    return out


# -- Façade-level noise ------------------------------------------------------


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

    key = ("noise", cfg.slug, round(lon, 5), round(lat, 5))
    hit = _cache.get(key)
    if hit is not None:
        return hit

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
    _cache.set(key, out)
    return out


# -- Phase 2: Umweltatlas Air Quality + Summer Heat --------------------------


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
    key = ("air", cfg.slug, round(lon, 5), round(lat, 5))
    hit = _cache.get(key)
    if hit is not None:
        return hit

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
    _cache.set(key, out)
    return out


def summer_heat_at(cfg: CityConfig, lon, lat, search_radius_m=60):
    """Per-block PET (Physiologisch Äquivalente Temperatur) day-time
    bioclimate classification for residential areas (Klimabewertung 2022).
    Bbox query + point-in-polygon on the returned features."""
    if not (cfg.heat_wfs_url and cfg.heat_layer):
        return {"unavailable": True, "reason": f"summer-heat map not configured for {cfg.display_name}"}
    key = ("heat", cfg.slug, round(lon, 5), round(lat, 5))
    hit = _cache.get(key)
    if hit is not None:
        return hit

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
    _cache.set(key, out)
    return out


if __name__ == "__main__":
    # Pure asserts only — no network in the module selfcheck.
    assert cql_esc("O'Neil") == "O''Neil"

    # -- Env-tunable timeout / retry knobs read at import time.
    assert _CONNECT_TIMEOUT_S == 5.0,  _CONNECT_TIMEOUT_S
    assert _READ_TIMEOUT_S   == 15.0, _READ_TIMEOUT_S
    assert _RETRIES          == 1,    _RETRIES
    assert 502 in _RETRY_STATUS and 503 in _RETRY_STATUS and 504 in _RETRY_STATUS

    # -- Negative env values are clamped to the floor, not passed through.
    assert max(_TIMEOUT_FLOOR_S, _env_float("WFS_DOES_NOT_EXIST", -7.0)) == _TIMEOUT_FLOOR_S

    # -- Client is a shared, lazily-built httpx.Client with our timeouts.
    import app.core.wfs as m
    m._client = None
    c = m._get_client()
    assert isinstance(c, httpx.Client)
    assert m._get_client() is c, "client not memoised"
    # httpx.Timeout compares by tuple of components — pick a couple of fields.
    assert c.timeout.connect == 5.0
    assert c.timeout.read   == 15.0

    # -- Retry loop: fail once with a timeout, then succeed. Stub the client.
    class _StubClient:
        def __init__(self, script):
            self.script = list(script)
            self.calls = []
        def get(self, url):
            self.calls.append(url)
            step = self.script.pop(0)
            if isinstance(step, Exception): raise step
            return step

    class _StubResp:
        def __init__(self, status, body=None):
            self.status_code = status
            self._body = body or {"features": []}
        def raise_for_status(self):
            if self.status_code >= 400:
                raise httpx.HTTPStatusError("bad", request=None, response=None)
        def json(self):
            return self._body

    # Patch backoff to zero so the selfcheck stays instant.
    real_backoff = m._RETRY_BACKOFF_S
    m._RETRY_BACKOFF_S = 0.0
    real_get_client = m._get_client
    try:
        # (a) Retriable exception then success.
        stub = _StubClient([httpx.ConnectTimeout("boom"), _StubResp(200, {"ok": 1})])
        m._get_client = lambda: stub
        got = m.wfs("http://x", typeNames="l")
        assert got == {"ok": 1}, got
        assert len(stub.calls) == 2

        # (b) 503 then success.
        stub = _StubClient([_StubResp(503), _StubResp(200, {"ok": 2})])
        m._get_client = lambda: stub
        got = m.wfs("http://x", typeNames="l")
        assert got == {"ok": 2}, got
        assert len(stub.calls) == 2

        # (c) All attempts exhaust on network error → re-raise.
        stub = _StubClient([httpx.ConnectError("no"), httpx.ConnectError("no")])
        m._get_client = lambda: stub
        try:
            m.wfs("http://x", typeNames="l")
        except httpx.NetworkError:
            pass
        else:
            raise AssertionError("expected NetworkError after retries exhausted")
        assert len(stub.calls) == 2

        # (d) Non-retriable 4xx bubbles immediately.
        stub = _StubClient([_StubResp(400)])
        m._get_client = lambda: stub
        try:
            m.wfs("http://x", typeNames="l")
        except httpx.HTTPStatusError:
            pass
        else:
            raise AssertionError("expected HTTPStatusError on 400")
        assert len(stub.calls) == 1
    finally:
        m._RETRY_BACKOFF_S = real_backoff
        m._get_client = real_get_client

    # -- bod_polygon_features: cache path + centroid math (unchanged behaviour).
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
        # Clear shared cache so a fresh key hits our fake. Call through
        # `m.` because `python -m app.core.wfs` runs the file as __main__
        # and the import above loads it a SECOND time under its real name
        # — the monkey-patch only takes on that second copy.
        m._cache.clear()
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
        m._cache.clear()
    print("wfs.py selfcheck OK")
