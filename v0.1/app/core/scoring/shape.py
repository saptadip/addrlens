"""Feature-shape helpers — coerce raw BOD / OSM records into the
response-ready feature dict every tile emits.

Every `_shape_*` returns either the shaped dict or `None` when required
fields are missing / invalid, so callers can `filter(None, ...)` the
list without further guards. `_shape_gesix` is shared between YF and
Newcomer lenses (only `card_key` differs).
"""

from typing import Optional

from app.core.scoring.constants import (
    TIER_AMBER, TIER_GREEN, TIER_RED, TIER_UNKNOWN, _walk_minutes,
)


def _prune(d: dict) -> dict:
    """Drop keys whose value is None or empty string. Keeps 0, False, [], {}
    so 'if feature.wheelchair:' still works but 'website: ""' doesn't leak
    an empty link into the response."""
    return {k: v for k, v in d.items() if v not in (None, "")}


def _int_or_none(x):
    """Coerce BOD raw field (str-int like '65' from kita e_platz) to int.
    Returns None on empty/None/unparseable."""
    try:
        return int(x) if x not in (None, "") else None
    except (ValueError, TypeError):
        return None


def _valid_latlon(d: dict) -> bool:
    """Check `lat`/`lon` are finite floats in real-world range. Prevents
    the frontend from trying to pin at (NaN, NaN) or (999, 999)."""
    lat, lon = d.get("lat"), d.get("lon")
    return (isinstance(lat, (int, float)) and isinstance(lon, (int, float))
            and -90 <= lat <= 90 and -180 <= lon <= 180)


def _tile(key: str, label: str, icon: str, *,
          tier: str, rule: str, numeric: str = "",
          caveat: str = "", features: list = None,
          sources: list = None, metadata: dict = None) -> dict:
    """Lightweight Spec D tile dict builder.  Fills every mandatory key with a
    safe default so callers only supply the fields that vary.

    ponytail: no schema validation here — callers are responsible for correct
    types; a future Pydantic model could replace this at v2."""
    d = {
        "key":      key,
        "label":    label,
        "icon":     icon,
        "tier":     tier,
        "rule":     rule,
        "numeric":  numeric,
        "caveat":   caveat,
        "features": features if features is not None else [],
        "sources":  sources  if sources  is not None else [],
    }
    if metadata is not None:
        d["metadata"] = metadata
    return d


def _shape_kita(o: dict, fm: dict) -> Optional[dict]:
    """Response-shape a kita feature from Index.kitas_near_bod output.
    Required: name, lat, lon, distance_m. All other fields optional and only
    included if the BOD row carries them. Kept in sync with the raw-mode
    kitaDetailHtml popover so Life Mode shows the same rich detail."""
    p = o.get("props") or {}
    street_line = " ".join(x for x in [(p.get("e_strasse") or "").strip(),
                                        (p.get("e_hnr") or "").strip()] if x).strip()
    if p.get("e_zusatz"):
        street_line = (street_line + (p.get("e_zusatz") or "")).strip()
    address = ", ".join(x for x in [street_line, (p.get("e_plz") or "").strip()] if x).strip(", ")
    approaches = " · ".join(x for x in [(p.get("ang_1") or "").strip(),
                                         (p.get("ang_2") or "").strip()] if x)
    r = _prune({
        "name": (o.get("name") or "").strip(),
        "lat":  o.get("lat"), "lon": o.get("lon"),
        "distance_m": o.get("distance_m"),
        "address":       address,
        "phone":        (p.get("e_tel") or "").strip(),
        "website":      (p.get("e_web") or "").strip(),
        "traeger_name": (p.get("t_name") or "").strip(),
        "capacity":       _int_or_none(p.get(fm["capacity"])),
        "operator_type": (p.get(fm["operator_type"]) or "").strip(),
        "approach":      approaches,
    })
    if not r.get("name") or not _valid_latlon(r) or r.get("distance_m") is None:
        return None
    return r


def _shape_playground(o: dict) -> Optional[dict]:
    """Response-shape a playground feature. BOD side has area (katasterfl
    or nettospfl) + optional renovation year (sanierjahr). OSM side just
    has {name, lat, lon, distance_m}. This shape covers both."""
    p = o.get("props") or {}
    r = _prune({
        "name": (o.get("name") or "").strip(),
        "lat":  o.get("lat"), "lon": o.get("lon"),
        "distance_m": o.get("distance_m"),
        "area_m2":        _int_or_none(p.get("katasterfl") or p.get("nettospfl")),
        "renovated_year": _int_or_none(p.get("sanierjahr")),
    })
    if not r.get("name") or not _valid_latlon(r) or r.get("distance_m") is None:
        return None
    return r


def _shape_paediatric_gp(o: dict) -> Optional[dict]:
    """Response-shape a paediatric doctor feature from OSM gps bucket.
    Composes address from OSM addr:* tags. `wheelchair` only surfaced
    when yes (opt-in disclosure of accessibility)."""
    t = o.get("tags") or {}
    street = (t.get("addr:street") or "").strip()
    hnr    = (t.get("addr:housenumber") or "").strip()
    plz    = (t.get("addr:postcode") or "").strip()
    city   = (t.get("addr:city") or "").strip()
    addr_left  = f"{street} {hnr}".strip()
    addr_right = f"{plz} {city}".strip()
    address = ", ".join(p for p in [addr_left, addr_right] if p)

    r = _prune({
        "name": (o.get("name") or "").strip(),
        "lat":  o.get("lat"), "lon": o.get("lon"),
        "distance_m": o.get("distance_m"),
        "address": address,
        "phone":   (t.get("phone") or "").strip(),
        "website": (t.get("website") or "").strip(),
        "hours":   (t.get("opening_hours") or "").strip(),
        "wheelchair": True if t.get("wheelchair") == "yes" else None,
    })
    if not r.get("name") or not _valid_latlon(r) or r.get("distance_m") is None:
        return None
    return r


def _shape_office(o: dict) -> Optional[dict]:
    """Response-shape a bureaucracy office feature. Historically served
    both the (removed) Bureaucracy lens and the Newcomer Bürgeramt tile;
    still used by the Newcomer lens for Bürgerämter.

    walk_min is computed here from distance_m via _walk_minutes and
    rounded to int."""
    d = o.get("distance_m")
    r = _prune({
        "name": (o.get("name") or "").strip(),
        "lat":  o.get("lat"), "lon": o.get("lon"),
        "distance_m": d,
        "address": (o.get("address") or "").strip(),
        "website": (o.get("website") or "").strip(),
        "walk_min": round(_walk_minutes(d)) if isinstance(d, (int, float)) else None,
    })
    if not r.get("name") or not _valid_latlon(r) or r.get("distance_m") is None:
        return None
    return r


def _shape_transit_stop(o: dict, modality: str) -> Optional[dict]:
    """Shape a transit-stop feature — same field set across S/U/Tram/Bus so the
    YF Transit tile can render a uniform list. `modality` is one of
    'S-Bahn' / 'U-Bahn' / 'Tram' / 'Bus'. Required: name, lat, lon, distance_m."""
    if not o:
        return None
    d = o.get("distance_m")
    r = _prune({
        "name": (o.get("name") or "").strip(),
        "lat":  o.get("lat"), "lon": o.get("lon"),
        "distance_m": d,
        "modality":   modality,
        "walk_min":   round(_walk_minutes(d)) if isinstance(d, (int, float)) else None,
    })
    if not r.get("name") or not _valid_latlon(r) or r.get("distance_m") is None:
        return None
    return r


def _shape_supermarket(o: dict) -> Optional[dict]:
    """Shape a supermarket feature. Data comes from OSM (Berlin has no BOD
    supermarket layer). Required: name, lat, lon, distance_m."""
    if not o:
        return None
    d = o.get("distance_m")
    t = o.get("tags") or {}
    r = _prune({
        "name": (o.get("name") or "").strip(),
        "lat":  o.get("lat"), "lon": o.get("lon"),
        "distance_m": d,
        "walk_min":   round(_walk_minutes(d)) if isinstance(d, (int, float)) else None,
        "brand":         (t.get("brand") or "").strip(),
        "opening_hours": (t.get("opening_hours") or "").strip(),
        "wheelchair":    True if t.get("wheelchair") == "yes" else None,
        "organic":       True if t.get("organic") == "yes" else None,
    })
    if not r.get("name") or not _valid_latlon(r) or r.get("distance_m") is None:
        return None
    return r


def _shape_osm_feature(o: dict) -> Optional[dict]:
    """Shape an OSM local snapshot entry into the newcomer feature dict.
    Items from OsmLocalCache.near() carry: lat, lon, name (optional), tags
    (dict), distance_m (added by .near()), source='osm'.  Required: lat,
    lon, distance_m — name falls back to the amenity tag."""
    t = o.get("tags") or {}
    name = (o.get("name") or t.get("name") or
            t.get("amenity") or t.get("shop") or
            t.get("office") or "").strip()
    d = o.get("distance_m")
    street = (t.get("addr:street") or "").strip()
    hnr    = (t.get("addr:housenumber") or "").strip()
    plz    = (t.get("addr:postcode") or "").strip()
    city   = (t.get("addr:city") or "").strip()
    addr_l = f"{street} {hnr}".strip()
    addr_r = f"{plz} {city}".strip()
    address = ", ".join(p for p in [addr_l, addr_r] if p)
    r = _prune({
        "name":       name,
        "lat":        o.get("lat"),
        "lon":        o.get("lon"),
        "distance_m": d,
        "address":    address,
        "phone":      (t.get("phone") or t.get("contact:phone") or "").strip(),
        "website":    (t.get("website") or t.get("contact:website") or "").strip(),
        "hours":      (t.get("opening_hours") or "").strip(),
        "walk_min":   round(_walk_minutes(d)) if isinstance(d, (int, float)) else None,
    })
    if not r.get("name") or not _valid_latlon(r) or r.get("distance_m") is None:
        return None
    return r


def _shape_refuge_quiet(q: dict, amber_quiet_m: int) -> list:
    """Return [feature] iff the quiet zone is within amber radius; else [].
    Refuge is composite (quiet zone OR tree crown) — a tile that went
    amber via TREES alone should NOT surface a distant quiet zone as a
    feature because the map pin would be misleading."""
    if not q or q.get("distance_m") is None:
        return []
    if q["distance_m"] > amber_quiet_m:
        return []
    r = _prune({
        "name": (q.get("name") or "").strip() or "Quiet zone",
        "lat":  q.get("lat"), "lon": q.get("lon"),
        "distance_m": q.get("distance_m"),
        "size_ha": q.get("size_ha"),
        "kind":    q.get("kind"),
    })
    if not _valid_latlon(r):
        return []
    return [r]


def _shape_refuge_trees(t: dict) -> dict:
    """Return trees summary for refuge tile's metadata. Passes through
    Index.trees_bbox keys, pruned. Returns {} if trees fetch failed
    (frontend hides the trees block when empty)."""
    if not t or t.get("error"):
        return {}
    top = t.get("top_species") or []
    return _prune({
        "count":               t.get("count"),
        "avg_age_yr":          t.get("avg_age_yr"),
        "tallest_m":           t.get("tallest_m"),
        "crown_coverage_pct":  t.get("crown_coverage_pct"),
        "top_species": [{"name": s.get("name"), "n": s.get("n")}
                        for s in top[:5] if s.get("name")],
    })


def _shape_gesix(cfg, index, lat: float, lon: float, *,
                 card_key: str = "gesix",
                 label: str = "Neighbourhood profile") -> dict:
    """Shape-only GESIx tile. No numeric on face.
    Face renders label + one-line hint; modal renders the 5-segment
    quintile bar (frontend responsibility). Metadata carries the raw
    GESIx attributes; the per-lens AI summariser consumes the tile
    tier + rule + numeric via /api/lens_insight.

    Used by all four Life Lenses — the caller controls `card_key` and
    `label` so the same helper serves gesix / gesix_newcomer /
    gesix_quiet / gesix_commuter tile keys.

    `cfg` is required so that `sources` resolves to the full licence text
    string from cfg.attribution rather than the bare dataset key "gesix".
    """
    g = index.gesix_at(lon, lat) if hasattr(index, "gesix_at") else None
    g = g or {}
    _q = g.get("quintile_5")
    if _q == 1 or _q == 2:
        tier = TIER_GREEN
    elif _q == 3:
        tier = TIER_AMBER
    elif _q == 4 or _q == 5:
        tier = TIER_RED
    else:
        tier = TIER_UNKNOWN
    return {
        "key":      card_key,
        "label":    label,
        "icon":     "gesix",
        "tier":     tier,
        "rule":     "socioeconomic band of this Planungsraum · tap for detail",
        "numeric":  "",
        "caveat":   "",
        "features": [],
        "metadata": {"gesix": g},
        "sources":  [s for s in [cfg.attribution.get("gesix")] if s],
    }


if __name__ == "__main__":
    assert _prune({"a": "x", "b": None, "c": "", "d": 0, "e": False, "f": [], "g": {}}) \
        == {"a": "x", "d": 0, "e": False, "f": [], "g": {}}

    assert _int_or_none("65") == 65
    assert _int_or_none(65) == 65
    assert _int_or_none(None) is None
    assert _int_or_none("") is None
    assert _int_or_none("abc") is None

    assert _valid_latlon({"lat": 52.5, "lon": 13.4}) is True
    assert _valid_latlon({"lat": 100.0, "lon": 13.4}) is False
    assert _valid_latlon({"lat": None, "lon": 13.4}) is False

    t = _tile("k", "L", "i", tier="green", rule="r")
    assert t["features"] == [] and t["sources"] == [] and "metadata" not in t
    t2 = _tile("k", "L", "i", tier="green", rule="r", metadata={"x": 1})
    assert t2["metadata"]["x"] == 1
    print("scoring.shape selfcheck OK")
