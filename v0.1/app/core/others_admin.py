"""Admin-offices bundle for the raw-view "Others" tab.

Replaces the Bureaucracy lens (removed): no tiers, no legends, no
threshold logic — just the five public-admin office cards
(buergeramt / finanzamt / standesamt / lea / arbeitsagentur) as
shaped features the SPA plots on a map.

Pure — no I/O. Reads preloaded Index state (Bezirksgrenzen,
Bürgerämter) and curated CityConfig directories (Finanzamt /
Standesamt / Arbeitsagentur / LEA). Deterministic; two identical
calls return equal dicts.

Response shape:

    {
      "tiles": [
        {"key": "buergeramt", "label": "Bürgeramt (Anmeldung)",
         "icon": "buergeramt", "features": [{"name", "lat", "lon",
         "distance_m", "address", "website"}, ...]},
        ...
      ],
      "provenance": "Bürgerämter — Berlin Open Data · dl-de/by-2-0 · ...",
    }

Frontend consumer: `renderOthers` in `web/static/app.js`. Only
`tiles[].key|label|icon|features` and `provenance` are used.
"""

from app.core.geo import haversine_m


def _with_distance(office: dict, lon: float, lat: float):
    """Return office dict with `distance_m` added. Used for the single-point
    LEA (cfg.lea_office doesn't come pre-decorated with distance)."""
    if not office or "lon" not in office or "lat" not in office:
        return None
    d = haversine_m(lon, lat, office["lon"], office["lat"])
    return {**office, "distance_m": round(d)}


def _shape_office(o: dict):
    """Shape a raw admin-office record into the response feature dict.
    Trimmed inline copy of the old `scorer._shape_office`, kept here so
    this module doesn't depend on `scorer` (which is the direction the
    scoring refactor is heading anyway).

    Returns None on missing required fields — callers filter."""
    if not o:
        return None
    d = o.get("distance_m")
    if not isinstance(d, (int, float)):
        return None
    name = (o.get("name") or "").strip()
    if not name:
        return None
    lat, lon = o.get("lat"), o.get("lon")
    if not (isinstance(lat, (int, float)) and isinstance(lon, (int, float))
            and -90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    r = {"name": name, "lat": lat, "lon": lon, "distance_m": d}
    addr = (o.get("address") or "").strip()
    if addr:
        r["address"] = addr
    web = (o.get("website") or "").strip()
    if web:
        r["website"] = web
    return r


def _provenance(cfg, keys):
    """Union of `cfg.attribution` strings for the given dataset keys,
    de-duped in insertion order and joined with ` · `. Empty strings are
    dropped so a missing attribution key doesn't leak an empty citation."""
    seen, out = set(), []
    for k in keys:
        s = cfg.attribution.get(k) or ""
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return " · ".join(out)


def _features_for(key: str, cfg, index, lon: float, lat: float) -> list:
    """Resolve the feature list for one admin-office card key. Each branch
    reads from the same source the old `bureaucracy_lens` used, so the
    Others tab sees identical data. Missing preload → empty list (not
    unknown-tier semantics)."""
    if key == "buergeramt":
        raw = index.buergeramt_near(lon, lat)
        return [f for f in (_shape_office(o) for o in raw) if f]
    if key == "finanzamt":
        o = index.finanzamt_nearest(lon, lat)
        shaped = _shape_office(o) if o else None
        return [shaped] if shaped else []
    if key == "standesamt":
        o = index.standesamt_for(lon, lat)         # None if outside Berlin
        shaped = _shape_office(o) if o else None
        return [shaped] if shaped else []
    if key == "lea":
        o = _with_distance(cfg.lea_office, lon, lat)
        shaped = _shape_office(o) if o else None
        return [shaped] if shaped else []
    if key == "arbeitsagentur":
        raw = index.arbeitsagentur_near(lon, lat)
        return [f for f in (_shape_office(o) for o in raw) if f]
    return []


# Attribution keys per admin-office card. Kept module-local so the
# provenance string is derived from the same table the response is built
# from — one place to edit when a new card lands.
_PROV_KEYS_BY_CARD = {
    "buergeramt":     ("buergeramt",),
    "finanzamt":      ("finanzamt",),
    "standesamt":     ("standesamt", "bezirksgrenzen"),
    "lea":            ("lea",),
    "arbeitsagentur": ("arbeitsagentur",),
}


def build(cfg, index, lon: float, lat: float) -> dict:
    """Assemble the Others tab admin-office bundle for one address.

    Iterates `cfg.others_admin_cards` (per-city ordered list of
    `OthersAdminCardConfig`); each entry contributes one tile. Tile
    order in the response matches config order — the frontend renders
    tiles in the same order they arrive.
    """
    tiles = []
    all_prov_keys = []
    for card in cfg.others_admin_cards:
        features = _features_for(card.key, cfg, index, lon, lat)
        tiles.append({
            "key":      card.key,
            "label":    card.label,
            "icon":     card.icon,
            "features": features,
        })
        # Only cite the attribution for a card if it produced at least one
        # feature — a card that drew nothing (e.g. Standesamt outside
        # Berlin) has nothing to attribute.
        if features:
            all_prov_keys.extend(_PROV_KEYS_BY_CARD.get(card.key, ()))
    return {
        "tiles":      tiles,
        "provenance": _provenance(cfg, all_prov_keys),
    }


if __name__ == "__main__":
    # -- _with_distance: happy path + guards --------------------------
    assert _with_distance({"lat": 52.5, "lon": 13.4, "name": "X"}, 13.4, 52.5)["distance_m"] == 0
    assert _with_distance(None, 0, 0) is None
    assert _with_distance({}, 0, 0) is None
    assert _with_distance({"lat": 52.5}, 0, 0) is None

    # -- _shape_office: happy + guards --------------------------------
    _off = {"name": "Bürgeramt X", "address": "Y-Str. 1, 10000 Berlin",
            "lat": 52.5, "lon": 13.4, "distance_m": 620,
            "website": "https://x.example/"}
    _s = _shape_office(_off)
    assert _s["distance_m"] == 620, _s
    assert "walk_min" not in _s, _s   # walk_min pruned; frontend renders km via fmtDistance
    assert _s["website"] == "https://x.example/"
    assert _s["address"] == "Y-Str. 1, 10000 Berlin"
    # Missing required fields → None
    assert _shape_office(None) is None
    assert _shape_office({"name": "X"}) is None                 # no distance
    assert _shape_office({"name": "", "lat": 52.5, "lon": 13.4, "distance_m": 100}) is None
    assert _shape_office({"name": "X", "lat": 100, "lon": 13.4, "distance_m": 100}) is None

    # -- _provenance: de-dup + insertion order ------------------------
    class _Cfg:
        attribution = {"a": "AAA", "b": "BBB", "c": "", "d": "AAA"}
    assert _provenance(_Cfg(), ["a", "b"]) == "AAA · BBB"
    assert _provenance(_Cfg(), ["a", "d", "b"]) == "AAA · BBB"    # d de-duped
    assert _provenance(_Cfg(), ["c"]) == ""                        # empty dropped
    assert _provenance(_Cfg(), ["missing"]) == ""

    # -- build(): tiles order, provenance, deterministic --------------
    from app.cities.berlin import BERLIN as _CFG

    class _StubIndex:
        def buergeramt_near(self, lon, lat, radius_m=3000):
            return [{"name": "BA-Test", "lat": 52.5, "lon": 13.4, "distance_m": 500,
                     "address": "A-Str. 1", "website": ""}]
        def arbeitsagentur_near(self, lon, lat, radius_m=5000):
            return [{"name": "AA-Test", "lat": 52.5, "lon": 13.4, "distance_m": 800}]
        def finanzamt_nearest(self, lon, lat):
            return {"name": "FA-Test", "lat": 52.5, "lon": 13.4, "distance_m": 600}
        def standesamt_for(self, lon, lat):
            return {"name": "Standesamt Pankow", "lat": 52.5, "lon": 13.4, "distance_m": 700}

    r_a = build(_CFG, _StubIndex(), 13.4, 52.5)
    r_b = build(_CFG, _StubIndex(), 13.4, 52.5)
    assert r_a == r_b, "build() must be deterministic"

    _keys = [t["key"] for t in r_a["tiles"]]
    assert _keys == [c.key for c in _CFG.others_admin_cards], _keys
    # Every tile has the four card fields — no tier/rule/numeric leakage.
    for t in r_a["tiles"]:
        assert set(t.keys()) == {"key", "label", "icon", "features"}, t

    _by = {t["key"]: t for t in r_a["tiles"]}
    assert len(_by["buergeramt"]["features"]) == 1
    assert _by["buergeramt"]["features"][0]["distance_m"] == 500
    assert len(_by["lea"]["features"]) == 1                     # from cfg.lea_office

    # Provenance concatenates non-empty attribution strings for cards that
    # actually produced features.
    assert "Bürgerämter" in r_a["provenance"], r_a["provenance"]

    # Standesamt outside Berlin → 0 features, no standesamt attribution.
    class _StubOutside(_StubIndex):
        def standesamt_for(self, lon, lat):
            return None
    r_out = build(_CFG, _StubOutside(), 13.4, 52.5)
    _by_out = {t["key"]: t for t in r_out["tiles"]}
    assert _by_out["standesamt"]["features"] == []

    # All-empty preload → tiles present but empty; provenance drops to
    # only whatever LEA (from cfg) still contributes.
    class _StubEmpty:
        def buergeramt_near(self, lon, lat, radius_m=3000): return []
        def arbeitsagentur_near(self, lon, lat, radius_m=5000): return []
        def finanzamt_nearest(self, lon, lat): return None
        def standesamt_for(self, lon, lat): return None
    r_e = build(_CFG, _StubEmpty(), 13.4, 52.5)
    _by_e = {t["key"]: t for t in r_e["tiles"]}
    assert _by_e["buergeramt"]["features"] == []
    assert _by_e["arbeitsagentur"]["features"] == []
    assert _by_e["finanzamt"]["features"] == []
    assert _by_e["standesamt"]["features"] == []
    # LEA feature still present — comes from cfg.lea_office, not index.
    assert len(_by_e["lea"]["features"]) == 1

    print("others_admin.py selfcheck OK")
