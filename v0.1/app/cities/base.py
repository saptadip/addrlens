"""CityConfig — the one place city-specific facts live. Every `core/` function
takes one of these instead of reading hard-coded constants (plan §2).

Ship B introduces the type; Berlin's values are in `berlin.py`. Ship C adds
`hamburg.py`. All future cities copy the same shape.

Field maps translate the canonical name the app uses ("name", "capacity", …)
into the per-city WFS property name ("e_name", "e_platz", …). Keep the
canonical keys stable across cities — that's the whole point.
"""
from __future__ import annotations

from dataclasses import dataclass, FrozenInstanceError
from typing import Optional


@dataclass(frozen=True)
class CityConfig:
    slug: str
    display_name: str
    default_center: tuple                 # (lat, lon)

    # Some servers expect `application/json` (Berlin gdi.berlin.de), others only
    # `application/geo+json` (Hamburg geodienste.hamburg.de). Set per-city so
    # the generic wfs() helper never has to guess.
    wfs_output_format: str

    # Address geocoding (WFS in Berlin; nominatim is the fallback path)
    geocoder: str                         # "wfs" | "nominatim"
    geocoder_wfs_url: Optional[str]
    geocoder_layer: Optional[str]
    geocoder_field_map: dict              # {"street", "hnr", "plz"}

    # Catchments (Schul-Einzugsgebiet)
    catchment_wfs_url: str
    catchment_layer: str
    catchment_field_map: dict             # {"id", "district"}

    # Schools
    schools_wfs_url: str
    schools_layer: str
    schools_field_map: dict               # {"name","id","type","public_flag",
                                          #  "street","hnr","plz","phone",
                                          #  "website","school_year"}
    schools_public_value: str             # "öffentlich"
    schools_primary_types: frozenset      # {"Grundschule", …}
    schools_intl_keywords: tuple          # substrings that flag intl/bilingual
    bilingual_schools: dict               # {name_substring_lower: strand_label}

    # Kitas
    kita_wfs_url: str
    kita_layer: str
    kita_field_map: dict                  # {"name","capacity","operator_type","approach"}

    # Hospitals (BOD-first, two layers in Berlin)
    hospital_wfs_url: Optional[str]
    hospital_layers: tuple                # ((layer_name, kind_tag), …)
    hospital_field_map: dict              # {"name_primary","name_alt1","name_alt2",
                                          #  "beds","beds_alt","traeger",
                                          #  "ortsteil","fachabteilungen"}
    hospital_radius_m: int                # search radius (2000 in Berlin)
    hospital_match_m: int                 # BOD ↔ OSM match tolerance

    # Drinking fountains (BOD-only; walkable stroller amenity)
    fountains_wfs_url: Optional[str]
    fountains_layer: Optional[str]
    fountains_field_map: dict             # {"seasonal","bezirk","type","location"}

    # Green space (parks + playgrounds share one WFS in Berlin)
    green_wfs_url: Optional[str]
    parks_layer: Optional[str]
    playgrounds_layer: Optional[str]

    # Façade noise (Strategische Lärmkarten)
    noise_wfs_url: Optional[str]
    noise_layer: Optional[str]
    noise_field_map: dict                 # {"total_den","road_den","rail_den","air_den",
                                          #  "total_n","road_n","rail_n","air_n"}
    noise_year: int

    # -- Phase-1 killer cards (Berlin BOD, all point-in-polygon or bbox) ------
    # Each block is Optional so a future city can opt out per-mode. Berlin's
    # values live in berlin.py.

    # Fire & rescue: two layers per plan §7.5.
    fire_wfs_url: Optional[str]
    fire_stations_layer: Optional[str]
    fire_zones_layer: Optional[str]
    fire_stations_field_map: dict       # {"name","type","address","phone_bf","phone_ff","zone_id"}
    fire_zones_field_map: dict          # {"id","name"}

    # Street trees (Baumbestand): city-wide huge (~435k rows), so per-request
    # bbox only — no preload. Radius is the "trees near you" window.
    trees_wfs_url: Optional[str]
    trees_layer: Optional[str]
    trees_field_map: dict               # {"species_de","genus_de","group","height","age","planting_year","street"}
    trees_radius_m: int                 # 200

    # Ruhige Gebiete (§47d BImSchG, quiet zones + inner-city recreation).
    quiet_wfs_url: Optional[str]
    quiet_layer: Optional[str]
    quiet_field_map: dict               # {"name","kind","size_ha","id"}

    # Neighborhood protection (§172 BauGB). Two overlapping layers: EM
    # (Milieuschutz — anti-displacement) and ES (city-character preservation).
    protection_wfs_url: Optional[str]
    protection_em_layer: Optional[str]
    protection_es_layer: Optional[str]
    protection_field_map: dict          # {"name","code","in_force","district","size_ha"}

    # -- Quiet Living lens data ----------------------------------------
    # Tempolimits: MultiLineString road segments carrying an EXCEPTION to
    # the general 50 km/h. Absence of a feature ≈ default 50. Autobahns
    # are included with their limit. Preloaded (~30k features, small
    # enough) so tempo-30 lookup is an in-memory nearest-line query.
    tempolimits_wfs_url:     Optional[str]
    tempolimits_layer:       Optional[str]
    tempolimits_field_map:   dict       # {"speed": "wert_ves", "time_restriction": "zeit_t", "reason": "durch_t"}
    # Übergeordnetes Straßennetz: LineString centrelines of the arterial
    # + supra-local road network. Distance-to-nearest = address exposure
    # to primary traffic. Preloaded.
    arterial_wfs_url:        Optional[str]
    arterial_layer:          Optional[str]
    arterial_field_map:      dict       # {"name":"strassenname","class":"strassenklasse1"}

    # Swim spots: pools (BBB) + EU-designated natural swimming waters.
    pools_wfs_url: Optional[str]
    pools_layer: Optional[str]
    pools_field_map: dict               # {"name","address","postcode","district","category","website","hours_hint"}
    swim_natural_wfs_url: Optional[str]
    swim_natural_layer: Optional[str]
    swim_natural_field_map: dict        # {"name","eu_rating","website","cyano"}

    # -- Phase 2 Umweltatlas cards --------------------------------------
    # Both layers are too big to preload (12k / 17k features), so lookups
    # use a per-request bbox query similar to noise_at().
    #
    # Air quality: per-street NO2 baseline for 2020 (Luftreinhalteplan
    # trend scenario). Feature is a LineString per road segment.
    air_wfs_url: Optional[str]
    air_layer: Optional[str]
    air_field_map: dict                 # {"street","no2","index","traffic","length"}
    # Summer heat: per-block bioclimate classification (PET at 14:00).
    # Feature is a MultiPolygon per residential block.
    heat_wfs_url: Optional[str]
    heat_layer: Optional[str]
    heat_field_map: dict                # {"day_class"}

    # Connectivity (S-Bahn / U-Bahn / Tram / Regional rail / Airport).
    # Each is Optional so a future city can opt out per-mode cleanly.
    #
    # S/U-Bahn come from a vendored CSV (see scripts/refresh_vbb.py). Tram
    # comes from a live BOD WFS at boot — same pattern as Kita/hospitals.
    # Regional rail is a curated list of (name, lat, lon) — VBB doesn't tag
    # regional-rail mode explicitly and it's a small, stable set. Airport
    # is one static point.
    stations_data_path: Optional[str]     # abs path to a vbb_<slug>_su.csv
    tram_wfs_url: Optional[str]
    tram_layer: Optional[str]
    tram_field_map: dict                  # {"name": "hstname"}
    regional_rail_stations: tuple         # ((name, lat, lon), …)
    airport: Optional[dict]               # {"name","iata","lat","lon"} or None

    # Local-language glossary — applied by core/gloss.py after inference-service
    # returns text. Each entry is (compiled_regex, english_gloss). See phase3
    # GERMAN_GLOSS for the Berlin seed.
    bilingual_glossary: list

    # Sanity bbox for input coord (south, west, north, east)
    overpass_bbox: tuple

    # Provenance strings, one per public-facing dataset. Keys used by the app:
    #   "catchment", "schools", "addresses", "kitas", "hospitals",
    #   "fountains", "playgrounds", "parks", "noise",
    #   "sbahn", "ubahn", "tram", "regional_rail", "airport",
    #   "fire", "trees", "quiet_zone", "protection",
    #   "pools", "natural_swim",
    #   "air", "heat".
    # Full string including licence tag; the app just concatenates when a
    # response mixes sources.
    attribution: dict

    # -- Local OSM snapshot (Geofabrik weekly) ---------------------------
    # Path to the JSON produced by scripts/refresh_osm_amenities.py. When
    # present, Index loads it into memory at boot and amenities_near serves
    # queries from it, falling back to Overpass only on miss / stale.
    # Optional: dev boxes without the file still work (Overpass path unchanged).
    # Prod: point at a Docker-mounted volume.
    osm_local_path: Optional[str]

    # Path to the JSON snapshot of Berlin addresses extracted from OSM by
    # scripts/refresh_osm_amenities.py. Loaded at Index boot into an
    # in-memory prefix index that powers the /api/suggest endpoint. Optional
    # — when None or the file is missing, /api/suggest returns []. Prod:
    # same Docker-mounted volume as osm_local_path.
    address_local_path: Optional[str]

    # -- GESIx (health & social composite index per Planungsraum) ---------
    # Berlin Senate 2022 open-data WFS. Optional per city; None disables the
    # neighbourhood-profile tile. When set, Index preloads all polygons at
    # boot and gesix_at(lon, lat) resolves to the address's Planungsraum
    # composite score + rank + stratum.
    gesix_wfs_url: Optional[str]
    gesix_layer:   Optional[str]

    # -- Lenses (Spec A: Young Family). Per-city view over amenities/environment
    # for a specific audience. Adding more lenses = adding more fields here.
    young_family_lens: LensConfig

    # -- Spec E: Newcomer lens -----------------------------------------
    newcomer_lens: LensConfig             # required — Spec E lens

    # -- Quiet Living lens (Ship D+) -----------------------------------
    quiet_living_lens: LensConfig

    # -- Commuter lens (Ship D+) ---------------------------------------
    commuter_lens: LensConfig

    # -- Public-admin office data (raw view "Others" tab) --------------
    # Was the Bureaucracy lens (Spec B); the traffic-light composer was
    # removed once the underlying cards moved to the raw-view Others tab.
    # These sources still feed that tab via `app.core.others_admin.build`.
    # Bezirksgrenzen — 12 polygons for point-in-polygon Bezirk assignment
    bezirksgrenzen_wfs_url:      Optional[str]
    bezirksgrenzen_layer:        Optional[str]
    bezirksgrenzen_field_map:    dict            # {"name": "namgem"} or similar
    # Bürgeramt (BOD WFS layer — points)
    buergeramt_wfs_url:          Optional[str]
    buergeramt_layer:            Optional[str]
    buergeramt_field_map:        dict            # {"name","address","website"}
    # Curated federal-office directories (small, stable — like regional_rail_stations)
    finanzamts:                  tuple           # ({"name","address","lat","lon"}, ...)
    standesamts_by_bezirk:       dict            # bezirk_name -> {"name","address","lat","lon"}
    arbeitsagenturs:             tuple           # ({"name","address","lat","lon"}, ...)
    lea_office:                  dict            # {"name","address","lat","lon"}
    # Ordered card metadata for the Others tab — each entry produces one
    # tile in the /api/lookup `others.bureaucracy.tiles` array (response
    # key retained for frontend compatibility; the concept is admin-cards).
    others_admin_cards:          tuple           # tuple[OthersAdminCardConfig, ...]


@dataclass(frozen=True)
class LensTileConfig:
    """One traffic-light tile in a lens.

    `thresholds` is deliberately an opaque dict — each `_tier_*` function in
    `app/core/scorer.py` interprets its own keys (distance vs dB vs μg/m³ vs
    class-strings). Keeps the config table readable per tile without a shared
    schema no tile actually satisfies.
    """
    key:        str
    label:      str
    icon:       str
    thresholds: dict
    caveat:     str = ""    # long-lived tile-scoped disclosure; hidden if empty


@dataclass(frozen=True)
class LensConfig:
    """Named view over an address (Young Family, Bureaucracy, …).

    Order of `tiles` is display order — the frontend renders tiles in this
    exact order, both in single-address and compare views.
    """
    slug:          str      # stable id, e.g. "young_family"
    label:         str      # human label, e.g. "Young Family (0–6)"
    audience_hint: str      # one-line subline shown under the label
    tiles:         tuple    # tuple[LensTileConfig, ...]


@dataclass(frozen=True)
class OthersAdminCardConfig:
    """One admin-office card on the raw-view Others tab.

    Minimal metadata — the tab is informational (no traffic-light tier,
    no thresholds). `key` matches a branch in
    `app.core.others_admin._features_for`; `icon` keys into the
    frontend `ico` map.
    """
    key:   str
    label: str
    icon:  str


if __name__ == "__main__":
    # Frozen — attempting to mutate must raise FrozenInstanceError.
    t = LensTileConfig(key="k", label="l", icon="i", thresholds={"green_m": 400})
    try:
        t.key = "changed"
    except FrozenInstanceError:
        pass
    else:
        raise AssertionError("LensTileConfig must be frozen")
    # `caveat` defaults to empty string — frontend hides when empty.
    assert t.caveat == ""
    lc = LensConfig(slug="s", label="l", audience_hint="h", tiles=(t,))
    assert lc.tiles[0].key == "k"

    # OthersAdminCardConfig — frozen, minimal metadata.
    oa = OthersAdminCardConfig(key="buergeramt", label="Bürgeramt", icon="buergeramt")
    try:
        oa.key = "changed"
    except FrozenInstanceError:
        pass
    else:
        raise AssertionError("OthersAdminCardConfig must be frozen")
    print("base.py selfcheck OK (LensTileConfig / LensConfig / OthersAdminCardConfig)")
