"""Berlin CityConfig assembly.

Every URL + field name was verified against the Berlin Geoportal at
initial data-source pull. When re-adding a field or fixing a URL,
cross-check with `docs/architecture-notes/` or the relevant landscape
snapshot so the config and the reference stay in sync.

Attribution is inlined in the CityConfig(...) call (unlike Hamburg,
which factors it into a module-level dict) — preserve that shape.
"""
import os
import re
from pathlib import Path

from app.cities.base import CityConfig
from app.cities.berlin.directories import (
    _BERLIN_GLOSSARY,
    _SESB_GRUNDSCHULEN,
    _STANDESAMTS_BY_BEZIRK,
    _FINANZAMTS,
    _ARBEITSAGENTURS,
    _LEA_OFFICE,
    OTHERS_ADMIN_CARDS,
)
from app.cities.berlin.lenses import (
    YOUNG_FAMILY_LENS,
    NEWCOMER_LENS,
    QUIET_LIVING_LENS,
    COMMUTER_LENS,
)

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
# Quiet Living lens
_WFS_TEMPOLIMITS   = "https://gdi.berlin.de/services/wfs/tempolimits"          # layer: tempolimits:hoechstgeschwindigkeit — MultiLineString road segments with speed exception (dl-de/zero-2.0)
_WFS_STRNETZ       = "https://gdi.berlin.de/services/wfs/strnetz"              # layer: strnetz:uebergeordnetes_strnetz — LineString centrelines of arterial network (dl-de/zero-2.0)
# Spec B — Bureaucracy lens
_WFS_BEZIRKE       = "https://gdi.berlin.de/services/wfs/alkis_bezirke"        # layer: alkis_bezirke:bezirksgrenzen (verified via GetCapabilities)
_BUERGERAEMTER_URL = "https://service.berlin.de/standorte/geojson/buergeramt"  # service.berlin.de REST GeoJSON (no WFS published); sentinel layer "_geojson" triggers custom loader
# Seasonal Weihnachtsmärkte feed — Berlin Senate publishes a live GeoJSON of
# every registered Christmas market. Peaks Nov–Dec (~45–50 markets); the feed
# thins to empty the rest of the year. Loaded at boot; no cron.
_WEIHNACHTSMARKT_URL = "https://www.berlin.de/sen/web/service/maerkte-feste/weihnachtsmaerkte/index.php/index/all.gjson"
# Parkraumbewirtschaftungszonen — Berlin's paid on-street parking zones
# (Anwohnerparken). Bezirks-maintained MultiPolygons published as one
# citywide layer via gdi.berlin.de. Feature count as of Sep 2026: 103.
# Attributes per zone: parkzone (code), bezirk, zeiten (enforcement
# hours), gebuehr (visitor fee/hr), bemerkung (notes on exceptions).
_WFS_PARKZONEN     = "https://gdi.berlin.de/services/wfs/parkraumbewirtschaftung"

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
    # T27 fix: gs_public must stay Grundschule-only for Berlin's catchment
    # fallback (nearest_gs_public) and T11 nearest-school ruling. The broader
    # schools_primary_types includes Gemeinschaftsschulen + Kombinierte which
    # are not Grundschulen. Without this override, T27's initial commit would
    # silently widen the set that catchment fallback searches against.
    schools_gs_public_types=frozenset({"Grundschule"}),
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

    # -- Quiet Living lens data ----------------------------------------
    # Tempolimits: MultiLineString road segments carrying a speed
    # exception to the general 50 km/h. `wert_ves` is the km/h value.
    tempolimits_wfs_url=_WFS_TEMPOLIMITS,
    tempolimits_layer="tempolimits:hoechstgeschwindigkeit",
    tempolimits_field_map={
        "speed":            "wert_ves",
        "time_restriction": "zeit_t",
        "reason":           "durch_t",
    },
    # Übergeordnetes Straßennetz: arterial + supra-local road centrelines.
    # Any address's distance-to-nearest = exposure to primary traffic.
    arterial_wfs_url=_WFS_STRNETZ,
    arterial_layer="strnetz:uebergeordnetes_strnetz",
    arterial_field_map={
        "name":  "strassenname",
        "class": "strassenklasse1",   # "I" = federal-tier, "II" = arterial-tier
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
    stations_data_path=str(Path(__file__).resolve().parent.parent / "data" / "vbb_berlin_su.csv"),
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
        # Inner-ring RE/RB platforms omitted from the original list.
        # Alexanderplatz carries RE1/RE2/RE7/RB14; Friedrichstraße carries
        # RE1/RE2/RE7/RB14 westbound; Potsdamer Platz carries RE3/RE4/RE5.
        # Their absence was surfaced when Karl-Liebknecht-Str. tested
        # AMBER on the Commuter lens because the nearest listed station
        # (S Ostbahnhof) sat 1.8 km away.
        ("S+U Alexanderplatz",                52.521650, 13.411483),
        ("S Friedrichstraße",                 52.520008, 13.386880),
        ("S+U Potsdamer Platz",               52.509703, 13.376229),
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
        "tempolimits":    "Geoportal Berlin / Tempolimits — angeordnete Höchstgeschwindigkeiten (dl-de/zero-2.0)",
        "arterial_road":  "Geoportal Berlin / Übergeordnetes Straßennetz — Bestand (dl-de/zero-2.0)",
        "cycling":        "© OpenStreetMap contributors (ODbL) via Geofabrik — highway=cycleway (weekly snapshot)",
        "cobblestone":    "© OpenStreetMap contributors (ODbL) via Geofabrik — trafficked highway + surface=sett|cobblestone|unhewn_cobblestone (weekly snapshot)",
        "car_sharing":    "© OpenStreetMap contributors (ODbL) via Geofabrik — amenity=car_sharing (weekly snapshot)",
        "xmas_market":    "Berlin Senate / Weihnachtsmärkte-Verzeichnis (berlin.de, live GeoJSON)",
        "parkzone":       "Geoportal Berlin / Parkraumbewirtschaftung — Parkzonen (dl-de/by-2.0)",
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
    quiet_living_lens=QUIET_LIVING_LENS,
    commuter_lens=COMMUTER_LENS,

    # --- Others tab: public-admin office data ---------------------
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
    others_admin_cards=OTHERS_ADMIN_CARDS,

    # Berlin Senate live Weihnachtsmärkte feed — fetched at boot,
    # cached in memory, no cron. Empty in summer, ~45–50 markets in Dec.
    xmas_market_url=_WEIHNACHTSMARKT_URL,

    # Canonical address for ops/deploy/update.sh smoke-test.
    smoke_address="Kastanienallee 12, 10435",

    # Parkraumbewirtschaftungszonen — 103 paid-parking polygons for the
    # Newcomer + Commuter Anwohnerparken tile.
    parking_zones_wfs_url=_WFS_PARKZONEN,
    parking_zones_layer="parkraumbewirtschaftung:parkzonen",
    parking_zones_field_map={
        "name":      "parkzone",
        "bezirk":    "bezirk",
        "zeiten":    "zeiten",
        "gebuehr":   "gebuehr",
        "bemerkung": "bemerkung",
    },
)
