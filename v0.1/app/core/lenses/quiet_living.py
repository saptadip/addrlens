"""Quiet Living lens composer.

Pure — no I/O on the hot path. All inputs are already-computed values
from `/api/lookup` (air / noise / quiet_zone / trees) plus the OSM
`nightlife` bucket which the composer resolves per-request from
`index.osm_local` (matches the newcomer lens pattern).

Nine tiles in fixed order:

    noise, air, quiet_zone, street_trees, tempo30, arterial_road,
    rail_noise, nightlife_inverted, gesix_quiet

Reuse:
- `noise` + `air` share the Young Family thresholds (WHO L_DEN 55/60 dB
  and Berlin NO₂ 20/40 µg/m³).
- `quiet_zone` and `street_trees` are split back out of YF's `refuge`
  composite so a "quiet living" audience gets each signal on its own.
- `gesix_quiet` is a shape-only tile (`_shape_gesix` with a per-lens
  `card_key`) — same pattern as `gesix` (YF) and `gesix_newcomer`.

New:
- `tempo30` — nearest Tempolimits exception.
- `arterial_road` — nearest arterial-tier road.
- `rail_noise` — nearest S/U-Bahn station as a track proxy.
- `nightlife_inverted` — OSM nightlife count within 300 m; lower = greener.
"""

from app.core.scoring.legends import _legend_for
from app.core.scoring.provenance import _lens_provenance, _sources_for
from app.core.scoring.shape import _shape_gesix, _shape_osm_feature
from app.core.scoring.tiers import (
    _tier_air, _tier_arterial_road, _tier_nightlife_inverted, _tier_noise,
    _tier_quiet_zone_solo, _tier_rail_noise, _tier_street_trees,
    _tier_tempo30,
)


def quiet_living_lens(cfg, index, lon: float, lat: float, *,
                     air: dict, noise: dict, quiet_zone: dict,
                     trees: dict) -> dict:
    """Assemble the 9-tile Quiet Living lens block for one address.

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
    rail = index.rail_track_proximity(lon, lat)

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

    results = [
        ("noise",              _tier_noise(noise, th["noise"])),
        ("air",                _tier_air(air, th["air"])),
        ("quiet_zone",         _tier_quiet_zone_solo(quiet_zone, th["quiet_zone"])),
        ("street_trees",       _tier_street_trees(trees, th["street_trees"])),
        ("tempo30",            _tier_tempo30(tempo, th["tempo30"])),
        ("arterial_road",      _tier_arterial_road(arterial, th["arterial_road"])),
        ("rail_noise",         _tier_rail_noise(rail, th["rail_noise"])),
        ("nightlife_inverted", _tier_nightlife_inverted(nightlife_feats, th["nightlife_inverted"])),
    ]

    # Feature payloads per tile — kept minimal since most Quiet Living
    # tiles are aggregate readings, not shortlists. Tiles that carry a
    # single anchor (quiet zone, arterial, rail) expose it so the map
    # can plot a pin. Nightlife-inverted exposes the whole shaped list
    # so the AI insight paragraph can reference specific venues.
    feat_map: dict = {
        "noise":              [],
        "air":                [],
        "quiet_zone":         [],
        "street_trees":       [],
        "tempo30":            [],
        "arterial_road":      [],
        "rail_noise":         [],
        "nightlife_inverted": nightlife_feats[:10],
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
    metadata_map["air"] = {"no2_ugm3": (air or {}).get("no2_ugm3")}

    # New single-anchor / aggregate tiles — the card_insight route reads
    # these keys via `_ctx_tempo30 / _ctx_arterial_road / _ctx_rail_noise`.
    # None inputs are stored as `None` so downstream builders can guard.
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

    # gesix_quiet — shape-only tile at the tail, same pattern as YF/Newcomer.
    tiles.append(_shape_gesix(cfg, index, lat, lon,
                              card_key="gesix_quiet",
                              label=tile_meta["gesix_quiet"][0]))

    return {
        "slug":       lens.slug,
        "label":      lens.label,
        "audience":   lens.audience_hint,
        "tiles":      tiles,
        "provenance": _lens_provenance(cfg, tiles),
    }
