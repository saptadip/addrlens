"""Shared WFS layer loaders used at Index-boot time.

Two shapes covered:

- `load_polygon_layer(cfg, url, layer, count)` — returns `[(props, geom),
  ...]` where geom is a shapely geometry. Skips features with no
  geometry (same tolerance the pre-split per-loader loops had).
- `load_point_layer_raw(cfg, url, layer, count)` — returns
  `[(props, coords), ...]` where coords is the raw `[lon, lat]` list.
  MultiPoint (Berlin's tram feed) is collapsed to its first coord —
  same as the pre-split logic in `Index._load_tram`.

Both helpers accept the full `CityConfig` so they can pick up
`wfs_output_format` without the caller having to pass it separately.

Also exposes `log_load(label)` — a tiny stdout helper that emits the
"loading X… " prefix the boot-time loaders write before each WFS call.
Kept as a public helper so caller and helper share the exact same
message shape.
"""

import sys

from shapely.geometry import shape

from app.cities.base import CityConfig
from app.core.wfs import wfs


def log_load(label: str) -> None:
    """Write "loading {label}… " to stdout (no newline, immediate flush).

    Every Index loader announces itself with this prefix before firing
    the WFS request; the trailing "N items" line is printed by the
    caller once the load succeeds.
    """
    sys.stdout.write(f"loading {label}… ")
    sys.stdout.flush()


def _fetch_features(cfg: CityConfig, url: str, layer: str, count: int) -> list:
    """One WFS GetFeature — return the raw feature list (`[]` if the
    response has no `features` key). Errors bubble up; the pre-split
    loaders let them propagate to `Index.__init__` too.
    """
    r = wfs(url, typeNames=layer, count=count, outputFormat=cfg.wfs_output_format)
    return r.get("features") or []


def load_polygon_layer(cfg: CityConfig, url: str, layer: str, count: int) -> list:
    """List of `(props, shapely.geometry)` for a WFS polygon layer.

    Features with no `geometry` are dropped — same tolerance the
    pre-split per-loader loops had. `properties: null` is normalised
    to `{}` so downstream callers can safely `.get(...)` — this
    matches the `p = f["properties"] or {}` guard several pre-split
    loops carried inline.
    """
    out = []
    for f in _fetch_features(cfg, url, layer, count):
        if not f.get("geometry"):
            continue
        out.append((f.get("properties") or {}, shape(f["geometry"])))
    return out


def load_point_layer_raw(cfg: CityConfig, url: str, layer: str, count: int) -> list:
    """List of `(props, coords)` for a WFS point layer.

    `coords` is the raw `[lon, lat]` list; callers unpack as
    `lo, la = coords`. MultiPoint geometries collapse to their first
    coord (Berlin's tram feed uses MultiPoint one-per-stop). Features
    with no `geometry` or an empty MultiPoint are dropped. As with
    `load_polygon_layer`, `properties: null` is normalised to `{}`.

    ponytail: the empty-coords drop is stricter than the pre-split
    per-loader loops, which would have crashed at `lo, la = coords`.
    Preferred — a malformed feature shouldn't break Index boot.
    """
    out = []
    for f in _fetch_features(cfg, url, layer, count):
        g = f.get("geometry")
        if not g:
            continue
        coords = g.get("coordinates")
        if not coords:
            continue
        if g.get("type") == "MultiPoint":
            coords = coords[0]
        out.append((f.get("properties") or {}, coords))
    return out


if __name__ == "__main__":
    # Pure asserts only — no network. `python -m …` loads this module
    # twice (as `__main__` AND under its real name); patch both copies
    # so the resolution inside `_fetch_features` sees the stub.
    import sys as _sys
    from shapely.geometry import Point as _Point

    _real_pkg = _sys.modules.get("app.core.loaders.wfs_layer")

    class _Cfg:
        wfs_output_format = "application/json"

    def _fake_wfs(base, **kw):
        return {"features": [
            {"geometry": {"type": "Polygon",
                          "coordinates": [[[13.4, 52.5], [13.42, 52.5],
                                           [13.42, 52.52], [13.4, 52.52],
                                           [13.4, 52.5]]]},
             "properties": {"name": "Poly A", "wert": 1}},
            {"geometry": None, "properties": {"name": "no-geom"}},
            {"geometry": {"type": "Polygon",
                          "coordinates": [[[13.5, 52.5], [13.52, 52.5],
                                           [13.52, 52.52], [13.5, 52.52],
                                           [13.5, 52.5]]]},
             "properties": {"name": "Poly B"}},
            # `properties: null` from the WFS must normalise to {} — regression
            # guard for the drop of the pre-split `p = f["properties"] or {}`.
            {"geometry": {"type": "Polygon",
                          "coordinates": [[[13.6, 52.5], [13.62, 52.5],
                                           [13.62, 52.52], [13.6, 52.52],
                                           [13.6, 52.5]]]},
             "properties": None},
        ]}

    _real_wfs = wfs
    globals()["wfs"] = _fake_wfs
    if _real_pkg is not None:
        _real_pkg.wfs = _fake_wfs
    try:
        polys = load_polygon_layer(_Cfg(), "http://x", "l", 100)
        assert len(polys) == 3, polys           # only no-geom feature dropped
        p0, g0 = polys[0]
        assert p0["name"] == "Poly A"
        assert g0.geom_type == "Polygon"
        assert g0.contains(_Point(13.41, 52.51))
        # `properties: null` was normalised to {} — safe to .get(...) downstream.
        p_null, _ = polys[-1]
        assert p_null == {}, p_null
    finally:
        globals()["wfs"] = _real_wfs
        if _real_pkg is not None:
            _real_pkg.wfs = _real_wfs

    def _fake_wfs_pts(base, **kw):
        return {"features": [
            {"geometry": {"type": "Point", "coordinates": [13.4, 52.5]},
             "properties": {"name": "P1"}},
            {"geometry": None, "properties": {"name": "no-geom"}},
            {"geometry": {"type": "Point", "coordinates": []},
             "properties": {"name": "empty-coords"}},
            {"geometry": {"type": "MultiPoint",
                          "coordinates": [[13.41, 52.51], [13.42, 52.52]]},
             "properties": {"name": "MP"}},
            # `properties: null` regression guard, same as polygon path.
            {"geometry": {"type": "Point", "coordinates": [13.5, 52.6]},
             "properties": None},
        ]}

    globals()["wfs"] = _fake_wfs_pts
    if _real_pkg is not None:
        _real_pkg.wfs = _fake_wfs_pts
    try:
        pts = load_point_layer_raw(_Cfg(), "http://x", "l", 100)
        # 5 in → 3 out (no-geom + empty-coords dropped; null-props kept).
        assert len(pts) == 3, pts
        assert pts[0][0]["name"] == "P1"
        assert pts[0][1] == [13.4, 52.5]
        # MultiPoint collapsed to first coord.
        assert pts[1][0]["name"] == "MP"
        assert pts[1][1] == [13.41, 52.51]
        # `properties: null` normalised to {}.
        assert pts[2][0] == {}, pts[2][0]
        assert pts[2][1] == [13.5, 52.6]
    finally:
        globals()["wfs"] = _real_wfs
        if _real_pkg is not None:
            _real_pkg.wfs = _real_wfs

    print("loaders.wfs_layer selfcheck OK")
