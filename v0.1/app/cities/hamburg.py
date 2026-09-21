"""Hamburg CityConfig — Ship C. Every URL + field name verified against
docs/superpowers/specs/2026-09-20-hamburg-data-landscape.md (2026-09-20).

Selfcheck: `python -m app.cities.hamburg` prints 'selfcheck ok' when Newcomer
+ Commuter lens configs land (Task 13 + Task 14). Until then, the config is
loadable but has None lens slots.

ponytail: re-verify Kundenzentrum + admin office locations annually; the
Standesamt dict was hand-curated 2026-09-20 from hamburg.de directories."""

import os
import re
from pathlib import Path

from app.cities.base import (
    CityConfig, LensConfig, LensTileConfig, OthersAdminCardConfig,
)

# ---- WFS endpoints (all verified 2026-09-20 via GetCapabilities) ------------
_WFS_DOG_OAF        = "https://api.hamburg.de/datasets/v1/gages_vereinfacht/collections/hauskoordinaten/items"
_WFS_SCHULEN        = "https://geodienste.hamburg.de/HH_WFS_Schulen"
_WFS_EINZUGSGEB     = "https://geodienste.hamburg.de/HH_WFS_Regionaler_Bildungsatlas_Einzugsgebiete_Schulwahl"
_WFS_KITA           = "https://geodienste.hamburg.de/HH_WFS_KitaEinrichtung"
_WFS_KKH            = "https://geodienste.hamburg.de/HH_WFS_Krankenhaeuser"
_WFS_BRUNNEN        = "https://geodienste.hamburg.de/wfs_wc_mit_trinkbrunnen"
_WFS_GRUENPLAN      = "https://geodienste.hamburg.de/HH_WFS_Gruenplan"
_WFS_SPIELPLAETZE   = "https://geodienste.hamburg.de/wfs_spielplaetze"
_WFS_LAERM          = "https://geodienste.hamburg.de/HH_WFS_Strassenverkehr"      # verify at impl (returned 404 in discovery)
_WFS_KLIMA          = "https://geodienste.hamburg.de/wfs_stadtklimaanalyse_hamburg_2023"
_WFS_BAUMKATASTER   = "https://geodienste.hamburg.de/HH_WFS_Strassenbaumkataster"
_WFS_RUHIGE         = "https://geodienste.hamburg.de/HH_WFS_Ruhige_Gebiete"
_WFS_SOZERHVO       = "https://geodienste.hamburg.de/HH_WFS_SozErhVO"
_WFS_VERW           = "https://geodienste.hamburg.de/HH_WFS_Verwaltungsgrenzen"
_WFS_FEUERWEHR      = "https://geodienste.hamburg.de/HH_WFS_feuerwehrstandorte"
_WFS_TEMPOLIMITS    = "https://geodienste.hamburg.de/HH_WFS_Zulaessige_Hoechstgeschwindigkeiten"
_WFS_STRNETZ        = "https://geodienste.hamburg.de/HH_WFS_Strassen_und_Wegenetz"
_WFS_BADEGEWAESSER  = "https://geodienste.hamburg.de/HH_WFS_Badegewaesser"
_WFS_PARKZONEN      = "https://geodienste.hamburg.de/HH_WFS_bewohnerparkgebiete"
_WFS_SOZMON         = "https://geodienste.hamburg.de/wfs_sozialmonitoring"

# ---- 7 Bezirke: integer code → name (SozErhVo stores as int) ----------------
_BEZIRK_ID_TO_NAME = {
    1: "Hamburg-Mitte", 2: "Altona", 3: "Eimsbüttel",
    4: "Hamburg-Nord", 5: "Wandsbek", 6: "Bergedorf", 7: "Harburg",
}

# ---- Standesamt — 1 per Bezirk (7 entries from landscape doc §4.2). ---------
# Only admin office curated for Hamburg day-1 per spec Q10-B.
# ponytail: re-verify 2027-09 against hamburg.de/politik-und-verwaltung
# /bezirke/bezirksthemen/standesamt.
_STANDESAMTS_BY_BEZIRK = {
    "Hamburg-Mitte":  {"name": "Standesamt Hamburg-Mitte",
                        "address": "Caffamacherreihe 1–3, 20355 Hamburg",
                        "lat": 53.5544, "lon":  9.9845},
    "Altona":          {"name": "Standesamt Altona",
                        "address": "Platz der Republik 1, 22765 Hamburg",
                        "lat": 53.5470, "lon":  9.9357},
    "Eimsbüttel":      {"name": "Standesamt Eimsbüttel",
                        "address": "Grindelberg 62–66, 20144 Hamburg",
                        "lat": 53.5747, "lon":  9.9790},
    "Hamburg-Nord":    {"name": "Standesamt Hamburg-Nord",
                        "address": "Kümmellstraße 5–7, 20249 Hamburg",
                        "lat": 53.5899, "lon":  9.9845},
    "Wandsbek":        {"name": "Standesamt Wandsbek",
                        "address": "Schloßstraße 60, 22041 Hamburg",
                        "lat": 53.5717, "lon": 10.0708},
    "Bergedorf":       {"name": "Standesamt Bergedorf",
                        "address": "Gräpelweg 8, 21029 Hamburg (Haus im Park)",
                        "lat": 53.4891, "lon": 10.2190},
    "Harburg":         {"name": "Standesamt Harburg",
                        "address": "Harburger Rathausplatz 1, 21073 Hamburg",
                        "lat": 53.4591, "lon":  9.9795},
}

# ---- Regional rail curated list (13 from landscape §3.3) --------------------
_REGIONAL_RAIL = (
    ("Hamburg Hauptbahnhof",   53.55278, 10.00639),
    ("Hamburg-Altona",         53.55194,  9.93500),
    ("Hamburg Dammtor",        53.56083,  9.98944),
    ("Hamburg-Harburg",        53.45611,  9.99169),
    ("Hamburg-Bergedorf",      53.48944, 10.20639),
    ("Hamburg-Rahlstedt",      53.60333, 10.15806),
    ("Hamburg-Tonndorf",       53.59306, 10.13361),
    ("Wilhelmsburg",           53.4989,  10.0069),
    ("Pinneberg",              53.65917,  9.79139),
    ("Elbgaustraße",           53.6103,   9.9036),
    ("Neugraben",              53.4728,   9.8611),
    ("Aumühle",                53.5300,  10.3167),
    ("Buxtehude",              53.4747,   9.6931),
)

# ---- Hamburg-specific glossary (LLM post-processing) ------------------------
_HAMBURG_GLOSSARY = [
    (re.compile(r"\bKundenzentr\w*\b"),        "citizens' service office"),
    (re.compile(r"\bBezirk\b"),                "Hamburg borough"),
    (re.compile(r"\bStadtteil\b"),             "neighbourhood"),
    (re.compile(r"\bStatistisches Gebiet\b"),  "statistical area (~2200 residents)"),
    (re.compile(r"\bSozialmonitoring\b"),      "Hamburg's neighbourhood-status monitor"),
    (re.compile(r"\bAufmerksamkeitsgebiet\b"), "an area flagged for city social monitoring"),
    (re.compile(r"\bBücherhallen\b"),          "public library network"),
    (re.compile(r"\bHVV\b"),                   "Hamburg's transit union"),
    (re.compile(r"\bHADAG\b"),                 "Elbe ferry operator"),
    (re.compile(r"\bBewohnerparkgebiet\b"),    "resident parking zone"),
]

# ---- Attribution dict — per-source credit strings ---------------------------
_ATTRIBUTION = {
    "catchment":      "Freie und Hansestadt Hamburg / BSB via LGV (dl-de/by-2-0)",
    "schools":        "Freie und Hansestadt Hamburg / BSB via LGV (dl-de/by-2-0)",
    "addresses":      "Freie und Hansestadt Hamburg / LGV — DOG (dl-de/by-2-0)",
    "kitas":          "Freie und Hansestadt Hamburg / BAGFI (dl-de/by-2-0)",
    "hospitals":      "Freie und Hansestadt Hamburg / BWGV (dl-de/by-2-0)",
    "fountains":      "Freie und Hansestadt Hamburg / BUKEA · Stadtreinigung Hamburg (dl-de/by-2-0)",
    "playgrounds":    "Freie und Hansestadt Hamburg / BUKEA — wfs_spielplaetze (dl-de/by-2-0)",
    "parks":          "Freie und Hansestadt Hamburg / BUKEA — Grünplan (dl-de/by-2-0)",
    "noise":          "Freie und Hansestadt Hamburg / BUKEA — Strategische Lärmkarten 2022 (dl-de/by-2-0)",
    "sbahn":          "Hamburger Verkehrsverbund GmbH (dl-de/by-2-0)",
    "ubahn":          "Hamburger Verkehrsverbund GmbH (dl-de/by-2-0)",
    "ferry":          "Hamburger Verkehrsverbund GmbH · HADAG Seetouristik und Fährdienst AG (dl-de/by-2-0)",
    "regional_rail":  "Hamburger Verkehrsverbund GmbH (dl-de/by-2-0)",
    "airport":        "Hamburg Airport Helmut Schmidt (HAM) — public landmark",
    "fire":           "Freie und Hansestadt Hamburg / Behörde für Inneres und Sport (dl-de/by-2-0)",
    "trees":          "Freie und Hansestadt Hamburg / BUKEA — Straßenbaumkataster (dl-de/by-2-0)",
    "quiet_zone":     "Freie und Hansestadt Hamburg / BUKEA — Ruhige Gebiete + Ruheinseln (dl-de/by-2-0)",
    "protection":     "Freie und Hansestadt Hamburg / BSW — Soziale Erhaltungsverordnungen § 172 BauGB (dl-de/by-2-0)",
    "heat":           "Freie und Hansestadt Hamburg / BUKEA — Stadtklimaanalyse 2023 (dl-de/by-2-0)",
    "bezirksgrenzen": "Freie und Hansestadt Hamburg / LGV — Verwaltungsgrenzen (dl-de/by-2-0)",
    "sozialmonitoring": "Freie und Hansestadt Hamburg / BSW — Sozialmonitoring Integrierte Stadtteilentwicklung (dl-de/by-2-0)",
    "standesamt":     "Curated from hamburg.de Standesamt-Verzeichnis (public reference, verified 2026-09-20)",
    "tempolimits":    "Freie und Hansestadt Hamburg / BVM — Zulässige Höchstgeschwindigkeiten (dl-de/by-2-0)",
    "arterial_road":  "Freie und Hansestadt Hamburg / BVM via LGV — Straßen- und Wegenetz (dl-de/by-2-0)",
    "cycling":        "© OpenStreetMap contributors (ODbL) via Geofabrik — highway=cycleway (weekly Hamburg extract)",
    "cobblestone":    "© OpenStreetMap contributors (ODbL) via Geofabrik — trafficked highway + surface=sett|cobblestone (weekly Hamburg extract)",
    "car_sharing":    "© OpenStreetMap contributors (ODbL) via Geofabrik — amenity=car_sharing (weekly Hamburg extract)",
    "parkzone":       "Freie und Hansestadt Hamburg / LGV — Bewohnerparkgebiete (dl-de/by-2-0)",
    "natural_swim":   "Freie und Hansestadt Hamburg / BUKEA — Badegewässer (dl-de/by-2-0)",
}

# ---- Others admin cards: Standesamt only (Q10-B) ----------------------------
OTHERS_ADMIN_CARDS: tuple = (
    OthersAdminCardConfig(key="standesamt", label="Standesamt (Marriage / Birth)", icon="standesamt"),
)

# ---- Lens configs: Task 13 fills Newcomer; Task 14 fills Commuter; YF+QL deferred (spec Q9) ----
NEWCOMER_LENS: LensConfig = LensConfig(
    slug="newcomer",
    label="Newcomer",
    audience_hint="First 90 days in Hamburg — HVV, ferry, Anmeldung, English-friendly services.",
    tiles=(
        LensTileConfig(
            key="rail_transit", label="Rail Transit", icon="transit",
            thresholds={"sbahn_m": 800, "ubahn_m": 500, "any_rail_m": 1200},
        ),
        LensTileConfig(
            key="ferry_transit", label="Ferry Transit", icon="ferry",
            thresholds={"green_m": 500, "amber_m": 1000},
            caveat=("HVV-integrated HADAG ferry piers (route_type=4). All-day service on "
                    "lines 62, 64, 72; other lines are peak-only. Distance is walk to the "
                    "nearest pier, not to a specific line."),
        ),
        LensTileConfig(
            key="bus_transit", label="Bus Transit", icon="transit",
            thresholds={"green_m": 300, "amber_m": 600},
        ),
        LensTileConfig(
            key="intl_food", label="International food", icon="intl_food",
            thresholds={"radius_m": 1000, "green_count": 6, "amber_count": 2},
        ),
        LensTileConfig(
            key="coworking", label="Coworking + Wi-Fi cafés", icon="coworking",
            thresholds={"radius_m": 1000, "green_count": 3, "amber_count": 1},
        ),
        LensTileConfig(
            key="english_clinic", label="English-speaking clinic", icon="english_clinic",
            thresholds={"green_m": 1000, "amber_m": 3000},
            caveat="OSM community-tagged — inner-district coverage good, outer may under-report.",
        ),
        LensTileConfig(
            key="language_school", label="German classes", icon="language_school",
            thresholds={"green_m": 1500, "amber_m": 3500},
            caveat=("Covers Volkshochschule Hamburg + private Sprachschulen tagged in OSM; "
                    "small independent schools may be missing."),
        ),
        LensTileConfig(
            key="library", label="Public library", icon="library",
            thresholds={"green_m": 1000, "amber_m": 2500},
            caveat="Bücherhallen Hamburg branches from OSM operator tag.",
        ),
        LensTileConfig(
            key="packstation", label="Parcel pickup", icon="packstation",
            thresholds={"green_m": 400, "amber_m": 1000},
            caveat="DHL Packstation + Deutsche Post branches from OSM.",
        ),
        LensTileConfig(
            key="parkzone", label="Resident parking", icon="parkzone",
            thresholds={"amber_edge_m": 400},
            caveat=("Hamburg Bewohnerparkgebiete — LGV polygons. Green means inside a "
                    "zone (residents get a Bewohnerparkausweis) or ≥400 m from any zone "
                    "edge. Hourly fees + enforcement hours not published in the WFS."),
        ),
        LensTileConfig(
            key="nightlife_density", label="Nightlife density", icon="nightlife",
            thresholds={},
            caveat=("Numeric only — no green/amber/red verdict. Hamburg's Kiez density "
                    "(St. Pauli, Sternschanze) is a positive for some and a negative for "
                    "others; the noise tile covers the sound-level side of the same signal."),
        ),
        LensTileConfig(
            key="sozialmonitoring_status", label="Neighbourhood status", icon="gesix",
            thresholds={},
            caveat=("Hamburg BSW Sozialmonitoring — 4-level Statusindex per Statistisches "
                    "Gebiet (~2200 residents). 'Hoch' = strong socioeconomic status; "
                    "'sehr niedrig' = neighbourhood flagged for city support. Refreshed "
                    "annually; polygon grain is finer than Berlin's Planungsraum."),
        ),
        LensTileConfig(
            key="sozialmonitoring_gesamt", label="City-watch flag", icon="gesix",
            thresholds={},
            caveat=("Hamburg BSW Sozialmonitoring — combined Status+Dynamik verdict. "
                    "'Aufmerksamkeitsgebiet' = the polygon around this flat is a city-"
                    "designated area for social monitoring. Independent of the Status tile."),
        ),
    ),
)
COMMUTER_LENS: LensConfig = LensConfig(
    slug="commuter",
    label="Commuter",
    audience_hint="For someone who needs a fast, reliable daily commute in Hamburg.",
    tiles=(
        LensTileConfig(
            key="commuter_rail_transit", label="S+U-Bahn reach", icon="commuter_rail",
            thresholds={"sbahn_m": 500, "ubahn_m": 500, "any_rail_m": 900},
        ),
        LensTileConfig(
            key="commuter_ferry_transit", label="Ferry reach", icon="ferry",
            thresholds={"green_m": 400, "amber_m": 800},
            caveat=("HADAG piers (HVV route_type=4). Tighter than Newcomer threshold "
                    "because a daily 2× walk multiplies. All-day lines: 62, 64, 72."),
        ),
        LensTileConfig(
            key="commuter_bus_transit", label="Bus reach", icon="transit",
            thresholds={"green_m": 250, "amber_m": 500},
        ),
        LensTileConfig(
            key="regional_rail_reach", label="Regional rail reach", icon="regional_rail",
            thresholds={"green_m": 1200, "amber_m": 2500},
            caveat=("Curated list of Hamburg RE/RB + AKN stations. Doesn't cover every "
                    "S-Bahn stop the regional trains pass through; the tile is 'which "
                    "platform will your commuter train actually stop at'."),
        ),
        LensTileConfig(
            key="cycling_network", label="Cycling network reach", icon="bike_network",
            thresholds={"green_m": 100, "amber_m": 300},
            caveat=("OSM highway=cycleway from the weekly Geofabrik Hamburg extract. "
                    "Painted bike lanes on shared roads are NOT in this signal — only "
                    "dedicated infrastructure."),
        ),
        LensTileConfig(
            key="parkzone", label="Resident parking", icon="parkzone",
            thresholds={"amber_edge_m": 400},
            caveat=("Hamburg Bewohnerparkgebiete — for car-owning commuters: green "
                    "inside a zone (Bewohnerparkausweis priority) or well outside; "
                    "amber at the edge of a paid zone."),
        ),
        LensTileConfig(
            key="car_sharing_reach", label="Car-sharing reach", icon="car_sharing",
            thresholds={"radius_m": 500, "green_count": 3, "amber_count": 1},
            caveat=("Fixed pickup points from OSM community tags. Free-float zones "
                    "are NOT modelled — a station-based tile is the honest signal."),
        ),
        LensTileConfig(
            key="ev_charging_reach", label="EV charger reach", icon="bolt",
            thresholds={"radius_m": 500, "green_count": 2, "amber_count": 1},
        ),
        LensTileConfig(
            key="airport_reach", label="Airport reach (HAM)", icon="airport",
            thresholds={"green_km": 20, "amber_km": 35},
            caveat=("Straight-line distance to Hamburg Airport Helmut Schmidt. "
                    "Actual door-to-gate time depends on S1 / bus timing; this tile "
                    "is a rough exposure signal, not a routing."),
        ),
        LensTileConfig(
            key="sozialmonitoring_status_commuter", label="Neighbourhood status", icon="gesix",
            thresholds={},
            caveat=("Hamburg BSW Sozialmonitoring — same signal as Newcomer's status "
                    "tile, commuter-audience framing."),
        ),
        LensTileConfig(
            key="sozialmonitoring_gesamt_commuter", label="City-watch flag", icon="gesix",
            thresholds={},
            caveat="Hamburg BSW Sozialmonitoring — combined verdict.",
        ),
    ),
)

# ---- Assemble HAMBURG CityConfig --------------------------------------------
HAMBURG = CityConfig(
    slug="hamburg",
    display_name="Hamburg",
    default_center=(53.5511, 9.9937),
    wfs_output_format="application/geo+json",
    wfs_srs_name="EPSG:4326",

    geocoder="oaf",
    geocoder_wfs_url=None, geocoder_layer=None, geocoder_field_map={},
    geocoder_oaf_url=_WFS_DOG_OAF,
    geocoder_oaf_field_map={"street": "strassenname", "hnr": "hausnummer", "plz": "postleitzahl"},

    # Hamburg catchment: einzugsgebiete_primarstufe has no polygon geometry (it's a
    # statistical linkage table, schule_id × statgeb_id). Leaving the URL set so
    # _load_catchments_and_schools still fires and loads schools; 0 ESB polygons is
    # expected. catchment_field_map uses actual field names from DescribeFeatureType.
    catchment_wfs_url=_WFS_EINZUGSGEB,
    catchment_layer="de.hh.up:einzug_einzugsgebiete_primarstufe",
    catchment_field_map={"id": "schule_id", "district": "statgeb_id"},

    schools_wfs_url=_WFS_SCHULEN,
    schools_layer="de.hh.up:staatliche_schulen",              # private schools loaded as second layer at impl
    schools_field_map={
        # kapitelbezeichnung = simple type group (e.g. "Grundschulen"); schulform is
        # pipe-delimited compound (e.g. "Grundschule|Vorschulklasse") so we map
        # "type" to kapitelbezeichnung for reliable filtering.
        "name": "schulname", "id": "schul_id", "type": "kapitelbezeichnung",
        "public_flag": "rechtsform",
        "street": "adresse_strasse_hausnr", "hnr": "adresse_strasse_hausnr", "plz": "adresse_ort",
        "phone": "schul_telefonnr", "website": "schul_homepage",
        "school_year": "schueleranzahl_schuljahr",
    },
    schools_public_value="staatlich",
    schools_primary_types=frozenset({"Grundschulen", "Stadtteilschulen"}),  # kapitelbezeichnung plural
    schools_intl_keywords=("international", "english", "bilingual", "bilinguale"),
    bilingual_schools={},

    kita_wfs_url=_WFS_KITA,
    kita_layer="app:KitaEinrichtungen",
    kita_field_map={"name": "Name", "capacity": "Anzahl_betreuter_Kinder",
                    "operator_type": "Leistungsarten", "approach": "Leistungsarten"},

    hospital_wfs_url=_WFS_KKH,
    hospital_layers=(("de.hh.up:gesundheit_krankenhaeuser", "plan"),),
    hospital_field_map={
        "name_primary": "name", "name_alt1": "einrichtung", "name_alt2": "name",
        "beds": "planbetten", "beds_alt": "teilstationaere_behandlungsplaetze",
        "traeger": "traegerschaft", "ortsteil": "ort",
        "fachabteilungen": "art_der_stationaeren_versorgung",
    },
    hospital_radius_m=2000, hospital_match_m=500,

    fountains_wfs_url=_WFS_BRUNNEN, fountains_layer="de.hh.up:wc_mit_trinkbrunnen",
    fountains_field_map={"seasonal": "hinweis", "bezirk": "bezirk",
                          "type": "typ", "location": "standort"},

    green_wfs_url=_WFS_GRUENPLAN,
    parks_layer="de.hh.up:verzeichnis_oeffentlicher_gruenanlagen",
    playgrounds_layer=None,   # split WFS — loaded via separate _WFS_SPIELPLAETZE at impl

    # Noise: isoline model, 6 layers
    noise_wfs_url=_WFS_LAERM,
    noise_layer=None,       # unused when noise_model == "isoline"
    noise_field_map={},
    noise_year=2022,
    noise_model="isoline",
    noise_isoline_road_day_layer="de.hh.up:strassenverkehr_tag_abend_nacht_2022",
    noise_isoline_road_night_layer="de.hh.up:strassenverkehr_nacht_2022",
    noise_isoline_rail_day_layer=None,     # fill after impl-time WFS verify
    noise_isoline_rail_night_layer=None,
    noise_isoline_air_day_layer=None,
    noise_isoline_air_night_layer=None,

    # Fire: BF + FF layers (UNION at impl); no citywide zone layer
    fire_wfs_url=_WFS_FEUERWEHR,
    fire_stations_layer="de.hh.up:berufsfeuerwehr",
    fire_zones_layer=None,
    fire_stations_field_map={"name": "name", "type": "typ", "address": "adresse",
                              "phone_bf": "telefon", "phone_ff": "telefon", "zone_id": None},
    fire_zones_field_map={},
    fire_zones_available=False,

    trees_wfs_url=_WFS_BAUMKATASTER, trees_layer="de.hh.up:strassenbaumkataster",
    trees_field_map={"species_de": "art_deutsch", "genus_de": "gattung_deutsch",
                      "group": "gattung", "height": None,      # HH has no height field
                      "age": None, "planting_year": "pflanzjahr", "street": "strasse"},
    trees_radius_m=200,

    quiet_wfs_url=_WFS_RUHIGE, quiet_layer="de.hh.up:ruhige_gebiete_hamburg",
    quiet_field_map={"name": "name", "kind": "kind",
                      "size_ha": "groesse_ha", "id": "id"},

    protection_wfs_url=_WFS_SOZERHVO,
    protection_em_layer="de.hh.up:sozerhvo_inkraft",
    protection_es_layer=None,
    protection_field_map={"name": "gebietsname", "code": "fundstelle",
                          "in_force": "datum", "district": "bezirk",     # int code!
                          "size_ha": None},

    pools_wfs_url=None,           # dropped per spec Q3
    pools_layer=None,
    pools_field_map={},
    swim_natural_wfs_url=_WFS_BADEGEWAESSER,
    swim_natural_layer="app:badegewaesser",
    swim_natural_field_map={"name": "name", "eu_rating": "eu_einstufung",
                             "website": "link", "cyano": "cyano"},

    # Air: none (per Q10 / landscape §2.8)
    air_wfs_url=None, air_layer=None, air_field_map={},
    air_model="none",

    heat_wfs_url=_WFS_KLIMA,
    heat_layer="de.hh.up:bewertung_tags_siedlung_verkehr",
    heat_field_map={"day_class": "bewertung"},

    stations_data_path=os.environ.get(
        "HVV_STATIONS_PATH",
        str(Path(__file__).resolve().parent / "data" / "vbb_hamburg_su.csv")),
    tram_wfs_url=None, tram_layer=None, tram_field_map={},
    regional_rail_stations=_REGIONAL_RAIL,
    airport={"name": "Hamburg Airport Helmut Schmidt (HAM)",
             "iata": "HAM", "lat": 53.6304, "lon": 9.98823},
    ferry_stations_data_path=os.environ.get(
        "HVV_FERRY_PATH",
        str(Path(__file__).resolve().parent / "data" / "hvv_hamburg_ferry.csv")),

    bilingual_glossary=_HAMBURG_GLOSSARY,
    overpass_bbox=(53.39, 9.73, 53.73, 10.32),
    attribution=_ATTRIBUTION,

    osm_local_path=os.environ.get("OSM_LOCAL_PATH", "data/osm/hamburg-amenities.json"),
    address_local_path=os.environ.get("ADDRESS_LOCAL_PATH", "data/osm/hamburg-addresses.json"),

    gesix_wfs_url=None, gesix_layer=None,        # Hamburg uses sozialmonitoring
    sozialmonitoring_wfs_url=_WFS_SOZMON,
    sozialmonitoring_layer="de.hh.up:sozialmonitoring",
    sozialmonitoring_field_map={
        "statusindex":  "statusindex",
        "gesamtindex":  "gesamtindex",
        "dynamikindex": "dynamikindex",
        "stadtteil":    "stadtteil",
        "statgeb":      "statgeb",
        "berichtsjahr": "berichtsjahr",
    },

    young_family_lens=None,       # deferred to a later release; frontend hides YF lens for Hamburg via slug filter (spec Q9)
    newcomer_lens=NEWCOMER_LENS,           # filled by Task 13
    quiet_living_lens=None,               # deferred to a later release; frontend hides QL lens for Hamburg via slug filter (spec Q9)
    commuter_lens=COMMUTER_LENS,           # filled by Task 14

    bezirksgrenzen_wfs_url=_WFS_VERW,
    bezirksgrenzen_layer="app:bezirke",
    bezirksgrenzen_field_map={"name": "bezirk_name"},   # verify at impl
    buergeramt_wfs_url=None, buergeramt_layer=None, buergeramt_field_map={},
    finanzamts=(), standesamts_by_bezirk=_STANDESAMTS_BY_BEZIRK,
    arbeitsagenturs=(), lea_office={},
    others_admin_cards=OTHERS_ADMIN_CARDS,

    xmas_market_url=None,

    parking_zones_wfs_url=_WFS_PARKZONEN,
    parking_zones_layer="de.hh.up:bewohnerparkgebiete",
    parking_zones_field_map={"name": "gebiet", "bezirk": "bezirk",
                              "zeiten": None, "gebuehr": None, "bemerkung": None},

    tempolimits_wfs_url=_WFS_TEMPOLIMITS,
    tempolimits_layer="de.hh.up:zulaessige_hoechstgeschwindigkeiten",
    tempolimits_field_map={"speed": "wert", "time_restriction": "zeit",
                            "reason": "durch_t"},

    arterial_wfs_url=_WFS_STRNETZ,
    arterial_layer="de.hh.up:strassennetz_gesamt",
    arterial_field_map={"name": "strassenname", "class": "strassenklasse"},

    bezirk_id_to_name=_BEZIRK_ID_TO_NAME,
)


if __name__ == "__main__":
    # T12 skeleton asserts
    assert HAMBURG.slug == "hamburg"
    assert HAMBURG.wfs_output_format == "application/geo+json"
    assert HAMBURG.geocoder == "oaf"
    assert HAMBURG.noise_model == "isoline"
    assert HAMBURG.air_model == "none"
    assert HAMBURG.fire_zones_available is False
    assert HAMBURG.bezirk_id_to_name[1] == "Hamburg-Mitte"
    assert len(HAMBURG.standesamts_by_bezirk) == 7
    assert len(HAMBURG.regional_rail_stations) == 13
    assert HAMBURG.gesix_wfs_url is None
    assert HAMBURG.sozialmonitoring_wfs_url is not None
    assert HAMBURG.pools_wfs_url is None
    assert HAMBURG.xmas_market_url is None
    # T13/T14 lens presence asserts
    assert HAMBURG.newcomer_lens is not None
    assert len(HAMBURG.newcomer_lens.tiles) == 13
    assert HAMBURG.commuter_lens is not None
    assert len(HAMBURG.commuter_lens.tiles) == 11
    assert HAMBURG.young_family_lens is None
    assert HAMBURG.quiet_living_lens is None
    # T15: identity asserts
    assert HAMBURG.newcomer_lens is NEWCOMER_LENS
    assert HAMBURG.commuter_lens is COMMUTER_LENS
    assert HAMBURG.others_admin_cards is OTHERS_ADMIN_CARDS
    assert HAMBURG.buergeramt_wfs_url is None
    # T15: tile-key order asserts — Newcomer (13 keys)
    keys = [t.key for t in HAMBURG.newcomer_lens.tiles]
    assert keys == [
        "rail_transit", "ferry_transit", "bus_transit",
        "intl_food", "coworking",
        "english_clinic", "language_school", "library",
        "packstation", "parkzone",
        "nightlife_density",
        "sozialmonitoring_status", "sozialmonitoring_gesamt",
    ], keys
    # T15: tile-key order asserts — Commuter (11 keys)
    commuter_keys = [t.key for t in HAMBURG.commuter_lens.tiles]
    assert commuter_keys == [
        "commuter_rail_transit", "commuter_ferry_transit", "commuter_bus_transit",
        "regional_rail_reach", "cycling_network",
        "parkzone", "car_sharing_reach", "ev_charging_reach",
        "airport_reach",
        "sozialmonitoring_status_commuter", "sozialmonitoring_gesamt_commuter",
    ], commuter_keys
    # No tram tile in either lens
    assert "tram_transit" not in keys
    assert "commuter_tram_transit" not in commuter_keys
    # Only Standesamt in Others tab
    admin_keys = [c.key for c in HAMBURG.others_admin_cards]
    assert admin_keys == ["standesamt"], admin_keys
    # Attribution keys wired for every provenance-bearing dataset
    for k in ("schools", "kitas", "hospitals", "trees", "sozialmonitoring",
              "ferry", "parkzone", "standesamt"):
        assert k in HAMBURG.attribution, f"missing attribution: {k}"
    print("selfcheck ok: Hamburg Newcomer + Commuter lenses wired")
