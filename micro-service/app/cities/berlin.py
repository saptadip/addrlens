"""Berlin CityConfig — the values that were hard-coded in Ship A. Populated
verbatim from phase3/server.py so behaviour is unchanged (plan §Ship B).

When adding a new city (Ship C onwards), copy this file, rename, and change
every value. Run `CITY=<slug> python -m app.selfcheck` group-by-group per
plan §9.3 as you go.
"""
import re
from pathlib import Path

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

# Phase-1 killer datasets (Berlin BOD)
_WFS_FIRE          = "https://gdi.berlin.de/services/wfs/feuerwehr"
_WFS_TREES         = "https://gdi.berlin.de/services/wfs/baumbestand"
_WFS_QUIET         = "https://gdi.berlin.de/services/wfs/ruhigegebiete_2018"
_WFS_PROTECTION    = "https://gdi.berlin.de/services/wfs/erhaltungsverordnungsgebiete"
_WFS_POOLS         = "https://gdi.berlin.de/services/wfs/schwimmbaeder_berlin"
_WFS_SWIM_NATURAL  = "https://gdi.berlin.de/services/wfs/badegewaesser"

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
    wfs_output_format="application/json",

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

    # -- Phase 1: killer cards ------------------------------------------------
    fire_wfs_url=_WFS_FIRE,
    fire_stations_layer="feuerwehr:a_feuerwehr_standorte",
    fire_zones_layer="feuerwehr:b_feuerwehr_einsatzbereiche",
    fire_stations_field_map={
        "name": "wach_name", "type": "wach_typ", "address": "adresse",
        "phone_bf": "telefon_bf", "phone_ff": "telefon_ff", "zone_id": "eb_kurz",
    },
    fire_zones_field_map={"id": "eb", "code": "eb_kurz", "name": "eb_name"},

    trees_wfs_url=_WFS_TREES,
    trees_layer="baumbestand:strassenbaeume",
    trees_field_map={
        "species_de": "art_dtsch", "genus_de": "gattung_deutsch", "group": "art_gruppe",
        "height": "baumhoehe", "age": "standalter", "planting_year": "pflanzjahr",
        "street": "strname",
    },
    trees_radius_m=200,

    quiet_wfs_url=_WFS_QUIET,
    quiet_layer="ruhigegebiete_2018:ruhigegeb2018_2023",
    quiet_field_map={"name": "name", "kind": "g_art",
                     "size_ha": "groesse_ha", "id": "gebnr"},

    protection_wfs_url=_WFS_PROTECTION,
    protection_em_layer="erhaltungsverordnungsgebiete:erhaltgeb_em",
    protection_es_layer="erhaltungsverordnungsgebiete:erhaltgeb_es",
    protection_field_map={
        "name": "gebietsname", "code": "schluessel", "in_force": "f_in_kraft",
        "district": "bezirk", "size_ha": "fl_ha",   # note: `es` layer uses fl_in_ha; loader tries both.
    },

    pools_wfs_url=_WFS_POOLS,
    pools_layer="schwimmbaeder_berlin:schwimmbaeder",
    pools_field_map={
        "name": "name_des_schwimmbads", "address": "adresse",
        "postcode": "postleitzahl", "district": "bezirk",
        "category": "badkategorie", "website": "link_zum_bad",
        "hours_hint": "hinweis_zu_oeffnungszeiten",
    },
    swim_natural_wfs_url=_WFS_SWIM_NATURAL,
    swim_natural_layer="badegewaesser:aa_badestellen",
    swim_natural_field_map={
        "name": "badegewaes", "eu_rating": "eu_einst",
        "website": "link", "cyano": "cyano",
    },

    # -- Connectivity ---------------------------------------------------------
    # S-Bahn + U-Bahn come from the vendored VBB CSV (regenerate via
    # scripts/refresh_vbb.py). Tram comes from a BOD WFS at boot.
    stations_data_path=str(Path(__file__).resolve().parent / "data" / "vbb_berlin_su.csv"),
    tram_wfs_url="https://gdi.berlin.de/services/wfs/oepnv_ungestoert",
    tram_layer="oepnv_ungestoert:b_tramstopp",
    tram_field_map={"name": "hstname"},

    # Regional-rail stations Berlin RE/RB trains actually stop at. Curated
    # because VBB doesn't tag regional-rail mode explicitly, and the set is
    # small + stable enough that a curated list is cleaner than a GTFS join.
    #
    # ADDING A NEW STATION:
    #   python -m scripts.refresh_vbb --find "<name>"
    # copies coords straight from the same VBB source used for S/U-Bahn.
    # Then paste `(name, lat, lon)` into the tuple below. Ordering doesn't
    # matter — the app sorts by distance per request.
    regional_rail_stations=(
        ("S+U Berlin Hauptbahnhof",           52.525847, 13.368924),
        ("S Ostbahnhof",                      52.510331, 13.435086),
        ("S Südkreuz",                        52.475502, 13.365552),
        ("S Spandau",                         52.534798, 13.197477),
        ("S+U Gesundbrunnen",                 52.548637, 13.388372),
        ("S+U Zoologischer Garten",           52.506921, 13.332707),
        ("S+U Lichtenberg",                   52.510672, 13.498359),
        ("S Ostkreuz",                        52.503113, 13.469221),
        ("S Wannsee",                         52.421725, 13.178932),
        ("S Charlottenburg",                  52.504732, 13.303862),
        ("S+U Jungfernheide",                 52.530452, 13.300124),
        ("S Karow",                           52.615755, 13.470081),
    ),

    # BER — public landmark, hard-coded coord.
    airport={"name": "Berlin Brandenburg Airport (BER)",
             "iata": "BER", "lat": 52.3667, "lon": 13.5033},

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
        "sbahn":         "VBB / Koordinaten der Zugangsmöglichkeiten zu Stationen (CC-BY-4.0)",
        "ubahn":         "VBB / Koordinaten der Zugangsmöglichkeiten zu Stationen (CC-BY-4.0)",
        "tram":          "Geoportal Berlin / BVG Ungestörtes ÖPNV-Netz — Straßenbahnhaltestellen (dl-de/by-2.0)",
        "regional_rail": "VBB / Koordinaten der Zugangsmöglichkeiten zu Stationen (CC-BY-4.0)",
        "airport":       "Berlin Brandenburg Airport (BER) — public landmark",
        "fire":          "Geoportal Berlin / Feuerwehr Standorte und Einsatzbereiche (dl-de/zero-2.0)",
        "trees":         "Geoportal Berlin / Baumbestand Berlin — Straßenbäume (dl-de/zero-2.0)",
        "quiet_zone":    "Geoportal Berlin / Ruhige Gebiete und innerstädtische Erholungsflächen 2018 (dl-de/by-2.0)",
        "protection":    "Geoportal Berlin / Erhaltungsverordnungsgebiete § 172 BauGB (dl-de/zero-2.0)",
        "pools":         "Geoportal Berlin / Schwimmbäder der Berliner Bäder-Betriebe (dl-de/zero-2.0)",
        "natural_swim":  "Geoportal Berlin / Badegewässerqualität (CC-BY-4.0) · LAGeSo",
    },
)
