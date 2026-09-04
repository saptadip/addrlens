"""Provenance composition — per-tile `sources` list + lens-level string."""

from app.core.scoring.constants import TIER_UNKNOWN


def _sources_for(cfg, key: str, tier: str) -> list:
    """Return the `sources` array for one tile. Unknown tiles get []. Every
    string is looked up in cfg.attribution — never invent a provenance line.
    Empty strings dropped so a missing attribution key doesn't leak an empty
    citation."""
    if tier == TIER_UNKNOWN:
        return []
    attr = cfg.attribution
    mapping = {
        "kita":         [attr.get("kitas")],
        "playground":   [attr.get("playgrounds"),
                         attr.get("parks"),
                         "© OpenStreetMap contributors (ODbL)"],
        "pediatrician": ["© OpenStreetMap contributors (ODbL)"],
        "noise":        [attr.get("noise")],
        "heat":         [attr.get("heat")],
        "air":          [attr.get("air")],
        "refuge":       [attr.get("quiet_zone"), attr.get("trees")],
        "transit":      [attr.get("sbahn"), attr.get("ubahn"), attr.get("tram"),
                         "© OpenStreetMap contributors (ODbL) — bus stops"],
        "supermarket":  ["© OpenStreetMap contributors (ODbL)"],
        "gesix":        [attr.get("gesix")],
        # Spec E — Newcomer lens
        # The Bürgeramt tile cites the BOD attribution string. The other
        # public-admin office data (Finanzamt / Standesamt / LEA /
        # Arbeitsagentur) is surfaced via the raw-view Others tab through
        # `app.core.others_admin.build`; its provenance is composed there.
        "buergeramt":     [attr.get("buergeramt")],
        # Transit uses the same VBB attribution as the YF transit tile.
        # OSM buckets cite Geofabrik; no separate attribution key in berlin.py
        # so we inline the standard ODbL line (ponytail: add per-key entries
        # to attribution once the snapshot source is pinned per-city).
        "rail_transit":    [attr.get("sbahn"), attr.get("ubahn")],
        "tram_transit":    [attr.get("tram")],
        "bus_transit":     ["© OpenStreetMap contributors (ODbL) via Geofabrik"],
        "intl_food":       ["© OpenStreetMap contributors (ODbL) via Geofabrik"],
        "coworking":       ["© OpenStreetMap contributors (ODbL) via Geofabrik"],
        "english_clinic":  ["© OpenStreetMap contributors (ODbL) via Geofabrik"],
        "language_school": ["© OpenStreetMap contributors (ODbL) via Geofabrik"],
        "library":         ["© OpenStreetMap contributors (ODbL) via Geofabrik"],
        "packstation":     ["© OpenStreetMap contributors (ODbL) via Geofabrik"],
        "wochenmarkt":     ["© OpenStreetMap contributors (ODbL) via Geofabrik"],
        "gesix_newcomer":  [attr.get("gesix")],
        # Ship D+ — Quiet Living lens
        # `noise`, `air`, and `gesix_quiet` reuse the Young Family tile
        # keys' attribution strings above via the same map lookup on
        # `attribution["noise"] / ["air"] / ["gesix"]`.
        "quiet_zone":         [attr.get("quiet_zone")],
        "street_trees":       [attr.get("trees")],
        "tempo30":            [attr.get("tempolimits")],
        "arterial_road":      [attr.get("arterial_road")],
        # Rail-noise cites S+U attribution because it's derived from
        # those station coords as a track proxy.
        "rail_noise":         [attr.get("sbahn"), attr.get("ubahn")],
        # Nightlife inverted reuses the newcomer OSM Geofabrik line.
        "nightlife_inverted": ["© OpenStreetMap contributors (ODbL) via Geofabrik"],
        "nightlife_density":  ["© OpenStreetMap contributors (ODbL) via Geofabrik"],
        "gesix_quiet":        [attr.get("gesix")],
        # Ship D++ — Commuter lens
        # `commuter_rail_transit`, `commuter_tram_transit`,
        # `commuter_bus_transit` reuse the VBB S+U / Tram attribution and
        # the standard OSM bus-stop line — same underlying feeds as the
        # newcomer / young-family transit tiles, just tighter thresholds
        # and a commuter framing in the AI prompt.
        "commuter_rail_transit":  [attr.get("sbahn"), attr.get("ubahn")],
        "commuter_tram_transit":  [attr.get("tram")],
        "commuter_bus_transit":   ["© OpenStreetMap contributors (ODbL) via Geofabrik"],
        # Regional rail — the curated Berlin RE/RB list already carries a
        # VBB station-coord provenance; reuse S-Bahn line as the closest
        # extant attribution.
        "regional_rail_reach":    [attr.get("sbahn")],
        "cycling_network":        [attr.get("cycling")],
        "car_sharing_reach":      [attr.get("car_sharing")],
        # EV chargers already exist in the OSM `ev_charging` bucket — cite
        # the ODbL Geofabrik line consistent with other OSM buckets.
        "ev_charging_reach":      ["© OpenStreetMap contributors (ODbL) via Geofabrik"],
        # Airport reach is a single curated coordinate from cfg.airport —
        # attribute to the public BER coordinate to avoid rendering an
        # empty "Data sources" section on the About tab.
        "airport_reach":          ["Curated coordinate — Berlin Brandenburg Airport (BER, public)"],
        "gesix_commuter":         [attr.get("gesix")],
    }
    return [s for s in (mapping.get(key) or []) if s]


def _lens_provenance(cfg, tiles: list) -> str:
    """Union of `sources` from tiles that contributed a real tier — de-duped,
    insertion-order preserved (Python 3.7+ dict semantics). Unknown tiles
    contribute [], so they're skipped naturally. Empty string if nothing to
    cite; frontend hides the provenance footer in that case (§14.5)."""
    seen, out = set(), []
    for tile in tiles:
        for s in (tile.get("sources") or []):
            if s and s not in seen:
                seen.add(s); out.append(s)
    return " · ".join(out)


if __name__ == "__main__":
    class _Cfg:
        attribution = {"kitas": "Kindertagesstätten (BOD)",
                       "buergeramt": "Bürgerämter (BOD)",
                       "gesix":      "GESIx 2022"}

    # Unknown tier → empty list (never cite for a tile we can't score).
    assert _sources_for(_Cfg(), "kita", TIER_UNKNOWN) == []
    # Green kita → cites Kindertagesstätten string, not the bare key.
    assert _sources_for(_Cfg(), "kita", "green") == ["Kindertagesstätten (BOD)"]
    # Newcomer buergeramt reuses the Spec-B BOD attribution.
    assert _sources_for(_Cfg(), "buergeramt", "green") == ["Bürgerämter (BOD)"]
    # Missing attribution key → drop the empty from sources.
    assert _sources_for(_Cfg(), "noise", "amber") == []
    # OSM Geofabrik line is inlined (no attribution key) — always present.
    assert "OpenStreetMap" in _sources_for(_Cfg(), "intl_food", "green")[0]

    # _lens_provenance — de-dup + insertion order preserved.
    tiles = [
        {"sources": ["A", "B"]},
        {"sources": []},
        {"sources": ["B", "C", "A"]},
        {"sources": None},
    ]
    assert _lens_provenance(_Cfg(), tiles) == "A · B · C"
    assert _lens_provenance(_Cfg(), [{"sources": []}, {"sources": None}]) == ""
    print("scoring.provenance selfcheck OK")
