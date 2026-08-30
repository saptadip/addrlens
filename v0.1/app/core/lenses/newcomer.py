"""Newcomer lens composer (Spec E).

Pure — reads only pre-loaded Index state, no live fetch on hot path.
Each tier function is a small pure translation from feature list +
thresholds to a tier dict; this composer wraps each in the Spec D
tile shape and resolves provenance strings from cfg.attribution.
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
    _tier_english_clinic, _tier_intl_food, _tier_language_school,
    _tier_library, _tier_nightlife_density, _tier_packstation,
    _tier_rail_transit, _tier_tram_transit, _tier_wochenmarkt,
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

    Tile order (fixed): buergeramt, rail_transit, tram_transit,
    bus_transit, intl_food, coworking, english_clinic, language_school,
    library, packstation, wochenmarkt, nightlife_density, gesix_newcomer.

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
    buergeramt_raw   = index.buergeramt_near(lon, lat, 5000)
    buergeramt_feats = [f for f in (_shape_office(o) for o in buergeramt_raw) if f]

    # -- Rail (S+U) from preloaded VBB+BOD lists ---------------------------
    # ponytail: No vbb_query() method exists; access per-modality lists
    # directly. Upgrade path: extract vbb_query() on Index when a third
    # lens needs S/U unified access.
    _rail_raw = []
    _rail_cap = th["rail_transit"]["any_rail_m"] * 2  # wide pre-filter
    for mode_tag, points in (("S", index.sbahn), ("U", index.ubahn)):
        for p in points:
            d = haversine_m(lon, lat, p["lon"], p["lat"])
            if d <= _rail_cap:
                _rail_raw.append({**p, "distance_m": round(d), "mode": mode_tag})
    _rail_raw.sort(key=lambda x: x["distance_m"])
    rail_feats = _cluster_by_base(_rail_raw)

    # -- Tram from preloaded VBB tram list ---------------------------------
    _tram_raw = []
    _tram_cap = th["tram_transit"]["amber_m"] * 2  # wide pre-filter
    for p in index.tram:
        d = haversine_m(lon, lat, p["lon"], p["lat"])
        if d <= _tram_cap:
            _tram_raw.append({**p, "distance_m": round(d), "mode": "T"})
    _tram_raw.sort(key=lambda x: x["distance_m"])
    tram_feats = _cluster_by_base(_tram_raw)

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

    intl_food_raw        = _osm_near("intl_food",       th["intl_food"]["radius_m"])
    coworking_raw        = _osm_near("coworking",       th["coworking"]["radius_m"])
    english_clinic_raw   = _osm_near("english_clinic",  3500)
    language_school_raw  = _osm_near("language_school", th["language_school"]["amber_m"] + 1500)
    library_raw          = _osm_near("library",         th["library"]["amber_m"] + 1500)
    packstation_raw      = _osm_near("packstation",     th["packstation"]["amber_m"] + 500)
    wochenmarkt_raw      = _osm_near("wochenmarkt",     th["wochenmarkt"]["amber_m"] + 1000)
    nightlife_raw        = _osm_near("nightlife",       1000)

    intl_food_feats       = [f for f in (_shape_osm_feature(o) for o in intl_food_raw)       if f]
    coworking_feats       = [f for f in (_shape_osm_feature(o) for o in coworking_raw)       if f]
    english_clinic_feats  = [f for f in (_shape_osm_feature(o) for o in english_clinic_raw)  if f]
    language_school_feats = [f for f in (_shape_osm_feature(o) for o in language_school_raw) if f]
    library_feats         = [f for f in (_shape_osm_feature(o) for o in library_raw)         if f]
    packstation_feats     = [f for f in (_shape_osm_feature(o) for o in packstation_raw)     if f]
    wochenmarkt_feats     = [f for f in (_shape_osm_feature(o) for o in wochenmarkt_raw)     if f]
    nightlife_feats       = [f for f in (_shape_osm_feature(o) for o in nightlife_raw)       if f]

    results = [
        ("buergeramt",       _tier_buergeramt_newcomer(buergeramt_feats,  th["buergeramt"])),
        ("rail_transit",     _tier_rail_transit(rail_feats,               th["rail_transit"])),
        ("tram_transit",     _tier_tram_transit(tram_feats,               th["tram_transit"])),
        ("bus_transit",      _tier_bus_transit(bus_feats,                 th["bus_transit"])),
        ("intl_food",        _tier_intl_food(intl_food_feats,             th["intl_food"])),
        ("coworking",        _tier_coworking(coworking_feats,             th["coworking"])),
        ("english_clinic",   _tier_english_clinic(english_clinic_feats,   th["english_clinic"])),
        ("language_school",  _tier_language_school(language_school_feats, th["language_school"])),
        ("library",          _tier_library(library_feats,                 th["library"])),
        ("packstation",      _tier_packstation(packstation_feats,         th["packstation"])),
        ("wochenmarkt",      _tier_wochenmarkt(wochenmarkt_feats,         th["wochenmarkt"])),
        ("nightlife_density", _tier_nightlife_density(nightlife_feats,    th["nightlife_density"])),
    ]

    feat_map = {
        "buergeramt":        buergeramt_feats,
        "rail_transit":     [{"name": f["name"], "lat": f["lat"], "lon": f["lon"],
                               "distance_m": f["distance_m"], "mode": f["mode"],
                               "walk_min": round(_walk_minutes(f["distance_m"])),
                               "directions": f.get("directions", [])}
                              for f in rail_feats[:10]],
        "tram_transit":     [{"name": f["name"], "lat": f["lat"], "lon": f["lon"],
                               "distance_m": f["distance_m"], "mode": "T",
                               "walk_min": round(_walk_minutes(f["distance_m"])),
                               "directions": f.get("directions", [])}
                              for f in tram_feats[:10]],
        "bus_transit":      [{"name": f["name"], "lat": f["lat"], "lon": f["lon"],
                               "distance_m": f["distance_m"], "mode": "B",
                               "walk_min": round(_walk_minutes(f["distance_m"]))}
                              for f in bus_feats[:10]],
        "intl_food":         intl_food_feats[:10],
        "coworking":         coworking_feats[:10],
        "english_clinic":    english_clinic_feats[:10],
        "language_school":   language_school_feats[:10],
        "library":           library_feats[:10],
        "packstation":       packstation_feats[:10],
        "wochenmarkt":       wochenmarkt_feats[:10],
        "nightlife_density": nightlife_feats[:10],
    }

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
        tiles.append({
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
        })

    tiles.append(_shape_gesix(cfg, index, lat, lon, card_key="gesix_newcomer",
                              label=tile_meta["gesix_newcomer"][0]))

    return {
        "slug":       lens.slug,
        "label":      lens.label,
        "audience":   lens.audience_hint,
        "tiles":      tiles,
        "provenance": _lens_provenance(cfg, tiles),
    }
