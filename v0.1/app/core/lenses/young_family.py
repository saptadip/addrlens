"""Young Family lens composer (Spec A).

Pure — no I/O on the hot path. All inputs are already-computed values
from `/api/lookup` (air / heat / noise / amenities / trees /
quiet_zone). Never call WFS from here — that keeps the lens from ever
disagreeing with the raw data in the same response.

Two per-city tile shapes coexist behind the same lens slug:

Berlin — 10 tiles in fixed order:
    kita, playground, pediatrician, transit, supermarket, gesix (shape-only),
    noise, heat, air, refuge

Hamburg — 8 tiles (no `air` / no `refuge` / no `noise`, `noise_band` in
place of `noise`, `sozialmonitoring_status_young_family` shape-only at tail):
    kita, playground, pediatrician, transit, supermarket, noise_band,
    heat, sozialmonitoring_status_young_family

Hamburg-specific behaviour:
- Transit tile skips Tram leg (abolished 1978) via `if getattr(index, "tram", None):` guard.
- `noise_band` reads Hamburg's isoline model via `index.noise_bands_at(lon, lat)`.
- `sozialmonitoring_status_young_family` is a shape-only tile appended at tail.
"""

from app.core.scoring.constants import TIER_UNKNOWN
from app.core.scoring.legends import _legend_for
from app.core.scoring.provenance import _lens_provenance, _sources_for
from app.core.scoring.shape import (
    _shape_gesix, _shape_kita, _shape_paediatric_gp, _shape_playground,
    _shape_refuge_quiet, _shape_refuge_trees, _shape_sozialmonitoring,
    _shape_supermarket, _shape_transit_stop,
)
from app.core.scoring.tiers import (
    _tier_air, _tier_heat, _tier_kita, _tier_noise, _tier_noise_isoline,
    _tier_pediatrician, _tier_playground, _tier_refuge, _tier_supermarket,
    _tier_transit,
)


def young_family_lens(cfg, index, lon: float, lat: float, *,
                      air: dict, heat: dict, noise: dict,
                      amenities: dict, trees: dict, quiet_zone: dict) -> dict:
    """Assemble tile results for one address — supports Berlin (10 tiles) and
    Hamburg (8 tiles) from the same composer by iterating over `cfg.young_family_lens.tiles`
    and branching on tile key."""
    from app.core.amenities import is_paediatric

    lens = cfg.young_family_lens
    th        = {t.key: t.thresholds for t in lens.tiles}
    tile_meta = {t.key: (t.label, t.icon, t.caveat) for t in lens.tiles}

    kitas = index.kitas_near_bod(lon, lat, 800)

    pg_block = (amenities or {}).get("playgrounds") or {}
    pg_items = pg_block.get("items") or []
    pg_error = bool(pg_block.get("error") or pg_block.get("_error"))

    gps_block = (amenities or {}).get("gps") or {}
    gps_items = gps_block.get("items") or []
    gps_error = bool(gps_block.get("error") or gps_block.get("_error"))
    paediatric = [g for g in gps_items if is_paediatric(g.get("tags"))]
    paediatric.sort(key=lambda x: x.get("distance_m", 10**9))

    # Transit — nearest of each modality. Consolidated feature list; tier
    # reads off the min walk_min across all modes.
    # Hamburg has no tram network (abolished 1978); skip the Tram leg when
    # `index.tram` is absent (None / missing attribute).
    _transit_feats = []
    _transit_modalities = [("S-Bahn", index.sbahn), ("U-Bahn", index.ubahn)]
    if getattr(index, "tram", None):
        _transit_modalities.append(("Tram", index.tram))
    for modality, points in _transit_modalities:
        nearest = index.nearest_station(points, lon, lat)
        f = _shape_transit_stop(nearest, modality) if nearest else None
        if f:
            _transit_feats.append(f)
    _tr_block = (amenities or {}).get("transit") or {}
    _tr_items = _tr_block.get("items") or []
    _bus_items = [it for it in _tr_items
                  if (it.get("tags") or {}).get("bus") == "yes"
                  or (it.get("tags") or {}).get("highway") == "bus_stop"]
    if _bus_items:
        _bus_items.sort(key=lambda x: x.get("distance_m", 10**9))
        f_bus = _shape_transit_stop(_bus_items[0], "Bus")
        if f_bus:
            _transit_feats.append(f_bus)
    _transit_feats.sort(key=lambda x: x.get("walk_min", 10**9))
    # Cap the feature list at the tile's amber walk budget so nearest-per-
    # modality doesn't surface a modality with zero neighbourhood coverage
    # (e.g. tram 4 km away). Tier is still min(walk_min) over the filtered
    # list, so a nearby Bus keeps a legitimately green verdict.
    _amber_min = th["transit"]["amber_min"]
    _transit_feats = [f for f in _transit_feats
                      if f.get("walk_min") is not None
                      and f["walk_min"] <= _amber_min]
    # Dedup platform pairs sharing a station name across modalities.
    # See scorer history for the S+U-hub and "-> DIR" reasoning.
    _clusters: dict = {}
    for _f in _transit_feats:
        _base = _f.get("name", "").partition(" -> ")[0].strip()
        if not _base:
            continue
        _entry = _clusters.get(_base)
        if _entry is None:
            _clusters[_base] = {**_f, "name": _base}
            continue
        _new = (_f.get("modality") or "").strip()
        if _new and _new not in (_entry.get("modality") or "").split(" · "):
            _existing = _entry.get("modality") or ""
            _entry["modality"] = f"{_existing} · {_new}" if _existing else _new
    _transit_feats = sorted(_clusters.values(),
                            key=lambda x: x.get("walk_min", 10**9))

    _sm_block = (amenities or {}).get("supermarkets") or {}
    _sm_items = _sm_block.get("items") or []
    _sm_error = bool(_sm_block.get("error") or _sm_block.get("_error"))
    _sm_feats = [f for f in (_shape_supermarket(o) for o in _sm_items) if f]
    _sm_feats.sort(key=lambda x: x.get("walk_min", 10**9))

    # Noise-band tile (Hamburg isoline path) — road-day layer lower edge.
    # `noise_bands_at` returns None for cities whose noise_model isn't "isoline".
    noise_band_val = None
    if "noise_band" in th and hasattr(index, "noise_bands_at"):
        bands = index.noise_bands_at(lon, lat) or {}
        noise_band_val = bands.get("road_den_band")

    # Presence in `th` = tile is configured for this city's lens.
    # Berlin ships kita, playground, pediatrician, transit, supermarket, gesix,
    # noise, heat, air, refuge.
    # Hamburg swaps noise -> noise_band, drops air + refuge, adds
    # sozialmonitoring_status_young_family shape-only at tail.
    # Shape-only tiles (gesix, sozialmonitoring_status_young_family) are
    # skipped here and appended after the results loop.
    results = []
    for t in lens.tiles:
        k = t.key
        if k == "kita":
            results.append((k, _tier_kita(kitas, th[k])))
        elif k == "playground":
            results.append((k, _tier_playground(pg_items, pg_error, th[k])))
        elif k == "pediatrician":
            results.append((k, _tier_pediatrician(paediatric, gps_error, th[k])))
        elif k == "transit":
            results.append((k, _tier_transit(_transit_feats, th[k])))
        elif k == "supermarket":
            results.append((k, (_tier_supermarket(_sm_feats, th[k])
                                 if not _sm_error
                                 else {"tier": TIER_UNKNOWN,
                                       "rule": "Supermarket data unavailable",
                                       "numeric": "OSM Overpass unavailable"})))
        elif k == "noise":
            results.append((k, _tier_noise(noise, th[k])))
        elif k == "noise_band":
            results.append((k, _tier_noise_isoline(noise_band_val, th[k])))
        elif k == "heat":
            results.append((k, _tier_heat(heat, th[k])))
        elif k == "air":
            results.append((k, _tier_air(air, th[k])))
        elif k == "refuge":
            results.append((k, _tier_refuge(quiet_zone, trees, th[k])))
        elif k in ("gesix", "sozialmonitoring_status_young_family"):
            # Shape-only tiles — appended via _shape_* helpers below.
            continue
        else:
            # Unknown tile key — skip rather than crash the lens. Add the
            # key here + wire an appropriate _tier_* fn when a new tile
            # is introduced.
            continue

    tiles = []
    for key, res in results:
        label, icon, caveat = tile_meta[key]
        tile = {
            "key":     key,
            "label":   label,
            "icon":    icon,
            "tier":    res["tier"],
            "rule":    res["rule"],
            "numeric": res["numeric"],
            "caveat":  caveat,
            "sources": _sources_for(cfg, key, res["tier"]),
            "legend":  _legend_for(key, th.get(key, {}) or {}),
        }
        if key == "kita":
            tile["features"] = [f for f in
                (_shape_kita(o, cfg.kita_field_map) for o in kitas) if f]
        elif key == "playground":
            tile["features"] = [f for f in
                (_shape_playground(o) for o in pg_items) if f]
        elif key == "pediatrician":
            tile["features"] = [f for f in
                (_shape_paediatric_gp(o) for o in paediatric) if f]
        elif key == "refuge":
            tile["features"] = _shape_refuge_quiet(
                quiet_zone, th["refuge"]["amber_quiet_m"])
            tile["metadata"] = {"trees": _shape_refuge_trees(trees)}
        elif key == "transit":
            tile["features"] = _transit_feats
        elif key == "supermarket":
            tile["features"] = _sm_feats[:10]
        else:
            tile["features"] = []
            if key == "noise":
                tile["metadata"] = {"l_den": (noise or {}).get("l_den"),
                                     "l_night": (noise or {}).get("l_night")}
            elif key == "noise_band":
                tile["metadata"] = {"road_den_band": noise_band_val}
            elif key == "heat":
                tile["metadata"] = {"day_class": (heat or {}).get("day_class"),
                                     "night_class": (heat or {}).get("night_class")}
            elif key == "air":
                tile["metadata"] = {"no2_ugm3": (air or {}).get("no2_ugm3")}
        tiles.append(tile)
        # GESIx shape-only tile follows supermarket in the output ordering
        # (Berlin's exact current behaviour — preserved verbatim).
        if key == "supermarket" and "gesix" in th:
            tiles.append(_shape_gesix(cfg, index, lat, lon, card_key="gesix",
                                      label=tile_meta["gesix"][0],
                                      caveat=tile_meta["gesix"][2] or ""))

    # Hamburg shape-only trailing tile — appended at the tail to match the
    # `lens.tiles` order in hamburg/lenses.py (last entry).
    if "sozialmonitoring_status_young_family" in th:
        tiles.append(_shape_sozialmonitoring(
            cfg, index, lat, lon,
            card_key="sozialmonitoring_status_young_family",
            label=tile_meta["sozialmonitoring_status_young_family"][0],
            focus="status",
            caveat=tile_meta["sozialmonitoring_status_young_family"][2] or "",
        ))

    return {
        "slug":       lens.slug,
        "label":      lens.label,
        "audience":   lens.audience_hint,
        "tiles":      tiles,
        "provenance": _lens_provenance(cfg, tiles),
    }
