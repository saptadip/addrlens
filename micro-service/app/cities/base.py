"""CityConfig — the one place city-specific facts live. Every `core/` function
takes one of these instead of reading hard-coded constants (plan §2).

Ship B introduces the type; Berlin's values are in `berlin.py`. Ship C adds
`hamburg.py`. All future cities copy the same shape.

Field maps translate the canonical name the app uses ("name", "capacity", …)
into the per-city WFS property name ("e_name", "e_platz", …). Keep the
canonical keys stable across cities — that's the whole point.
"""
from __future__ import annotations

from dataclasses import dataclass
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

    # Local-language glossary — applied by core/gloss.py after inference-service
    # returns text. Each entry is (compiled_regex, english_gloss). See phase3
    # GERMAN_GLOSS for the Berlin seed.
    bilingual_glossary: list

    # Sanity bbox for input coord (south, west, north, east)
    overpass_bbox: tuple

    # Provenance strings, one per public-facing dataset. Keys used by the app:
    #   "catchment", "schools", "addresses", "kitas", "hospitals",
    #   "fountains", "playgrounds", "parks", "noise".
    # Full string including licence tag; the app just concatenates when a
    # response mixes sources.
    attribution: dict
