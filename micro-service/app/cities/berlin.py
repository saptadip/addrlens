"""Berlin CityConfig — the values that were hard-coded in Ship A. Populated
verbatim from phase3/server.py so behaviour is unchanged (plan §Ship B).

When adding a new city (Ship C onwards), copy this file, rename, and change
every value. Run `CITY=<slug> python -m app.selfcheck` group-by-group per
plan §9.3 as you go.
"""
import re

from app.cities.base import CityConfig

# Order matters: longer/multi-word forms first so "freier Träger" is matched
# before bare "Träger" (see phase3/server.py:GERMAN_GLOSS).
_BERLIN_GLOSSARY = [
    (re.compile(r"\bfreie[rnms]?\s+Träger\b"),           "a non-profit or private provider"),
    (re.compile(r"\bEigenbetrieb\b"),                     "city-run"),
    (re.compile(r"\bTräger\b"),                           "operator"),
    (re.compile(r"\bSituationsansatz\b"),                 "a child-led Berlin pedagogy"),
    (re.compile(r"\bSituationssatz\b"),                   "a child-led Berlin pedagogy"),  # common model misspelling
    (re.compile(r"\bGrundschule[n]?\b"),                  "primary school"),
    (re.compile(r"\bStaatliche Europa-Schule Berlin\b"),  "state bilingual school program"),
    (re.compile(r"\bSESB\b"),                             "state bilingual school program"),
    (re.compile(r"\bKita[s]?\b"),                         "daycare"),
]

_SESB_GRUNDSCHULEN = {
    "aziz-nesin": "German-Turkish",
    "charles-dickens": "German-English",
    "christian-morgenstern": "German-Russian",
    "finow": "German-Italian",
    "homer": "German-Greek",
    "hunsruck": "German-Turkish",
    "joan-miro": "German-Spanish",
    "judith-kerr": "German-English",
    "kastanienbaum": "German-French",
    "konrad-duden": "German-Polish",
    "markische": "German-French",
    "neumark": "German-Portuguese",
    "regenbogen": "German-Portuguese",
    "wedding-grundschule": "German-French",
}

# Base URLs (all under the Berlin Geoportal gdi.berlin.de)
_WFS_SCHULEN = "https://gdi.berlin.de/services/wfs/schulen"
_WFS_ADR     = "https://gdi.berlin.de/services/wfs/adressen_berlin"
_WFS_KITA    = "https://gdi.berlin.de/services/wfs/kita"
_WFS_KKH     = "https://gdi.berlin.de/services/wfs/krankenhaeuser"
_WFS_BRUNNEN = "https://gdi.berlin.de/services/wfs/trinkwasserbrunnen"
_WFS_GRUEN   = "https://gdi.berlin.de/services/wfs/gruenanlagen"
_WFS_NOISE   = "https://gdi.berlin.de/services/wfs/ua_stratlaerm_2022"

BERLIN = CityConfig(
    slug="berlin",
    display_name="Berlin",
    default_center=(52.5200, 13.4050),

    geocoder="wfs",
    geocoder_wfs_url=_WFS_ADR,
    geocoder_layer="adressen_berlin:adressen_berlin",
    geocoder_field_map={"street": "str_name", "hnr": "hnr", "plz": "plz"},

    catchment_wfs_url=_WFS_SCHULEN,
    catchment_layer="schulen:schulen_esb",
    catchment_field_map={"id": "esb", "district": "bezname"},

    schools_wfs_url=_WFS_SCHULEN,
    schools_layer="schulen:schulen",
    schools_field_map={
        "name": "schulname", "id": "bsn", "type": "schulart",
        "public_flag": "traeger",
        "street": "strasse", "hnr": "hausnr", "plz": "plz",
        "phone": "telefon", "website": "internet",
        "school_year": "schuljahr",
    },
    schools_public_value="öffentlich",
    schools_primary_types=frozenset({
        "Grundschule", "Gemeinschaftsschule", "Kombinierte allgemein bildende Schule",
    }),
    schools_intl_keywords=("international", "english", "american", "british",
                           "bilingual", "bilinguale", "jfk", "kennedy", "europa"),
    bilingual_schools=_SESB_GRUNDSCHULEN,

    kita_wfs_url=_WFS_KITA,
    kita_layer="kita:kita",
    kita_field_map={
        "name": "e_name", "capacity": "e_platz",
        "operator_type": "t_art", "approach": "ang_1",
    },

    hospital_wfs_url=_WFS_KKH,
    hospital_layers=(
        ("krankenhaeuser:plankrankenhaeuser",   "plan"),
        ("krankenhaeuser:weitere_krankenhaeuser", "weitere"),
    ),
    hospital_field_map={
        "name_primary": "kkh_standort", "name_alt1": "name", "name_alt2": "kkh",
        "beds": "betten_insgesamt", "beds_alt": "betten",
        "traeger": "kkh",
        "ortsteil": "gc_ortsteil",
        "fachabteilungen": "fachabteilungen",
    },
    hospital_radius_m=2000,
    hospital_match_m=500,

    fountains_wfs_url=_WFS_BRUNNEN,
    fountains_layer="trinkwasserbrunnen:trinkwasserbrunnen",
    fountains_field_map={
        "seasonal": "einschraenkungen", "bezirk": "bezirk",
        "type": "trinkbrunnenart", "location": "standort",
    },

    green_wfs_url=_WFS_GRUEN,
    parks_layer="gruenanlagen:gruenanlagen",
    playgrounds_layer="gruenanlagen:spielplaetze",

    noise_wfs_url=_WFS_NOISE,
    noise_layer="ua_stratlaerm_2022:aa_fp_gesamt2022",
    noise_field_map={
        "total_den": "ges_den", "road_den": "str_den",
        "rail_den":  "sch_den", "air_den":  "flg_den",
        "total_n":   "ges_n",   "road_n":   "str_n",
        "rail_n":    "sch_n",   "air_n":    "flg_n",
    },
    noise_year=2022,

    bilingual_glossary=_BERLIN_GLOSSARY,

    # Rough Berlin bbox with a small margin. Sourced from OSM city-boundary relation.
    overpass_bbox=(52.33, 13.08, 52.68, 13.76),

    attribution={
        "catchment":   "Geoportal Berlin / Schulen (dl-de/zero-2.0)",
        "schools":     "Geoportal Berlin / Schulen (dl-de/zero-2.0)",
        "addresses":   "Geoportal Berlin / Adressen Berlin (dl-de/by-2.0)",
        "kitas":       "Geoportal Berlin / Kindertagesstätten (dl-de/by-2.0)",
        "hospitals":   "Geoportal Berlin / Krankenhäuser (dl-de/by-2.0)",
        "fountains":   "Geoportal Berlin / Trinkwasserbrunnen (dl-de/by-2.0) · Betrieb: Berliner Wasserbetriebe",
        "playgrounds": "Geoportal Berlin / Grünanlagen — Spielplätze (dl-de/by-2.0)",
        "parks":       "Geoportal Berlin / Grünanlagen — Grünanlagen (dl-de/by-2.0)",
        "noise":       "Geoportal Berlin / Strategische Lärmkarten 2022 — Fassadenpegel gesamt (dl-de/by-2.0)",
    },
)
