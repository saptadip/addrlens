"""Quiet Living lens composer.

Pure — no I/O on the hot path. All inputs are already-computed values
from `/api/lookup` (air / noise / quiet_zone / trees / heat) plus the
OSM `nightlife` bucket which the composer resolves per-request from
`index.osm_local` (matches the newcomer lens pattern).

Two per-city tile shapes coexist behind the same lens slug:

Berlin — 10 tiles in fixed order:
    noise, air, quiet_zone, street_trees, tempo30, arterial_road,
    cobblestone_nearby, rail_noise, nightlife_inverted, gesix_quiet

Hamburg — 9 tiles (no `air` / no `rail_noise`, `noise_band` in place
of `noise`, `heat` added, `sozialmonitoring_status_quiet` in place of
`gesix_quiet`):
    noise_band, quiet_zone, street_trees, tempo30, arterial_road,
    cobblestone_nearby, nightlife_inverted, heat,
    sozialmonitoring_status_quiet

Reuse:
- `noise` + `air` share the Young Family thresholds (WHO L_DEN 55/60 dB
  and Berlin NO₂ 20/40 µg/m³).
- `quiet_zone` and `street_trees` are split back out of YF's `refuge`
  composite so a "quiet living" audience gets each signal on its own.
- `gesix_quiet` is a shape-only tile (`_shape_gesix` with a per-lens
  `card_key`) — same pattern as `gesix` (YF) and `gesix_newcomer`.

Berlin-only tiles skipped for Hamburg:
- `air` — Hamburg publishes no per-street NO₂ (spec Q10).
- `rail_noise` — the Berlin heuristic treats U-Bahn as always green
  (mostly underground); Hamburg's U-Bahn is largely elevated so the
  shortcut inverts. Rewiring is a follow-up.

Hamburg-only additions:
- `noise_band` — reads Hamburg's isoline noise model via
  `index.noise_bands_at`; tier derived from the road-day band's lower
  edge with the same 55 / 60 dB WHO cutoffs.
- `street_trees` uses `_tier_street_trees_density` (count fallback);
  Hamburg's Straßenbaumkataster has no crown-diameter field.
- `heat` — Stadtklimaanalyse 2023 PET class, reused from YF.
- `sozialmonitoring_status_quiet` — shape-only Sozialmonitoring tile.
"""

from app.core.scoring.legends import _legend_for
from app.core.scoring.provenance import _lens_provenance, _sources_for
from app.core.scoring.shape import (
    _shape_gesix, _shape_osm_feature, _shape_sozialmonitoring,
)
from app.core.scoring.tiers import (
    _tier_air, _tier_arterial_road, _tier_cobblestone_nearby, _tier_heat,
    _tier_nightlife_inverted, _tier_noise, _tier_noise_isoline,
    _tier_quiet_zone_solo, _tier_rail_noise, _tier_street_trees,
    _tier_street_trees_density, _tier_tempo30,
)


def quiet_living_lens(cfg, index, lon: float, lat: float, *,
                     air: dict, noise: dict, quiet_zone: dict,
                     trees: dict, heat: dict = None) -> dict:
    """Assemble the 10-tile Quiet Living lens block for one address.

    Args match the Young Family lens for `air`, `noise`, `quiet_zone`,
    `trees` — the /api/lookup handler computes these once and passes
    them into every lens that needs them.

    The two new WFS-backed signals (Tempolimits, arterial roads) and the
    rail-noise proxy read from preloaded `Index` state — no live WFS on
    the hot path. Nightlife-inverted queries `index.osm_local` for the
    OSM `nightlife` bucket (same as newcomer lens).
    """
    lens = cfg.quiet_living_lens
    th        = {t.key: t.thresholds for t in lens.tiles}
    tile_meta = {t.key: (t.label, t.icon, t.caveat) for t in lens.tiles}

    # -- Data resolution -------------------------------------------------
    tempo = index.tempolimit_at(lon, lat)
    arterial = index.nearest_arterial(lon, lat)
    # Rail-noise is Berlin-only for now — see module docstring.
    rail = (index.rail_track_proximity(lon, lat)
            if "rail_noise" in th else None)

    # Noise-band tile (Hamburg isoline path) — the road-day layer is the
    # only one Hamburg has wired at this point; rail / aircraft isoline
    # layers are None-holders in `hamburg/config.py`. `noise_bands_at`
    # returns None for cities whose `noise_model` isn't "isoline".
    noise_band_val = None
    if "noise_band" in th and hasattr(index, "noise_bands_at"):
        bands = index.noise_bands_at(lon, lat) or {}
        noise_band_val = bands.get("road_den_band")

    # Nightlife-inverted: reuse the newcomer OSM `nightlife` bucket at a
    # tighter radius (300 m). If the OsmLocalCache isn't loaded, treat
    # as zero features (green — no local nightlife observed).
    oc = getattr(index, "osm_local", None)
    _nl_radius = th["nightlife_inverted"]["radius_m"]
    if oc is None:
        nightlife_raw = []
    else:
        nightlife_raw = oc.near("nightlife", lon, lat, _nl_radius) or []
    # Shape to the response feature dict (same as newcomer). The tier
    # func only reads `len()`, but the feature list is what the AI
    # insight paragraph reads — must be shaped.
    nightlife_feats = [f for f in
                       (_shape_osm_feature(o) for o in nightlife_raw) if f]

    # Cobblestone: nearest OSM way with a stone driving-surface tag on
    # a trafficked highway class. Fetch out to (green_m + margin) so the
    # tier func can classify at the edge; matches the cycling pattern of
    # fetching amber_m + 200 in the Commuter composer.
    # `oc is None` (no OSM snapshot loaded at all — production hard-fail
    # scenario) is treated the same as bucket-absent → `unknown`, following
    # the cycling_network / car_sharing_reach precedent. This is stricter
    # than `nightlife_inverted` above (which treats `oc is None` as green);
    # cobblestone leans conservative because a silent green claim of "no
    # cobblestone streets nearby" on a broken snapshot would be a false
    # positive with real user impact.
    _cob_green_m = th["cobblestone_nearby"]["green_m"]
    _cob_fetch_radius = _cob_green_m + 100
    _cob_missing = oc is None or "cobblestone" not in getattr(oc, "buckets", {})
    if _cob_missing:
        _cob_raw = []
    else:
        _cob_raw = oc.near("cobblestone", lon, lat, _cob_fetch_radius) or []
    # Inline shape — `_shape_osm_feature` drops rows without a name, but
    # some OSM cobblestone ways may lack a `name` tag (short alley, private
    # driveway that still counts as `highway=residential`). Keep the row
    # so distance is honoured; synthesise a stable label at read time.
    cobblestone_feats = []
    for _o in _cob_raw:
        _d = _o.get("distance_m")
        _la = _o.get("lat")
        _lo = _o.get("lon")
        if _d is None or _la is None or _lo is None:
            continue
        cobblestone_feats.append({
            "name":       (_o.get("name") or "Cobblestone street").strip(),
            "lat":        _la, "lon": _lo,
            "distance_m": _d,
        })
    cobblestone_feats.sort(key=lambda x: x["distance_m"])

    # `bucket_missing` flag is threaded through the thresholds so a fresh
    # code / stale snapshot cleanly resolves to 'unknown' rather than a
    # false green (same pattern as cycling_network / car_sharing_reach).
    _th_cobblestone = {**th["cobblestone_nearby"], "bucket_missing": _cob_missing}

    # Presence in `th` = tile is configured for this city's lens. Berlin
    # ships `noise` + `air` + `rail_noise` + `gesix_quiet`; Hamburg swaps
    # to `noise_band` + `heat` + `sozialmonitoring_status_quiet` and skips
    # `air` / `rail_noise`. Order matches the tile-list order in each
    # city's `lenses.py` so the response array stays in the expected slot.
    results = []
    for t in lens.tiles:
        k = t.key
        if k == "noise":
            results.append((k, _tier_noise(noise, th[k])))
        elif k == "noise_band":
            results.append((k, _tier_noise_isoline(noise_band_val, th[k])))
        elif k == "air":
            results.append((k, _tier_air(air, th[k])))
        elif k == "quiet_zone":
            results.append((k, _tier_quiet_zone_solo(quiet_zone, th[k])))
        elif k == "street_trees":
            # Two threshold shapes select the tier fn: crown-coverage %
            # (Berlin) vs. tree-count density (Hamburg).
            if "green_count" in th[k]:
                results.append((k, _tier_street_trees_density(trees, th[k])))
            else:
                results.append((k, _tier_street_trees(trees, th[k])))
        elif k == "tempo30":
            results.append((k, _tier_tempo30(tempo, th[k])))
        elif k == "arterial_road":
            results.append((k, _tier_arterial_road(arterial, th[k])))
        elif k == "cobblestone_nearby":
            results.append((k, _tier_cobblestone_nearby(cobblestone_feats, _th_cobblestone)))
        elif k == "rail_noise":
            results.append((k, _tier_rail_noise(rail, th[k])))
        elif k == "nightlife_inverted":
            results.append((k, _tier_nightlife_inverted(nightlife_feats, th[k])))
        elif k == "heat":
            results.append((k, _tier_heat(heat, th[k])))
        elif k in ("gesix_quiet", "sozialmonitoring_status_quiet"):
            # Shape-only tiles are appended at the tail via _shape_*
            # helpers below (not through the tier-result flow).
            continue
        else:
            # Unknown tile key — skip rather than crash the lens. Add the
            # key here + wire an appropriate _tier_* fn when a new tile
            # is introduced.
            continue

    # Feature payloads per tile — kept minimal since most Quiet Living
    # tiles are aggregate readings, not shortlists. Tiles that carry a
    # single anchor (quiet zone, arterial, rail) expose it so the map
    # can plot a pin. Nightlife-inverted exposes the whole shaped list
    # so the AI insight paragraph can reference specific venues.
    feat_map: dict = {
        "noise":              [],
        "noise_band":         [],
        "air":                [],
        "quiet_zone":         [],
        "street_trees":       [],
        "tempo30":            [],
        "arterial_road":      [],
        "cobblestone_nearby": cobblestone_feats[:10],
        "rail_noise":         [],
        "nightlife_inverted": nightlife_feats[:10],
        "heat":               [],
    }
    metadata_map: dict = {}

    # Quiet zone — pin the polygon centroid when in range.
    if quiet_zone and quiet_zone.get("distance_m") is not None:
        feat_map["quiet_zone"] = [{
            "name":       (quiet_zone.get("name") or "Quiet zone").strip(),
            "lat":        quiet_zone.get("lat"),
            "lon":        quiet_zone.get("lon"),
            "distance_m": quiet_zone.get("distance_m"),
        }]

    # Street trees — expose the top-species summary so the modal can
    # render the same block as YF's refuge.metadata.trees.
    if trees and not trees.get("error"):
        metadata_map["street_trees"] = {"trees": {
            "count":              trees.get("count"),
            "avg_age_yr":         trees.get("avg_age_yr"),
            "tallest_m":          trees.get("tallest_m"),
            "crown_coverage_pct": trees.get("crown_coverage_pct"),
            "top_species":       [{"name": s.get("name"), "n": s.get("n")}
                                   for s in (trees.get("top_species") or [])[:5]
                                   if s.get("name")],
        }}

    # Nightlife-inverted: expose the count + radius for the modal.
    metadata_map["nightlife_inverted"] = {
        "count":    len(nightlife_feats),
        "radius_m": _nl_radius,
    }

    # Aggregate-reading tiles carry the raw payload on metadata so the
    # AI-insight route sends structured facts (matches YF pattern).
    metadata_map["noise"] = {
        "l_den":   (noise or {}).get("l_den"),
        "l_night": (noise or {}).get("l_night"),
    }
    metadata_map["noise_band"] = {
        "road_den_band": noise_band_val,
    }
    metadata_map["air"] = {"no2_ugm3": (air or {}).get("no2_ugm3")}
    metadata_map["heat"] = {"day_class": (heat or {}).get("day_class")}

    # Single-anchor / aggregate tiles — metadata carried on the tile
    # for the modal's Readout view. None inputs are stored as `None` so
    # downstream builders can guard.
    metadata_map["tempo30"] = {"tempolimit": tempo}
    metadata_map["arterial_road"] = {"arterial": arterial}
    metadata_map["rail_noise"] = {"rail": rail}

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

    # Shape-only trailing tile — Berlin ships `gesix_quiet`, Hamburg
    # ships `sozialmonitoring_status_quiet`. Order in the response
    # matches the tile-list order in each city's `lenses.py`, which
    # places the shape-only tile at the tail.
    if "gesix_quiet" in th:
        tiles.append(_shape_gesix(cfg, index, lat, lon,
                                  card_key="gesix_quiet",
                                  label=tile_meta["gesix_quiet"][0]))
    if "sozialmonitoring_status_quiet" in th:
        tiles.append(_shape_sozialmonitoring(
            cfg, index, lat, lon,
            card_key="sozialmonitoring_status_quiet",
            label=tile_meta["sozialmonitoring_status_quiet"][0],
            focus="status",
        ))

    return {
        "slug":       lens.slug,
        "label":      lens.label,
        "audience":   lens.audience_hint,
        "tiles":      tiles,
        "provenance": _lens_provenance(cfg, tiles),
    }
