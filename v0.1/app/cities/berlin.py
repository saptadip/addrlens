"""Berlin CityConfig — the values that were hard-coded in Ship A. Populated
verbatim from phase3/server.py so behaviour is unchanged (plan §Ship B).

When adding a new city (Ship C onwards), copy this file, rename, and change
every value. Run `CITY=<slug> python -m app.selfcheck` group-by-group per
plan §9.3 as you go.
"""
import os
import re
from pathlib import Path

from app.cities.base import CityConfig, LensConfig, LensTileConfig

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
# Phase 2 (Umweltatlas)
_WFS_AIR           = "https://gdi.berlin.de/services/wfs/ua_luftreinhalteplan_2018_2025"
_WFS_HEAT          = "https://gdi.berlin.de/services/wfs/ua_klimabewertung_2022"
# Spec B — Bureaucracy lens
_WFS_BEZIRKE       = "https://gdi.berlin.de/services/wfs/alkis_bezirke"        # layer: alkis_bezirke:bezirksgrenzen (verified via GetCapabilities)
_BUERGERAEMTER_URL = "https://service.berlin.de/standorte/geojson/buergeramt"  # service.berlin.de REST GeoJSON (no WFS published); sentinel layer "_geojson" triggers custom loader

# Base URLs (all under the Berlin Geoportal gdi.berlin.de)
_WFS_SCHULEN = "https://gdi.berlin.de/services/wfs/schulen"
_WFS_ADR     = "https://gdi.berlin.de/services/wfs/adressen_berlin"
_WFS_KITA    = "https://gdi.berlin.de/services/wfs/kita"
_WFS_KKH     = "https://gdi.berlin.de/services/wfs/krankenhaeuser"
_WFS_BRUNNEN = "https://gdi.berlin.de/services/wfs/trinkwasserbrunnen"
_WFS_GRUEN   = "https://gdi.berlin.de/services/wfs/gruenanlagen"
_WFS_NOISE   = "https://gdi.berlin.de/services/wfs/ua_stratlaerm_2022"

# --- Bureaucracy lens curated directories (Spec B) -------------------------
# Small, stable federal-adjacent directories. Hardcoded here per §14.4
# "BOD first, curated fallback" — the Berlin Geoportal doesn't cleanly
# publish these; curated is the honest choice for stable directories.
# ponytail: refresh annually or when a Bezirk merger/rename happens.

# One Standesamt per Bezirk (12 total). Names + addresses from berlin.de.
# Coordinates rounded to 4 decimals (~11 m precision). Verify at
# implementation time via Nominatim or Berlin's own address lookup.
_STANDESAMTS_BY_BEZIRK = {
    "Mitte":                          {"name": "Standesamt Mitte",
                                        "address": "Karl-Marx-Allee 31, 10178 Berlin",
                                        "lat": 52.5197, "lon": 13.4180},
    "Friedrichshain-Kreuzberg":       {"name": "Standesamt Friedrichshain-Kreuzberg",
                                        "address": "Schlesische Str. 27a, 10997 Berlin",
                                        "lat": 52.5008, "lon": 13.4460},
    "Pankow":                         {"name": "Standesamt Pankow",
                                        "address": "Fröbelstr. 17, 10405 Berlin",
                                        "lat": 52.5348, "lon": 13.4249},
    "Charlottenburg-Wilmersdorf":     {"name": "Standesamt Charlottenburg-Wilmersdorf",
                                        "address": "Otto-Suhr-Allee 100, 10585 Berlin",
                                        "lat": 52.5163, "lon": 13.3020},
    "Spandau":                        {"name": "Standesamt Spandau",
                                        "address": "Carl-Schurz-Str. 2/6, 13597 Berlin",
                                        "lat": 52.5350, "lon": 13.2010},
    "Steglitz-Zehlendorf":            {"name": "Standesamt Steglitz-Zehlendorf",
                                        "address": "Kirchstr. 1/3, 14163 Berlin",
                                        "lat": 52.4319, "lon": 13.2596},
    "Tempelhof-Schöneberg":           {"name": "Standesamt Tempelhof-Schöneberg",
                                        "address": "Rathausstr. 27, 12105 Berlin",
                                        "lat": 52.4685, "lon": 13.3888},
    "Neukölln":                       {"name": "Standesamt Neukölln",
                                        "address": "Karl-Marx-Str. 83, 12040 Berlin",
                                        "lat": 52.4813, "lon": 13.4400},
    "Treptow-Köpenick":               {"name": "Standesamt Treptow-Köpenick",
                                        "address": "Alt-Köpenick 21, 12555 Berlin",
                                        "lat": 52.4459, "lon": 13.5765},
    "Marzahn-Hellersdorf":            {"name": "Standesamt Marzahn-Hellersdorf",
                                        "address": "Riesaer Str. 94, 12627 Berlin",
                                        "lat": 52.5390, "lon": 13.6055},
    "Lichtenberg":                    {"name": "Standesamt Lichtenberg",
                                        "address": "Egon-Erwin-Kisch-Str. 106, 13059 Berlin",
                                        "lat": 52.5670, "lon": 13.5030},
    "Reinickendorf":                  {"name": "Standesamt Reinickendorf",
                                        "address": "Eichborndamm 215-239, 13437 Berlin",
                                        "lat": 52.5825, "lon": 13.3130},
}

# Finanzämter — ~17 offices across Berlin. Individual-income tax
# jurisdictions carve Berlin by street ranges, so this directory is a
# "starting point" (caveat on the lens tile carries this disclosure).
# ponytail: verify addresses at berlin.de/finanzaemter; annual refresh.
_FINANZAMTS = (
    {"name": "Finanzamt Charlottenburg",       "address": "Bismarckstr. 48, 10627 Berlin",
     "lat": 52.5075, "lon": 13.3060},
    {"name": "Finanzamt Friedrichshain-Kreuzberg", "address": "Möllendorffstr. 34, 10367 Berlin",
     "lat": 52.5225, "lon": 13.4550},
    {"name": "Finanzamt Lichtenberg",          "address": "Josef-Orlopp-Str. 62, 10365 Berlin",
     "lat": 52.5225, "lon": 13.4790},
    {"name": "Finanzamt Marzahn-Hellersdorf",  "address": "Allee der Kosmonauten 29, 10315 Berlin",
     "lat": 52.5305, "lon": 13.5265},
    {"name": "Finanzamt Mitte/Tiergarten",     "address": "Neue Jakobstr. 6-7, 10179 Berlin",
     "lat": 52.5140, "lon": 13.4160},
    {"name": "Finanzamt Neukölln",             "address": "Thiemannstr. 1, 12059 Berlin",
     "lat": 52.4680, "lon": 13.4530},
    {"name": "Finanzamt Pankow/Weißensee",     "address": "Storkower Str. 134, 10407 Berlin",
     "lat": 52.5290, "lon": 13.4560},
    {"name": "Finanzamt Prenzlauer Berg",      "address": "Storkower Str. 134, 10407 Berlin",
     "lat": 52.5290, "lon": 13.4560},
    {"name": "Finanzamt Reinickendorf",        "address": "Eichborndamm 208, 13437 Berlin",
     "lat": 52.5820, "lon": 13.3140},
    {"name": "Finanzamt Schöneberg",           "address": "Bundesallee 171, 10715 Berlin",
     "lat": 52.4820, "lon": 13.3335},
    {"name": "Finanzamt Spandau",              "address": "Nonnendammallee 15-21, 13599 Berlin",
     "lat": 52.5395, "lon": 13.2170},
    {"name": "Finanzamt Steglitz",             "address": "Schloßstr. 58-59, 12165 Berlin",
     "lat": 52.4570, "lon": 13.3260},
    {"name": "Finanzamt Tempelhof",            "address": "Tempelhofer Damm 234, 12099 Berlin",
     "lat": 52.4525, "lon": 13.3860},
    {"name": "Finanzamt Treptow-Köpenick",     "address": "Seelenbinderstr. 99, 12555 Berlin",
     "lat": 52.4570, "lon": 13.5770},
    {"name": "Finanzamt Wedding",              "address": "Osloer Str. 37, 13359 Berlin",
     "lat": 52.5540, "lon": 13.3800},
    {"name": "Finanzamt Wilmersdorf",          "address": "Volkslehrer- und Blissestr., 10713 Berlin",
     "lat": 52.4870, "lon": 13.3120},
    {"name": "Finanzamt Zehlendorf",           "address": "Martin-Buber-Str. 20, 14163 Berlin",
     "lat": 52.4330, "lon": 13.2540},
)

# Arbeitsagentur — Bundesagentur für Arbeit branches in Berlin.
# ~10 branches. Curated from arbeitsagentur.de.
_ARBEITSAGENTURS = (
    {"name": "Agentur für Arbeit Berlin Mitte",     "address": "Friedrichstr. 34, 10969 Berlin",
     "lat": 52.5063, "lon": 13.3900},
    {"name": "Agentur für Arbeit Berlin Nord",      "address": "Königin-Elisabeth-Str. 49, 14059 Berlin",
     "lat": 52.5290, "lon": 13.2880},
    {"name": "Agentur für Arbeit Berlin Süd",       "address": "Sonnenallee 282, 12057 Berlin",
     "lat": 52.4700, "lon": 13.4500},
    {"name": "Agentur für Arbeit Berlin Marzahn",   "address": "Allee der Kosmonauten 29, 12681 Berlin",
     "lat": 52.5410, "lon": 13.5910},
    {"name": "Agentur für Arbeit Berlin Neukölln",  "address": "Sonnenallee 282, 12057 Berlin",
     "lat": 52.4700, "lon": 13.4500},
    {"name": "Agentur für Arbeit Berlin Pankow",    "address": "Storkower Str. 118, 10407 Berlin",
     "lat": 52.5300, "lon": 13.4530},
    {"name": "Agentur für Arbeit Berlin Reinickendorf", "address": "Miraustr. 54, 13509 Berlin",
     "lat": 52.5900, "lon": 13.3320},
    {"name": "Agentur für Arbeit Berlin Spandau",   "address": "Altonaer Str. 70-72, 13581 Berlin",
     "lat": 52.5320, "lon": 13.2010},
    {"name": "Agentur für Arbeit Berlin Steglitz",  "address": "Kaiser-Wilhelm-Str. 1, 12247 Berlin",
     "lat": 52.4360, "lon": 13.3200},
    {"name": "Agentur für Arbeit Berlin Charlottenburg", "address": "Königin-Elisabeth-Str. 49, 14059 Berlin",
     "lat": 52.5290, "lon": 13.2880},
)

# LEA — Landesamt für Einwanderung, main office.
_LEA_OFFICE = {
    "name": "LEA Berlin — Landesamt für Einwanderung",
    "address": "Friedrich-Krause-Ufer 24, 13353 Berlin",
    "lat": 52.5450, "lon": 13.3616,
}

# --- Young Family lens (Spec A) --------------------------------------------
# Seven traffic-light tiles for families with kids under 6. Thresholds live
# per tile — every "why is this the tier" answer sits in one table here.
# Boundary convention: inclusive on the greener side (≤ green_m is green;
# > green_m is amber). See
# docs/superpowers/specs/2026-08-09-young-family-lens-design.md.
YOUNG_FAMILY_LENS: LensConfig = LensConfig(
    slug="young_family",
    label="Young Family (0–6)",
    audience_hint="For a family with kids under 6",
    tiles=(
        LensTileConfig(
            key="kita", label="Kita reachability", icon="kita",
            thresholds={"green_count": 3, "green_m": 400, "amber_m": 800},
        ),
        LensTileConfig(
            key="playground", label="Playground within stroller walk", icon="playground",
            thresholds={"green_m": 400, "amber_m": 800},
        ),
        LensTileConfig(
            key="pediatrician", label="Pediatrician within walk", icon="pediatrician",
            thresholds={"green_m": 800, "amber_m": 1500},
            caveat=("OSM community-tagged — inner-district coverage is good; "
                    "outer districts may under-report."),
        ),
        LensTileConfig(
            key="transit", label="Transit stop within walk", icon="transit",
            thresholds={"green_min": 5, "amber_min": 10},
            caveat=("Combines S-Bahn / U-Bahn / Tram (Berlin BOD + VBB) with the "
                    "nearest OSM-tagged bus stop. Tier is the shortest walk across "
                    "all four modes."),
        ),
        LensTileConfig(
            key="supermarket", label="Supermarket within walk", icon="cart",
            thresholds={"green_min": 5, "amber_min": 10},
            caveat=("OSM community-tagged — brand + hours coverage varies; "
                    "expect a small kiosk to look identical to a Rewe until you visit."),
        ),
        LensTileConfig(
            key="noise", label="Façade noise", icon="noise",
            thresholds={"green_db": 55, "amber_db": 60},
        ),
        LensTileConfig(
            key="heat", label="Summer heat", icon="heat",
            # Umweltatlas class strings — matched case-insensitively as substrings.
            thresholds={
                "green_classes": ("keine Belastung", "geringe Belastung"),
                "amber_classes": ("mäßige Belastung", "starke Belastung"),
            },
        ),
        LensTileConfig(
            key="air", label="Air quality (NO₂)", icon="air",
            # 20/40 tiers follow the app's existing NO₂ card thresholds
            # (§14.9 tier-color convention), not WHO 2021 strictly (10 μg/m³).
            thresholds={"green_ugm3": 20, "amber_ugm3": 40},
        ),
        LensTileConfig(
            key="refuge", label="Quiet / green refuge nearby", icon="refuge",
            # Composite: quiet zone distance OR crown coverage %. OR-forgiving
            # at both tiers so losing one signal still yields a real tier.
            thresholds={
                "green_quiet_m": 400,  "amber_quiet_m": 1000,
                "green_crown_pct": 25, "amber_crown_pct": 15,
            },
        ),
        LensTileConfig(
            key="gesix", label="Neighbourhood profile", icon="gesix",
            thresholds={},                       # quintiles derived from the Senate's own distribution
            caveat=("Senate GESIx 2022 composite — 20 employment / social / health "
                    "indicators aggregated per Planungsraum (~10k residents). "
                    "Reflects the polygon around your flat, not the individual "
                    "building. Refreshed by the Senate every 3–5 years."),
        ),
    ),
)

# --- Bureaucracy lens (Spec B) --------------------------------------------
# Five traffic-light tiles for Berlin public-admin infrastructure.
# Boundary convention: inclusive on greener side (≤ 15 min = green;
# > 15 min = amber). See
# docs/superpowers/specs/2026-08-09-bureaucracy-lens-design.md.
BUREAUCRACY_LENS: LensConfig = LensConfig(
    slug="bureaucracy",
    label="Bureaucracy",
    audience_hint="Public admin offices you'll visit as a new arrival",
    tiles=(
        LensTileConfig(
            key="buergeramt", label="Bürgeramt (Anmeldung)", icon="buergeramt",
            thresholds={"green_min": 15, "amber_min": 30},
            caveat="Berlin lets you book any Bürgeramt for Anmeldung — not restricted by PLZ.",
        ),
        LensTileConfig(
            key="finanzamt", label="Finanzamt (Tax Office)", icon="finanzamt",
            thresholds={"green_min": 15, "amber_min": 30},
            caveat=("Your assigned Finanzamt is set by Steuernummer, not address alone. "
                    "Nearest office shown as a starting point."),
        ),
        LensTileConfig(
            key="standesamt", label="Standesamt (Marriage / Birth)", icon="standesamt",
            thresholds={"green_min": 15, "amber_min": 30},
        ),
        LensTileConfig(
            key="lea", label="LEA (Residence Permit)", icon="lea",
            thresholds={"green_min": 15, "amber_min": 30},
            caveat=("Specialty branches exist for skilled workers, students, and refugees — "
                    "check LEA Berlin's website for the right one."),
        ),
        LensTileConfig(
            key="arbeitsagentur", label="Arbeitsagentur (Employment Agency)", icon="arbeitsagentur",
            thresholds={"green_min": 15, "amber_min": 30},
        ),
    ),
)

# --- Newcomer lens (Spec E) ------------------------------------------------
# Six traffic-light tiles for English-speaking expats in their first 90 days.
# Threshold convention: inclusive on the greener side (≤ green_m is green).
# See docs/superpowers/specs/2026-08-12-newcomer-lens-design.md.
NEWCOMER_LENS: LensConfig = LensConfig(
    slug="newcomer",
    label="Newcomer",
    audience_hint="First 90 days in Berlin — registration, transit, English-friendly services.",
    tiles=(
        LensTileConfig(
            key="buergeramt", label="Bürgeramt reach", icon="buergeramt",
            thresholds={"green_m": 1500, "amber_m": 3000},
        ),
        LensTileConfig(
            key="rail_transit", label="Rail Transit", icon="transit",
            thresholds={"sbahn_m": 800, "ubahn_m": 500, "any_rail_m": 1200},
        ),
        LensTileConfig(
            key="tram_transit", label="Tram Transit", icon="transit",
            thresholds={"green_m": 500, "amber_m": 1000},
        ),
        LensTileConfig(
            key="bus_transit", label="Bus Transit", icon="transit",
            thresholds={"green_m": 300, "amber_m": 600},
        ),
        LensTileConfig(
            key="intl_food", label="International food", icon="intl_food",
            thresholds={"radius_m": 800, "green_count": 5, "amber_count": 2},
        ),
        LensTileConfig(
            key="coworking", label="Coworking + Wi-Fi cafés", icon="coworking",
            thresholds={"radius_m": 1000, "green_count": 3, "amber_count": 1},
        ),
        LensTileConfig(
            key="english_clinic", label="English-speaking clinic", icon="english_clinic",
            thresholds={"green_m": 1200, "amber_m": 3000},
            caveat="OSM community-tagged — inner-district coverage good, outer may under-report",
        ),
        LensTileConfig(
            key="language_school", label="German classes", icon="language_school",
            thresholds={"green_m": 1500, "amber_m": 3500},
            caveat="Covers VHS branches + private Sprachschulen tagged in OSM; small independent schools may be missing.",
        ),
        LensTileConfig(
            key="library", label="Public library", icon="library",
            thresholds={"green_m": 1000, "amber_m": 2500},
        ),
        LensTileConfig(
            key="packstation", label="Parcel pickup", icon="packstation",
            thresholds={"green_m": 400, "amber_m": 1000},
            caveat="DHL Packstation + Deutsche Post branches from OSM; DHL Packstation locker moves may take a few weeks to reflect.",
        ),
        LensTileConfig(
            key="wochenmarkt", label="Open market", icon="wochenmarkt",
            thresholds={"green_m": 800, "amber_m": 2000},
            caveat="Only permitted weekly markets; closures may take a season to disappear from the feed.",
        ),
        LensTileConfig(
            key="nightlife_density", label="Nightlife density", icon="nightlife",
            thresholds={},   # numeric-only — no tier logic, no verdict
            caveat="Numeric only — no green/amber/red verdict. Dense nightlife is a positive for some newcomers and a negative for others; the noise tile covers the sound-level side of the same signal.",
        ),
        LensTileConfig(
            key="gesix_newcomer", label="Neighbourhood profile", icon="gesix",
            thresholds={},   # shape-only — no tier logic
        ),
    ),
)

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

    # Phase 2 Umweltatlas: NO2 baseline (2020) per street segment + PET
    # bioclimate day classification per residential block (Klimabewertung).
    air_wfs_url=_WFS_AIR,
    air_layer="ua_luftreinhalteplan_2018_2025:trend_szenario",
    air_field_map={
        "street":  "name",
        "no2":     "no2_2020",       # µg/m³ annual mean
        "index":   "index_2020",     # combined NO2 + PM10 index
        "traffic": "dtv_2020",       # cars/day
        "length":  "laenge",         # segment length (m)
    },
    heat_wfs_url=_WFS_HEAT,
    heat_layer="ua_klimabewertung_2022:cb_ua_phk_bioklim_siedl_tag_2022",
    heat_field_map={
        "day_class": "pet14h_tag_klar",   # PET class at 14:00 (e.g. "> 33 °C - <= 35 °C - mäßige Belastung")
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
        "air":           "Geoportal Berlin / Umweltatlas — Luftreinhalteplan 2018–2025 (Trend-Szenario 2020) (dl-de/zero-2.0)",
        "heat":          "Geoportal Berlin / Umweltatlas — Klimabewertungskarten 2022 (Bioklima Tag) (dl-de/zero-2.0)",
        "bezirksgrenzen": "Geoportal Berlin / Bezirksgrenzen (dl-de/by-2.0)",
        "gesix":          "Senatsverwaltung für Wissenschaft, Gesundheit, Pflege und Gleichstellung / Gesundheits- und Sozialstrukturatlas — GESIx 2022 (dl-de/zero-2.0)",
        "buergeramt":     "Berlin ServicePortal / Bürgerämter-Standorte (service.berlin.de)",
        "finanzamt":      "Curated from berlin.de Finanzamt-Verzeichnis (public reference)",
        "standesamt":     "Curated from berlin.de Standesamt-Verzeichnis (public reference)",
        "lea":            "Curated from Landesamt für Einwanderung Berlin (public reference)",
        "arbeitsagentur": "Curated from Bundesagentur für Arbeit Berlin-Brandenburg (public reference)",
    },
    # Geofabrik weekly snapshot lives at data/osm/berlin-amenities.json.
    # Env override for prod: OSM_LOCAL_PATH=/mnt/osm/berlin-amenities.json.
    osm_local_path=os.environ.get("OSM_LOCAL_PATH", "data/osm/berlin-amenities.json"),
    # OSM addresses extracted by scripts/refresh_osm_amenities.py; feeds
    # /api/suggest. Env override for prod: ADDRESS_LOCAL_PATH.
    address_local_path=os.environ.get("ADDRESS_LOCAL_PATH", "data/osm/berlin-addresses.json"),

    # GESIx 2022 — Senate's neighbourhood health & social composite index
    # per Planungsraum. 447 polygons total. Published 2022, refresh cadence
    # ~3-5 years. dl-de/zero-2.0 (no attribution burden).
    gesix_wfs_url="https://gdi.berlin.de/services/wfs/gssa_gesix2022",
    gesix_layer="gssa_gesix2022:gssa_gesix2022",

    young_family_lens=YOUNG_FAMILY_LENS,
    newcomer_lens=NEWCOMER_LENS,

    # --- Spec B: Bureaucracy lens ---------------------------------
    bezirksgrenzen_wfs_url=_WFS_BEZIRKE,
    bezirksgrenzen_layer="alkis_bezirke:bezirksgrenzen",   # verified via GetCapabilities; namgem = Bezirk name
    bezirksgrenzen_field_map={"name": "namgem"},           # props: name, gem, namgem, namlan, lan
    buergeramt_wfs_url=_BUERGERAEMTER_URL,
    buergeramt_layer="_geojson",                           # sentinel: service.berlin.de REST GeoJSON (no WFS for Bürgerämter on gdi.berlin.de)
    buergeramt_field_map={"name": "name", "address": "address", "website": "website"},
    finanzamts=_FINANZAMTS,
    standesamts_by_bezirk=_STANDESAMTS_BY_BEZIRK,
    arbeitsagenturs=_ARBEITSAGENTURS,
    lea_office=_LEA_OFFICE,
    bureaucracy_lens=BUREAUCRACY_LENS,
)

if __name__ == "__main__":
    from app.cities.berlin import BERLIN, NEWCOMER_LENS
    assert BERLIN.newcomer_lens is NEWCOMER_LENS
    assert BERLIN.buergeramt_wfs_url is not None    # Spec B: WFS already wired; not None in Berlin
    keys = [t.key for t in BERLIN.newcomer_lens.tiles]
    assert keys == ["buergeramt", "transit_newcomer", "intl_food",
                    "coworking", "english_clinic",
                    "language_school", "library", "packstation", "wochenmarkt",
                    "nightlife_density",
                    "gesix_newcomer"], keys
    assert "buergeramt" in BERLIN.attribution
    print("selfcheck ok: NEWCOMER_LENS wired")
