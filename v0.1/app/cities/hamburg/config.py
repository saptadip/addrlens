"""Hamburg CityConfig assembly.

Every URL + field name was verified against the landscape doc dated
2026-09-20; see `v0.1/docs/superpowers/specs/2026-09-20-hamburg-data-landscape.md`.
When re-adding a field or fixing a URL, cross-check the same section
in that doc so the config and the reference stay in sync.
"""
import os
from pathlib import Path

from app.cities.base import CityConfig
from app.cities.hamburg.directories import (
    _BEZIRK_ID_TO_NAME,
    _STANDESAMTS_BY_BEZIRK,
    _REGIONAL_RAIL,
    _HAMBURG_GLOSSARY,
    _LEA_OFFICE,
    _ARBEITSAGENTURS,
    _INTL_SCHOOLS,
    _KUNDENZENTREN,
    _FINANZAMTS,
    OTHERS_ADMIN_CARDS,
)
from app.cities.hamburg.lenses import NEWCOMER_LENS, COMMUTER_LENS

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
    "kundenzentrum":  "Curated from hamburg.de Kundenzentren-Verzeichnis (public reference, verified 2026-09-21)",
    "finanzamt":      "Curated from Hamburger Finanzbehörde — Finanzämter-Übersicht (public reference, verified 2026-09-21)",
    "tempolimits":    "Freie und Hansestadt Hamburg / BVM — Zulässige Höchstgeschwindigkeiten (dl-de/by-2-0)",
    "arterial_road":  "Freie und Hansestadt Hamburg / BVM via LGV — Straßen- und Wegenetz (dl-de/by-2-0)",
    "cycling":        "© OpenStreetMap contributors (ODbL) via Geofabrik — highway=cycleway (weekly Hamburg extract)",
    "cobblestone":    "© OpenStreetMap contributors (ODbL) via Geofabrik — trafficked highway + surface=sett|cobblestone (weekly Hamburg extract)",
    "car_sharing":    "© OpenStreetMap contributors (ODbL) via Geofabrik — amenity=car_sharing (weekly Hamburg extract)",
    "parkzone":       "Freie und Hansestadt Hamburg / LGV — Bewohnerparkgebiete (dl-de/by-2-0)",
    "natural_swim":   "Freie und Hansestadt Hamburg / BUKEA — Badegewässer (dl-de/by-2-0)",
}

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
    # Extended vs Berlin's 4-key map — carries per-Kita rendering fields
    # (Strasse/Hausnr/PLZ/Ort/Telefon + Leistungsname[]) so the frontend
    # tooltip has Address/Phone/Capacity/Approach rows for Hamburg too.
    kita_field_map={"name": "Name", "capacity": "Anzahl_betreuter_Kinder",
                    "operator_type": "Leistungsarten", "approach": "Leistungsname",
                    "street": "Strasse", "hnr": "Hausnr", "plz": "PLZ", "ort": "Ort",
                    "phone": "Telefon", "contact": "Ansprechpartner",
                    "area_sqm": "Pädagogische_Fläche_in_qm",
                    "as_of": "Erhebungsstichtag"},

    hospital_wfs_url=_WFS_KKH,
    hospital_layers=(("de.hh.up:gesundheit_krankenhaeuser", "plan"),),
    hospital_field_map={
        "name_primary": "name", "name_alt1": "einrichtung", "name_alt2": "name",
        "beds": "planbetten", "beds_alt": "teilstationaere_behandlungsplaetze",
        "traeger": "traegerschaft", "ortsteil": "ort",
        "fachabteilungen": "art_der_stationaeren_versorgung",
        # extended: adresse + ort together give a full street + PLZ line;
        # homepage feeds the Website row on the tooltip.
        "address": "adresse", "website": "homepage",
        "beds_class": "groessenklasse_krankenhaus",
    },
    hospital_radius_m=2000, hospital_match_m=500,

    fountains_wfs_url=_WFS_BRUNNEN, fountains_layer="de.hh.up:wc_mit_trinkbrunnen",
    # Verified live 2026-09-21: layer carries {toilette, standort, adresse,
    # bezirk, kostenlos, behindertengerecht, genderneutral, wickeltisch}.
    # `type` → `toilette` (Automatiktoilette / Trinkbrunnen), `location` →
    # `standort`, `seasonal` absent → left as unmapped `hinweis` for fallthrough.
    fountains_field_map={"seasonal": "hinweis", "bezirk": "bezirk",
                          "type": "toilette", "location": "standort",
                          "address": "adresse", "free": "kostenlos",
                          "wheelchair": "behindertengerecht"},

    green_wfs_url=_WFS_GRUENPLAN,
    parks_layer="de.hh.up:verzeichnis_oeffentlicher_gruenanlagen",
    playgrounds_layer="de.hh.up:spielplaetze_hh",
    playgrounds_wfs_url=_WFS_SPIELPLAETZE,   # split WFS — separate base URL

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

    # Fire: BF + FF two layers (UNION at load-time); no citywide zone layer.
    # Verified live 2026-09-21 — layers carry {bezeichnung, strasse,
    # hausnummer, postleitzahl, ab_ort, ab_ortsteil}. No `telefon` on
    # either layer, so per-station phone rows are dropped for Hamburg
    # (universal fire/rescue number: 112).
    fire_wfs_url=_WFS_FEUERWEHR,
    fire_stations_layer="de.hh.up:berufsfeuerwehr",
    fire_stations_layer_ff="de.hh.up:freiwillige_feuerwehr",
    fire_zones_layer=None,
    fire_stations_field_map={"name": "bezeichnung", "type": None,
                              "address": "strasse", "hnr": "hausnummer",
                              "plz": "postleitzahl", "ort": "ab_ort",
                              "phone_bf": None, "phone_ff": None, "zone_id": None},
    fire_zones_field_map={},
    fire_zones_available=False,

    trees_wfs_url=_WFS_BAUMKATASTER, trees_layer="de.hh.up:strassenbaumkataster",
    trees_field_map={"species_de": "art_deutsch", "genus_de": "gattung_deutsch",
                      "group": "gattung", "height": None,      # HH has no height field
                      "age": None, "planting_year": "pflanzjahr", "street": "strasse"},
    trees_radius_m=200,

    quiet_wfs_url=_WFS_RUHIGE, quiet_layer="de.hh.up:ruhige_gebiete_hamburg",
    # Verified via live DescribeFeatureType 2026-09-21: layer returns
    # `{nr: int, ruhiges_gebiet: str}` — no `kind` or `groesse_ha`. Map
    # `name → ruhiges_gebiet` so nearest_quiet_zone doesn't render
    # "Unnamed zone" for every Hamburg lookup. Other keys stay for API
    # symmetry (return None cleanly instead of KeyError).
    quiet_field_map={"name": "ruhiges_gebiet", "kind": "kind",
                      "size_ha": "groesse_ha", "id": "nr"},

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
    # Verified via live GetFeature 2026-09-21: properties are
    # `{typ, nutzung, pet_14h, pet_klasse, bewertung_tag}`. `bewertung_tag`
    # carries the full label ("Sehr starke Belastung (38 °C bis <= 41 °C)")
    # which the frontend splits on " - " into level+range — same shape the
    # Berlin heat card expects. Map `day_class → bewertung_tag`, not
    # `bewertung` (which returned None → "unknown unknown" in the raw view).
    heat_field_map={"day_class": "bewertung_tag"},

    stations_data_path=os.environ.get(
        "HVV_STATIONS_PATH",
        str(Path(__file__).resolve().parent.parent / "data" / "vbb_hamburg_su.csv")),
    tram_wfs_url=None, tram_layer=None, tram_field_map={},
    regional_rail_stations=_REGIONAL_RAIL,
    airport={"name": "Hamburg Airport Helmut Schmidt (HAM)",
             "iata": "HAM", "lat": 53.6304, "lon": 9.98823},
    ferry_stations_data_path=os.environ.get(
        "HVV_FERRY_PATH",
        str(Path(__file__).resolve().parent.parent / "data" / "hvv_hamburg_ferry.csv")),

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
    finanzamts=_FINANZAMTS, standesamts_by_bezirk=_STANDESAMTS_BY_BEZIRK,
    arbeitsagenturs=_ARBEITSAGENTURS, lea_office=_LEA_OFFICE,
    kundenzentren=_KUNDENZENTREN,
    intl_schools_curated=_INTL_SCHOOLS,
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

    # Canonical address for ops/deploy/update.sh smoke-test.
    smoke_address="Heidenkampsweg 40, 20097",

    # Hero image alt-text — describes the exact landmark inside the pin
    # marker so screen-reader users get the specific visual referent
    # (Speicherstadt warehouse district with the iron canal bridge over
    # the Zollkanal).
    hero_alt="AddrLens Hamburg — Speicherstadt with iron canal bridge inside pin marker",
)
