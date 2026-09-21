"""Commuter lens composer.

Pure — no I/O on the hot path. Reads only pre-loaded Index state and
the OSM local snapshot.

Config-driven dispatch: tile presence is gated on the city's LensConfig
tile set. Berlin-only tiles (commuter_tram_transit, gesix_commuter) are
conditionally included only when they appear in cfg.commuter_lens.tiles.
Hamburg-only tiles (commuter_ferry_transit, sozialmonitoring_status_commuter,
sozialmonitoring_gesamt_commuter) are included when they appear.
Fixes PR #81 Critical: commuter_lens(HAMBURG, ...) previously threw
KeyError on commuter_tram_transit.

Nine Berlin tiles in fixed order:

    commuter_rail_transit, commuter_tram_transit,
    commuter_bus_transit, regional_rail_reach,
    cycling_network, car_sharing_reach, ev_charging_reach,
    airport_reach, gesix_commuter

Eleven Hamburg tiles in fixed order:

    commuter_rail_transit, commuter_ferry_transit,
    commuter_bus_transit, regional_rail_reach,
    cycling_network, parkzone, car_sharing_reach, ev_charging_reach,
    airport_reach, sozialmonitoring_status_commuter,
    sozialmonitoring_gesamt_commuter

Reuse:
- Rail / tram / bus data come from the same Index fields the Newcomer
  lens uses (`sbahn`, `ubahn`, `tram`, plus the OSM `transit` bucket for
  bus). The tile KEYS are commuter-specific so the AI-insight prompts
  can frame each mode as a daily commute rather than a first-90-days
  Anmeldung reach.
- `regional_rail_reach` reads the curated `Index.regional_rail` list
  (already wired for the raw-view connectivity card).
- `airport_reach` reads `cfg.airport` (already wired).

New buckets (added to `refresh_osm_amenities.py` in this same PR):
- `cycling`      — highway=cycleway on ways (centroid-per-way).
- `car_sharing`  — amenity=car_sharing on nodes.

When the local snapshot pre-dates this code (fresh code / stale
snapshot combination), the composer passes `bucket_missing=True` on
the tile thresholds and the tier func reports `unknown` rather than
red. The next weekly OSM refresh populates the bucket automatically.
"""

from app.core.geo import haversine_m
from app.core.scoring.legends import _legend_for
from app.core.scoring.provenance import _lens_provenance, _sources_for
from app.core.scoring.shape import _shape_gesix, _shape_osm_feature
from app.core.scoring.tiers import (
    _tier_airport_reach, _tier_car_sharing_reach, _tier_commuter_bus_transit,
    _tier_commuter_tram_transit, _tier_cycling_network,
    _tier_distance_ladder, _tier_ev_charging_reach, _tier_ferry_transit,
    _tier_parkzone, _tier_rail_transit, _tier_regional_rail_reach,
    _tier_sozialmonitoring_gesamt, _tier_sozialmonitoring_status,
)


def commuter_lens(cfg, index, lon: float, lat: float, *,
                  amenities: dict | None = None) -> dict:
    """Assemble the Commuter lens for one address.

    Tile presence is driven by cfg.commuter_lens.tiles — Berlin and Hamburg
    carry different sets. Each pre-fetch, tier call, feat_map entry, and
    results entry is guarded by `if key in th` so adding or removing a tile
    from the city config is the only change needed. No KeyError on Hamburg.
    """
    assert -60 <= lat <= 60, f"lat out of range: {lat}"
    assert -180 <= lon <= 180, f"lon out of range: {lon}"
    lens = cfg.commuter_lens
    th        = {t.key: t.thresholds for t in lens.tiles}
    tile_meta = {t.key: (t.label, t.icon, t.caveat) for t in lens.tiles}

    # -- Rail (S+U) — reuse Newcomer's cluster-and-tag pattern -------------
    # ponytail: same _cluster_by_base logic could be lifted onto Index once
    # a third lens needs it; today only the Newcomer + Commuter lenses do.
    from app.core.lenses.newcomer import _cluster_by_base

    rail_feats = []
    if "commuter_rail_transit" in th:
        _rail_cap = th["commuter_rail_transit"]["any_rail_m"] * 2
        _rail_raw = []
        for mode_tag, points in (("S", index.sbahn), ("U", index.ubahn)):
            for p in points:
                d = haversine_m(lon, lat, p["lon"], p["lat"])
                if d <= _rail_cap:
                    _rail_raw.append({**p, "distance_m": round(d), "mode": mode_tag})
        _rail_raw.sort(key=lambda x: x["distance_m"])
        rail_feats = _cluster_by_base(_rail_raw)

    # -- Tram from the preloaded VBB list (Berlin only) -------------------
    tram_feats = []
    if "commuter_tram_transit" in th:
        _tram_cap = th["commuter_tram_transit"]["amber_m"] * 2
        _tram_raw = []
        for p in index.tram:
            d = haversine_m(lon, lat, p["lon"], p["lat"])
            if d <= _tram_cap:
                _tram_raw.append({**p, "distance_m": round(d), "mode": "T"})
        _tram_raw.sort(key=lambda x: x["distance_m"])
        tram_feats = _cluster_by_base(_tram_raw)

    # -- Ferry from the preloaded HADAG piers (Hamburg only) --------------
    ferry_feats = []
    if "commuter_ferry_transit" in th:
        _ferry_cap = th["commuter_ferry_transit"]["amber_m"] * 2
        _ferry_raw = []
        for p in (index.ferry if hasattr(index, "ferry") else []):
            d = haversine_m(lon, lat, p["lon"], p["lat"])
            if d <= _ferry_cap:
                _ferry_raw.append({**p, "distance_m": round(d), "mode": "F"})
        _ferry_raw.sort(key=lambda x: x["distance_m"])
        ferry_feats = _cluster_by_base(_ferry_raw)

    # -- Bus from the OSM `transit` bucket in amenities -------------------
    _tr_block = (amenities or {}).get("transit") or {}
    _tr_items = _tr_block.get("items") or []
    _bus_items = [it for it in _tr_items
                  if (it.get("tags") or {}).get("bus") == "yes"
                  or (it.get("tags") or {}).get("highway") == "bus_stop"]
    _bus_items.sort(key=lambda x: x.get("distance_m", 10**9))
    bus_feats = []
    for it in _bus_items:
        d = it.get("distance_m")
        name = (it.get("name") or "").strip()
        if d is None or not name:
            continue
        bus_feats.append({"name": name,
                          "lat": it.get("lat"), "lon": it.get("lon"),
                          "distance_m": round(d)})

    # -- Regional rail — curated list already carries lat/lon -------------
    _regional = []
    for st in index.regional_rail:
        d = haversine_m(lon, lat, st["lon"], st["lat"])
        _regional.append({**st, "distance_m": round(d)})
    _regional.sort(key=lambda x: x["distance_m"])
    regional_feats = _regional[:5]

    # -- OSM local snapshot buckets ---------------------------------------
    oc = getattr(index, "osm_local", None)

    def _osm_near(bucket: str, radius_m: int) -> list:
        if oc is None:
            return []
        return oc.near(bucket, lon, lat, radius_m) or []

    # Detect stale-snapshot case: bucket missing entirely vs bucket present
    # but empty at this location. `bucket_missing=True` short-circuits the
    # tier func to `unknown`.
    def _has_bucket(name: str) -> bool:
        if oc is None:
            return False
        try:
            return name in oc.buckets
        except Exception:
            return False

    _cycling_missing  = not _has_bucket("cycling")  if "cycling_network"   in th else False
    _carshare_missing = not _has_bucket("car_sharing") if "car_sharing_reach" in th else False

    _cycling_raw  = _osm_near("cycling",     th["cycling_network"]["amber_m"] + 200)   if "cycling_network"   in th else []
    _carshare_raw = _osm_near("car_sharing", th["car_sharing_reach"]["radius_m"])      if "car_sharing_reach" in th else []
    _ev_raw       = _osm_near("ev_charging", th["ev_charging_reach"]["radius_m"])      if "ev_charging_reach" in th else []

    # `highway=cycleway` ways almost never carry a `name=` tag, so
    # `_shape_osm_feature` (which drops empty-name rows to avoid ghost
    # amenities on the map) would collapse every cycling row and turn a
    # dense cycleway grid into a false RED tier. Cycleways are UNNAMED
    # linear infrastructure — the presence of an anonymous way at short
    # distance IS the signal. Inline a minimal shape that keeps the row
    # and synthesises a stable label for the numeric readout.
    cycling_feats = []
    for _o in _cycling_raw:
        _d = _o.get("distance_m")
        _la = _o.get("lat")
        _lo = _o.get("lon")
        if _d is None or _la is None or _lo is None:
            continue
        cycling_feats.append({
            "name":       (_o.get("name") or "Cycleway").strip(),
            "lat":        _la, "lon": _lo,
            "distance_m": _d,
        })
    cycling_feats.sort(key=lambda x: x["distance_m"])

    carshare_feats = [f for f in (_shape_osm_feature(o) for o in _carshare_raw) if f]
    ev_feats       = [f for f in (_shape_osm_feature(o) for o in _ev_raw) if f]

    # -- Parking zone: point-in-polygon (present in both Berlin and Hamburg) --
    parkzone_info = index.parking_zone_at(lon, lat) if "parkzone" in th else None

    # -- Airport reach (single-point distance) ----------------------------
    airport = None
    _cfg_airport = getattr(cfg, "airport", None)
    if _cfg_airport and "lat" in _cfg_airport and "lon" in _cfg_airport:
        d = haversine_m(lon, lat, _cfg_airport["lon"], _cfg_airport["lat"])
        airport = {**_cfg_airport, "distance_m": round(d)}

    # -- Sozialmonitoring (Hamburg only) — single lookup shared by two tiles --
    sm = None
    if "sozialmonitoring_status_commuter" in th or "sozialmonitoring_gesamt_commuter" in th:
        sm = index.sozialmonitoring_at(lon, lat) if hasattr(index, "sozialmonitoring_at") else None

    # -- Tier computations ------------------------------------------------
    # `bucket_missing` flag is threaded into the tier func via the
    # thresholds dict so a stale OSM snapshot cleanly resolves to
    # `unknown` rather than a false red.
    _th_cycling  = ({**th["cycling_network"],   "bucket_missing": _cycling_missing}
                    if "cycling_network"   in th else {})
    _th_carshare = ({**th["car_sharing_reach"], "bucket_missing": _carshare_missing}
                    if "car_sharing_reach" in th else {})

    results = []
    if "commuter_rail_transit"           in th: results.append(("commuter_rail_transit",           _tier_rail_transit(rail_feats,     th["commuter_rail_transit"])))
    if "commuter_ferry_transit"          in th: results.append(("commuter_ferry_transit",          _tier_ferry_transit(ferry_feats,   th["commuter_ferry_transit"])))
    if "commuter_tram_transit"           in th: results.append(("commuter_tram_transit",           _tier_commuter_tram_transit(tram_feats, th["commuter_tram_transit"])))
    if "commuter_bus_transit"            in th: results.append(("commuter_bus_transit",            _tier_commuter_bus_transit(bus_feats, th["commuter_bus_transit"])))
    if "regional_rail_reach"             in th: results.append(("regional_rail_reach",             _tier_regional_rail_reach(regional_feats, th["regional_rail_reach"])))
    if "cycling_network"                 in th: results.append(("cycling_network",                 _tier_cycling_network(cycling_feats, _th_cycling)))
    if "parkzone"                        in th: results.append(("parkzone",                        _tier_parkzone(parkzone_info, th["parkzone"])))
    if "car_sharing_reach"               in th: results.append(("car_sharing_reach",               _tier_car_sharing_reach(carshare_feats, _th_carshare)))
    if "ev_charging_reach"               in th: results.append(("ev_charging_reach",               _tier_ev_charging_reach(ev_feats, th["ev_charging_reach"])))
    if "airport_reach"                   in th: results.append(("airport_reach",                   _tier_airport_reach(airport, th["airport_reach"])))
    if "sozialmonitoring_status_commuter" in th: results.append(("sozialmonitoring_status_commuter", _tier_sozialmonitoring_status(sm, th["sozialmonitoring_status_commuter"])))
    if "sozialmonitoring_gesamt_commuter" in th: results.append(("sozialmonitoring_gesamt_commuter", _tier_sozialmonitoring_gesamt(sm, th["sozialmonitoring_gesamt_commuter"])))

    # -- Feature payloads + metadata per tile -----------------------------
    from app.core.scoring.constants import _walk_minutes
    feat_map: dict = {}
    if "commuter_rail_transit" in th:
        feat_map["commuter_rail_transit"] = [{
            "name": f["name"], "lat": f["lat"], "lon": f["lon"],
            "distance_m": f["distance_m"], "mode": f.get("mode", ""),
            "walk_min": round(_walk_minutes(f["distance_m"])),
            "directions": f.get("directions", []),
        } for f in rail_feats[:10]]
    if "commuter_ferry_transit" in th:
        feat_map["commuter_ferry_transit"] = [{
            "name": f["name"], "lat": f["lat"], "lon": f["lon"],
            "distance_m": f["distance_m"], "mode": "F",
            "walk_min": round(_walk_minutes(f["distance_m"])),
            "lines": f.get("lines", ""),
        } for f in ferry_feats[:10]]
    if "commuter_tram_transit" in th:
        feat_map["commuter_tram_transit"] = [{
            "name": f["name"], "lat": f["lat"], "lon": f["lon"],
            "distance_m": f["distance_m"], "mode": "T",
            "walk_min": round(_walk_minutes(f["distance_m"])),
            "directions": f.get("directions", []),
        } for f in tram_feats[:10]]
    if "commuter_bus_transit" in th:
        feat_map["commuter_bus_transit"] = [{
            "name": f["name"], "lat": f["lat"], "lon": f["lon"],
            "distance_m": f["distance_m"], "mode": "B",
            "walk_min": round(_walk_minutes(f["distance_m"])),
        } for f in bus_feats[:10]]
    if "regional_rail_reach"  in th: feat_map["regional_rail_reach"]  = regional_feats
    if "cycling_network"      in th: feat_map["cycling_network"]      = cycling_feats[:10]
    if "parkzone"             in th: feat_map["parkzone"]             = []
    if "car_sharing_reach"    in th: feat_map["car_sharing_reach"]    = carshare_feats[:10]
    if "ev_charging_reach"    in th: feat_map["ev_charging_reach"]    = ev_feats[:10]
    if "airport_reach"        in th: feat_map["airport_reach"]        = []
    if "sozialmonitoring_status_commuter" in th: feat_map["sozialmonitoring_status_commuter"] = []
    if "sozialmonitoring_gesamt_commuter" in th: feat_map["sozialmonitoring_gesamt_commuter"] = []

    metadata_map: dict = {}
    if "airport_reach" in th:
        metadata_map["airport_reach"] = {"airport": airport}
    # Report bucket-missing state in metadata so the frontend can
    # optionally hint at a stale snapshot on the modal Readout.
    if "cycling_network"   in th: metadata_map["cycling_network"]   = {"bucket_missing": _cycling_missing}
    if "car_sharing_reach" in th: metadata_map["car_sharing_reach"] = {"bucket_missing": _carshare_missing}
    if "parkzone" in th and parkzone_info is not None:
        metadata_map["parkzone"] = {"parkzone": parkzone_info}
    if sm:
        if "sozialmonitoring_status_commuter" in th:
            metadata_map["sozialmonitoring_status_commuter"] = {"sozialmonitoring": sm}
        if "sozialmonitoring_gesamt_commuter" in th:
            metadata_map["sozialmonitoring_gesamt_commuter"] = {"sozialmonitoring": sm}

    tiles = []
    for key, res in results:
        label, icon, caveat = tile_meta[key]
        tile = {
            "key":      key,
            "label":    label,
            "icon":     icon,
            "tier":     res["tier"],
            "rule":     res["rule"],
            "numeric":  res["numeric"],
            "caveat":   caveat,
            "features": feat_map.get(key, []),
            "sources":  _sources_for(cfg, key, res["tier"]),
            "legend":   _legend_for(key, th.get(key, {}) or {}),
        }
        if key in metadata_map:
            tile["metadata"] = metadata_map[key]
        tiles.append(tile)

    # gesix_commuter — Berlin only (Hamburg has no GESIx; guarded by tile key presence)
    if "gesix_commuter" in th:
        tiles.append(_shape_gesix(cfg, index, lat, lon,
                                  card_key="gesix_commuter",
                                  label=tile_meta["gesix_commuter"][0]))

    return {
        "slug":       lens.slug,
        "label":      lens.label,
        "audience":   lens.audience_hint,
        "tiles":      tiles,
        "provenance": _lens_provenance(cfg, tiles),
    }
