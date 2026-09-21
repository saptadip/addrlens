"""Newcomer lens composer (Spec E).

Pure — reads only pre-loaded Index state, no live fetch on hot path.
Each tier function is a small pure translation from feature list +
thresholds to a tier dict; this composer wraps each in the Spec D
tile shape and resolves provenance strings from cfg.attribution.

Config-driven dispatch: tile presence is gated on the city's LensConfig
tile set. Berlin-only tiles (buergeramt, xmas_market, wochenmarkt,
tram_transit, gesix_newcomer) are conditionally included only when they
appear in cfg.newcomer_lens.tiles. Hamburg-only tiles (ferry_transit,
sozialmonitoring_status, sozialmonitoring_gesamt) are included when they
appear. Fixes PR #81 Critical: newcomer_lens(HAMBURG, ...) previously
threw KeyError on Berlin-only tile keys.
"""

from app.core.geo import haversine_m
from app.core.scoring.constants import _walk_minutes
from app.core.scoring.legends import _legend_for
from app.core.scoring.provenance import _lens_provenance, _sources_for
from app.core.scoring.shape import (
    _shape_gesix, _shape_office, _shape_osm_feature,
)
from app.core.scoring.tiers import (
    _tier_buergeramt_newcomer, _tier_bus_transit, _tier_coworking,
    _tier_english_clinic, _tier_ferry_transit, _tier_intl_food,
    _tier_language_school, _tier_library, _tier_nightlife_density,
    _tier_packstation, _tier_parkzone, _tier_rail_transit,
    _tier_sozialmonitoring_gesamt, _tier_sozialmonitoring_status,
    _tier_tram_transit, _tier_wochenmarkt, _tier_xmas_market,
)


def _cluster_by_base(raw: list) -> list:
    """Dedup platform pairs sharing a station name. Two effects to
    collapse: (a) VBB / BOD tram stores each direction as its own
    point ("Freienwalder Str. -> Stadt" / "-> Land"); (b) at S+U
    hubs (S+U Hermannstr., S+U Alexanderplatz…) VBB stores S-Bahn
    and U-Bahn platforms as separate points with identical base
    names. Cluster by base_name only. Keep nearest hit; join
    distinct modes with "," so the SPA can map to labels; union
    the direction suffixes."""
    clusters: dict = {}
    for p in raw:
        base, _sep, direction = p["name"].partition(" -> ")
        base = base.strip()
        direction = direction.strip()
        entry = clusters.get(base)
        if entry is None:
            entry = {**p, "name": base, "directions": []}
            clusters[base] = entry
        existing_modes = entry.get("mode", "").split(",")
        if p.get("mode") and p["mode"] not in existing_modes:
            entry["mode"] = ",".join(
                [m for m in existing_modes if m] + [p["mode"]])
        if direction and direction not in entry["directions"]:
            entry["directions"].append(direction)
    return sorted(clusters.values(), key=lambda x: x["distance_m"])


def newcomer_lens(cfg, index, lon: float, lat: float, *,
                  amenities: dict | None = None) -> dict:
    """Assemble the Newcomer lens block for one address.

    Args follow the project-wide (lon, lat) convention — same as
    young_family_lens.

    Tile presence is driven by cfg.newcomer_lens.tiles — Berlin and Hamburg
    carry different sets. Each pre-fetch, tier call, feat_map entry, and
    results entry is guarded by `if key in th` so adding or removing a tile
    from the city config is the only change needed. No KeyError on Hamburg.

    `amenities` is the OSM buckets dict from amenities_near() — only the
    "transit" bucket is consumed here (nearest bus-tagged stop for the
    bus_transit tile). Passed as kwarg so tests can call this without
    an amenities snapshot.
    """
    assert -60 <= lat <= 60, f"lat out of range: {lat}"
    assert -180 <= lon <= 180, f"lon out of range: {lon}"
    lens = cfg.newcomer_lens
    th        = {t.key: t.thresholds for t in lens.tiles}
    tile_meta = {t.key: (t.label, t.icon, t.caveat) for t in lens.tiles}

    # -- Bürgeramt: BOD-first (preloaded via buergeramt_near) --------------
    buergeramt_feats = []
    if "buergeramt" in th:
        buergeramt_raw  = index.buergeramt_near(lon, lat, 5000)
        buergeramt_feats = [f for f in (_shape_office(o) for o in buergeramt_raw) if f]

    # -- Christmas markets: Senate live GeoJSON preloaded at boot ---------
    xmas_market_feats = []
    if "xmas_market" in th:
        xmas_market_feats = index.xmas_market_near(
            lon, lat, th["xmas_market"]["radius_m"])

    # -- Parking zone: point-in-polygon (both Berlin and Hamburg) ----------
    parkzone_info = index.parking_zone_at(lon, lat) if "parkzone" in th else None

    # -- Rail (S+U) from preloaded VBB+BOD lists ---------------------------
    # ponytail: No vbb_query() method exists; access per-modality lists
    # directly. Upgrade path: extract vbb_query() on Index when a third
    # lens needs S/U unified access.
    rail_feats = []
    if "rail_transit" in th:
        _rail_raw = []
        _rail_cap = th["rail_transit"]["any_rail_m"] * 2  # wide pre-filter
        for mode_tag, points in (("S", index.sbahn), ("U", index.ubahn)):
            for p in points:
                d = haversine_m(lon, lat, p["lon"], p["lat"])
                if d <= _rail_cap:
                    _rail_raw.append({**p, "distance_m": round(d), "mode": mode_tag})
        _rail_raw.sort(key=lambda x: x["distance_m"])
        rail_feats = _cluster_by_base(_rail_raw)

    # -- Tram from preloaded VBB tram list (Berlin only) -------------------
    tram_feats = []
    if "tram_transit" in th:
        _tram_raw = []
        _tram_cap = th["tram_transit"]["amber_m"] * 2  # wide pre-filter
        for p in index.tram:
            d = haversine_m(lon, lat, p["lon"], p["lat"])
            if d <= _tram_cap:
                _tram_raw.append({**p, "distance_m": round(d), "mode": "T"})
        _tram_raw.sort(key=lambda x: x["distance_m"])
        tram_feats = _cluster_by_base(_tram_raw)

    # -- Ferry from preloaded HADAG piers (Hamburg only) -------------------
    ferry_feats = []
    if "ferry_transit" in th:
        _ferry_raw = []
        _ferry_cap = th["ferry_transit"]["amber_m"] * 2  # wide pre-filter
        for p in (index.ferry if hasattr(index, "ferry") else []):
            d = haversine_m(lon, lat, p["lon"], p["lat"])
            if d <= _ferry_cap:
                _ferry_raw.append({**p, "distance_m": round(d), "mode": "F"})
        _ferry_raw.sort(key=lambda x: x["distance_m"])
        ferry_feats = _cluster_by_base(_ferry_raw)

    # -- Bus from OSM `transit` bucket (bus-tagged only) -------------------
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

    # -- OSM local buckets: intl_food, coworking, english_clinic, others ---
    oc = getattr(index, "osm_local", None)

    def _osm_near(bucket: str, radius_m: int) -> list:
        if oc is None:
            return []
        return oc.near(bucket, lon, lat, radius_m)

    intl_food_raw        = _osm_near("intl_food",       th["intl_food"]["radius_m"])       if "intl_food"       in th else []
    coworking_raw        = _osm_near("coworking",       th["coworking"]["radius_m"])        if "coworking"       in th else []
    english_clinic_raw   = _osm_near("english_clinic",  3500)                               if "english_clinic"  in th else []
    language_school_raw  = _osm_near("language_school", th["language_school"]["amber_m"] + 1500) if "language_school" in th else []
    library_raw          = _osm_near("library",         th["library"]["amber_m"] + 1500)    if "library"         in th else []
    packstation_raw      = _osm_near("packstation",     th["packstation"]["amber_m"] + 500) if "packstation"     in th else []
    wochenmarkt_raw      = _osm_near("wochenmarkt",     th["wochenmarkt"]["amber_m"] + 1000) if "wochenmarkt"    in th else []
    nightlife_raw        = _osm_near("nightlife",       1000)                               if "nightlife_density" in th else []

    intl_food_feats       = [f for f in (_shape_osm_feature(o) for o in intl_food_raw)       if f]
    coworking_feats       = [f for f in (_shape_osm_feature(o) for o in coworking_raw)       if f]
    english_clinic_feats  = [f for f in (_shape_osm_feature(o) for o in english_clinic_raw)  if f]
    language_school_feats = [f for f in (_shape_osm_feature(o) for o in language_school_raw) if f]
    library_feats         = [f for f in (_shape_osm_feature(o) for o in library_raw)         if f]
    packstation_feats     = [f for f in (_shape_osm_feature(o) for o in packstation_raw)     if f]
    wochenmarkt_feats     = [f for f in (_shape_osm_feature(o) for o in wochenmarkt_raw)     if f]
    nightlife_feats       = [f for f in (_shape_osm_feature(o) for o in nightlife_raw)       if f]

    # -- Sozialmonitoring (Hamburg only) — single lookup shared by two tiles --
    sm = None
    if "sozialmonitoring_status" in th or "sozialmonitoring_gesamt" in th:
        sm = index.sozialmonitoring_at(lon, lat) if hasattr(index, "sozialmonitoring_at") else None

    # -- Build results list conditionally (only tiles in this city's config) --
    results = []
    if "buergeramt"            in th: results.append(("buergeramt",           _tier_buergeramt_newcomer(buergeramt_feats,   th["buergeramt"])))
    if "rail_transit"          in th: results.append(("rail_transit",         _tier_rail_transit(rail_feats,                th["rail_transit"])))
    if "ferry_transit"         in th: results.append(("ferry_transit",        _tier_ferry_transit(ferry_feats,              th["ferry_transit"])))
    if "tram_transit"          in th: results.append(("tram_transit",         _tier_tram_transit(tram_feats,                th["tram_transit"])))
    if "bus_transit"           in th: results.append(("bus_transit",          _tier_bus_transit(bus_feats,                  th["bus_transit"])))
    if "intl_food"             in th: results.append(("intl_food",            _tier_intl_food(intl_food_feats,              th["intl_food"])))
    if "coworking"             in th: results.append(("coworking",            _tier_coworking(coworking_feats,              th["coworking"])))
    if "english_clinic"        in th: results.append(("english_clinic",       _tier_english_clinic(english_clinic_feats,    th["english_clinic"])))
    if "language_school"       in th: results.append(("language_school",      _tier_language_school(language_school_feats,  th["language_school"])))
    if "library"               in th: results.append(("library",              _tier_library(library_feats,                  th["library"])))
    if "packstation"           in th: results.append(("packstation",          _tier_packstation(packstation_feats,           th["packstation"])))
    if "parkzone"              in th: results.append(("parkzone",             _tier_parkzone(parkzone_info,                  th["parkzone"])))
    if "wochenmarkt"           in th: results.append(("wochenmarkt",          _tier_wochenmarkt(wochenmarkt_feats,           th["wochenmarkt"])))
    if "xmas_market"           in th: results.append(("xmas_market",          _tier_xmas_market(xmas_market_feats,          th["xmas_market"])))
    if "nightlife_density"     in th: results.append(("nightlife_density",    _tier_nightlife_density(nightlife_feats,       th["nightlife_density"])))
    if "sozialmonitoring_status"  in th: results.append(("sozialmonitoring_status",  _tier_sozialmonitoring_status(sm,  th["sozialmonitoring_status"])))
    if "sozialmonitoring_gesamt"  in th: results.append(("sozialmonitoring_gesamt",  _tier_sozialmonitoring_gesamt(sm,  th["sozialmonitoring_gesamt"])))

    # -- Feature payloads per tile -------------------------------------------
    feat_map: dict = {}
    if "buergeramt" in th:
        feat_map["buergeramt"] = buergeramt_feats
    if "rail_transit" in th:
        feat_map["rail_transit"] = [{"name": f["name"], "lat": f["lat"], "lon": f["lon"],
                                     "distance_m": f["distance_m"], "mode": f["mode"],
                                     "walk_min": round(_walk_minutes(f["distance_m"])),
                                     "directions": f.get("directions", [])}
                                    for f in rail_feats[:10]]
    if "ferry_transit" in th:
        feat_map["ferry_transit"] = [{"name": f["name"], "lat": f["lat"], "lon": f["lon"],
                                      "distance_m": f["distance_m"], "mode": "F",
                                      "walk_min": round(_walk_minutes(f["distance_m"])),
                                      "lines": f.get("lines", "")}
                                     for f in ferry_feats[:10]]
    if "tram_transit" in th:
        feat_map["tram_transit"] = [{"name": f["name"], "lat": f["lat"], "lon": f["lon"],
                                     "distance_m": f["distance_m"], "mode": "T",
                                     "walk_min": round(_walk_minutes(f["distance_m"])),
                                     "directions": f.get("directions", [])}
                                    for f in tram_feats[:10]]
    if "bus_transit" in th:
        feat_map["bus_transit"] = [{"name": f["name"], "lat": f["lat"], "lon": f["lon"],
                                    "distance_m": f["distance_m"], "mode": "B",
                                    "walk_min": round(_walk_minutes(f["distance_m"]))}
                                   for f in bus_feats[:10]]
    if "intl_food"         in th: feat_map["intl_food"]       = intl_food_feats[:10]
    if "coworking"         in th: feat_map["coworking"]       = coworking_feats[:10]
    if "english_clinic"    in th: feat_map["english_clinic"]  = english_clinic_feats[:10]
    if "language_school"   in th: feat_map["language_school"] = language_school_feats[:10]
    if "library"           in th: feat_map["library"]         = library_feats[:10]
    if "packstation"       in th: feat_map["packstation"]     = packstation_feats[:10]
    if "parkzone"          in th: feat_map["parkzone"]        = []
    if "wochenmarkt"       in th: feat_map["wochenmarkt"]     = wochenmarkt_feats[:10]
    if "xmas_market"       in th: feat_map["xmas_market"]     = xmas_market_feats[:10]
    if "nightlife_density" in th: feat_map["nightlife_density"] = nightlife_feats[:10]
    if "sozialmonitoring_status"  in th: feat_map["sozialmonitoring_status"]  = []
    if "sozialmonitoring_gesamt"  in th: feat_map["sozialmonitoring_gesamt"]  = []

    tiles = []
    for key, res in results:
        label, icon, caveat = tile_meta[key]
        # Numeric-only tiles are tier=UNKNOWN by design; _sources_for()
        # returns [] for unknown, which would drop the OSM attribution for
        # a count that IS a real fact. Override for these keys so the
        # citation still renders.
        if key == "nightlife_density":
            sources = ["© OpenStreetMap contributors (ODbL) via Geofabrik"]
        else:
            sources = _sources_for(cfg, key, res["tier"])
        tile = {
            "key":      key,
            "label":    label,
            "icon":     icon,
            "tier":     res["tier"],
            "rule":     res["rule"],
            "numeric":  res["numeric"],
            "caveat":   caveat,
            "features": feat_map.get(key, []),
            "sources":  sources,
            "legend":   _legend_for(key, th.get(key, {}) or {}),
        }
        # Per-source freshness metadata — currently emitted only for
        # tiles whose upstream dataset self-publishes a refresh signal
        # our loader can read (xmas_market → Senate ETag date). Falls
        # back to boot-cache time when the upstream date is unknown.
        # ponytail: generalise across all tiles once a broader
        # attribution_dates map lands on CityConfig.
        # Attach the full parkzone info dict as tile metadata so the
        # frontend modal can render fee / hours / bemerkung without
        # roundtripping to a separate endpoint.
        if key == "parkzone" and parkzone_info is not None:
            tile["metadata"] = {"parkzone": parkzone_info}
        if key == "xmas_market" and sources:
            upstream = getattr(index, "xmas_market_upstream_refreshed_on", "")
            if upstream:
                fresh = {"label": "Source refreshed", "value": upstream}
            else:
                fresh = {"label": "Cached at server boot",
                         "value": getattr(index, "boot_time_utc", "")}
            # Skip the whole row when we have neither a real upstream
            # date nor a boot timestamp (e.g. scorer stubs without
            # `boot_time_utc`) — an empty value would render as
            # "Cached at server boot: " with a trailing colon.
            if fresh["value"]:
                tile["source_dates"] = [{"source": sources[0], **fresh}]
        # Sozialmonitoring tiles carry the raw sm dict in metadata so the
        # frontend modal can display stadtteil / statgeb / berichtsjahr.
        if key in ("sozialmonitoring_status", "sozialmonitoring_gesamt") and sm:
            tile["metadata"] = {"sozialmonitoring": sm}
        tiles.append(tile)

    # gesix_newcomer — Berlin only (Hamburg has no GESIx; guarded by tile key presence)
    if "gesix_newcomer" in th:
        tiles.append(_shape_gesix(cfg, index, lat, lon, card_key="gesix_newcomer",
                                  label=tile_meta["gesix_newcomer"][0]))

    return {
        "slug":       lens.slug,
        "label":      lens.label,
        "audience":   lens.audience_hint,
        "tiles":      tiles,
        "provenance": _lens_provenance(cfg, tiles),
    }
