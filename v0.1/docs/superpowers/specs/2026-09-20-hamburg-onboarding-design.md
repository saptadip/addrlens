# Hamburg onboarding — architectural design

**Author:** design phase, 2026-09-20
**Status:** Phase 1 architectural spec — feeds Phase 2 implementation plan via `writing-plans` skill.
**Companion:** `2026-09-20-hamburg-data-landscape.md` (Phase 0 discovery output — data-source facts + curated directories cited here).
**Scope:** Extend AddrLens from Berlin-only to a second city (Hamburg) served from `hamburg.addrlens.de` on the same Hetzner box, using the existing `CityConfig` abstraction with additive fields. Ship 2 lenses (Newcomer + Commuter) for Hamburg on day-1; Young Family + Quiet Living land in later releases. Preserve Berlin behaviour byte-exactly.

---

## 1. Scope + non-goals

### 1.1 What ships (locked decisions)

| # | Decision | Details |
|---|---|---|
| Q1 | Same host, second stack | `docker-compose.prod.yml` gets a new `app-hh` service with `CITY=hamburg`; one shared inference container serves both apps. |
| Q2 | Same UI shape (Raw view + Life Lens), Hamburg-designed cards | Tile keys diverge per city; tile categories (Education / Amenities / Emergency / Environment / Connectivity / Others) stay identical. |
| Q3 | Discovery spike ran first; landscape doc verified | See `2026-09-20-hamburg-data-landscape.md`. All URLs + fields cited here originate there. |
| Q4 | Newcomer + Commuter lenses day-1 | Young Family + Quiet Living for Hamburg deferred to later releases; Hamburg lens picker renders 2 buttons vs Berlin's 4. |
| Q5 | Duplicate + edit LLM templates | `inference/templates/lens_newcomer_hamburg_insight.py` + `lens_commuter_hamburg_insight.py`; Berlin templates untouched. |
| Q6 | `addrlens.de` stays Berlin; `hamburg.addrlens.de` = Hamburg | Cross-link pills added to both header bars; no root-domain city picker. |
| Q7 | Per-city legal pages | `hamburg.addrlens.de/impressum` serves a Hamburg-specific impressum listing only Hamburg data sources; Berlin's stays Berlin-only. |
| Q8 | WFS-first + curated fallback for admin dirs | Hamburg has no admin-office WFS — curation applies to every admin card considered. Curation scope narrowed by Q10 (below). |
| Q9 | Tram slot → ferry | Hamburg's Newcomer + Commuter tile lists drop the tram tile entirely and add a ferry tile (HADAG piers). Preserves tile count. |
| Q10 | Minimal manual curation (strict) | Curate ONLY where values change rarely (~3-5+ yrs). Skip Kundenzentrum, Finanzamt, Arbeitsagentur, Amt für Migration tiles for Hamburg day-1 — Others tab is thinner than Berlin's. Only **Standesamt** carries over as a curated admin card. |
| Geocoder | OGC API Features runtime for Hamburg address lookup | Fallback path C (nightly preload from GML) kept in reserve if OAF rate-limits us in prod. Berlin's WFS geocoder unchanged. |
| Noise tile | Bands (isoline model) for Hamburg | `noise_at()` returns dB band strings ("55-59", "60-64", …) instead of numeric values; tier logic bins band strings. |
| Pools | Dropped from Hamburg raw view | No baederland.de scrape; no Sportstaetten filter. Amenities tab loses one card in Hamburg. |
| Wochenmarkt + Weihnachtsmarkt | Dropped from Hamburg Newcomer lens | No HTML scrape, no curated seed. Two Newcomer tiles removed for Hamburg. |
| Sozialmonitoring | Two tiles: `statusindex` + `gesamtindex` (per Q5) | Rendered independently on each lens's Neighbourhood-profile section. `dynamikindex` NOT a separate tile in v1 — held for later. |
| Nearest primary school | Distance-in-km only (per Q6) | Hamburg's catchment WFS is per-district not per-school; the "your assigned Grundschule" concept doesn't cleanly translate. Show "nearest primary school: 0.4 km" and stop. |
| Bezirk int→name lookup | Inlined in `hamburg.py` | 7-entry dict, no CityConfig field required. |

### 1.2 Non-goals

- **Full lens parity.** Young Family + Quiet Living lenses are Hamburg-deferred; not blockers for day-1.
- **Path-based routing** (`addrlens.de/hamburg/…`). Rejected in Q6 to preserve `CITY=<slug>` single-boot invariant.
- **Shared prompt/exemplar files across cities.** Q5 chose duplicate-edit, not parameterised skeleton — no refactor of Berlin templates.
- **New third-city readiness scaffolding.** Berlin's `CityConfig` already handles arbitrary cities; Hamburg exercises but does not extend the abstraction beyond what its own data demands. Any München/Köln extensions are Phase-N work.
- **Kundenzentrum / Finanzamt / Arbeitsagentur / Amt-für-Migration tiles for Hamburg.** Per Q10-B, dropped for day-1. Can be added later by extending the curated dicts.
- **Address geocoder via runtime GML parsing.** Rejected — OAF is the primary path, nightly preload the fallback.
- **Realtime HVV data** (Geofox / GTI). Only static GTFS coordinates used, mirroring Berlin's VBB-CSV approach.

---

## 2. `CityConfig` additive changes

Every new field is `Optional` with a default that leaves Berlin behaviour byte-exact. No breaking rename of existing fields. `app/cities/base.py` diff summary:

### 2.1 New fields (all Optional, defaults preserve Berlin)

```python
# --- Geocoder axis: allow OGC API Features (Hamburg) alongside WFS + nominatim ---
# `geocoder` string accepted values become {"wfs", "oaf", "nominatim"}. Berlin
# stays "wfs"; Hamburg uses "oaf".
geocoder_oaf_url:      Optional[str] = None    # e.g. "https://api.hamburg.de/datasets/v1/hh_wfs_dog/collections/hauskoordinaten"
geocoder_oaf_field_map: Optional[dict] = None  # {"street": "strasse", "hnr": "hausnummer", "plz": "plz"}

# --- WFS transport axis ---
# Berlin's WFS auto-projects to 4326 when srsName omitted; Hamburg requires
# explicit `srsName=EPSG:4326` on every request. Default preserves Berlin.
wfs_srs_name: str = "EPSG:4326"

# --- Ferry as first-class transit mode ---
# Berlin has no ferry-as-commute; Hamburg's HADAG piers are the tram-slot
# replacement in both Newcomer + Commuter lenses.
ferry_stations_data_path: Optional[str] = None  # abs path to ferry_<slug>.csv extracted from HVV GTFS

# --- Sozialmonitoring (Hamburg) — parallels gesix_* for Berlin ---
# Both cities keep their own field set; a lookup helper in Index picks the
# right one based on which is configured.
sozialmonitoring_wfs_url:   Optional[str] = None
sozialmonitoring_layer:     Optional[str] = None
sozialmonitoring_field_map: Optional[dict] = None   # {"statusindex": "statusindex", "gesamtindex": "gesamtindex", "dynamikindex": "dynamikindex", "stadtteil": "stadtteil", "statgeb": "statgeb", "berichtsjahr": "berichtsjahr"}

# --- Noise model axis ---
# "point" = per-façade attribute lookup (Berlin's ua_stratlaerm_2022 → dB
# integer). "isoline" = per-source point-in-polygon returning band strings
# ("55-59", "60-64", ...). "none" = no noise data available (future cities).
noise_model: Literal["point", "isoline", "none"] = "point"
# Only used when noise_model == "isoline". Six sources × day/night = up to 6
# layer configs; None entries drop the source cleanly.
noise_isoline_road_day_layer:  Optional[str] = None
noise_isoline_road_night_layer: Optional[str] = None
noise_isoline_rail_day_layer:  Optional[str] = None
noise_isoline_rail_night_layer: Optional[str] = None
noise_isoline_air_day_layer:   Optional[str] = None
noise_isoline_air_night_layer: Optional[str] = None

# --- Air model axis ---
# "street" = per-Straßenabschnitt NO₂ modelling (Berlin). "station" =
# nearest-station distance proxy (fallback for cities with only station-
# level data). "none" = no air tile shown (Hamburg for now — HaLm not
# integrated in v1).
air_model: Literal["street", "station", "none"] = "street"
air_stations_data_path: Optional[str] = None      # curated CSV when air_model == "station"

# --- Fire response zones availability ---
# Berlin has full citywide Einsatzbereiche polygons; Hamburg publishes only
# an Eimsbüttel pilot. When False, Index.fire_rescue returns nearest-station
# only + zone fields set to None; frontend hides the zone line.
fire_zones_available: bool = True

# --- Bezirks integer-code lookup ---
# Berlin stores bezirk as string in every layer that uses it; Hamburg stores
# integer codes on the SozErhVo layer. Inline lookup, no new plumbing.
bezirk_id_to_name: Optional[dict[int, str]] = None
```

### 2.2 Fields NOT added

The following were considered and rejected — either Berlin's existing Optional pattern covers them or the tile is dropped for Hamburg:

- `pools_curated: Optional[tuple]` — pools tile dropped from Hamburg per Q3, no code path needed.
- `xmas_market_curated: Optional[tuple]` — dropped per Q10 minimal-curation rule.
- `wochenmarkt_url: Optional[str]` — dropped per Q10.
- `kundenzentrum_curated: Optional[tuple]` — Q10-B skips this tile entirely.
- A generic `namespace: str` field — Berlin's `<prefix>:<layer>` typeName already carries the namespace; Hamburg's `de.hh.up:foo` / `app:bar` / `dog:baz` work identically because `wfs()` passes typeName through unchanged.
- A generic `attribution_authority: dict` — Berlin's flat `attribution` dict already lets Hamburg cite BUKEA/LGV/BSB etc. per tile without new plumbing.

---

## 3. Hamburg tile design

### 3.1 Newcomer lens — Hamburg tile list

Berlin's Newcomer lens has 15 tiles. Hamburg's proposed set (13 tiles):

| # | key | label | Berlin equiv | Notes |
|---|---|---|---|---|
| 1 | ~~buergeramt~~ | — | Bürgeramt reach | **DROPPED** (Q10-B — no Kundenzentrum curation) |
| 2 | rail_transit | Rail Transit | rail_transit | S+U-Bahn, thresholds unchanged from Berlin |
| 3 | ferry_transit | Ferry Transit | ~~tram_transit~~ | **NEW — HADAG piers**. Green ≤ 500 m, amber ≤ 1000 m. Caveat: peak/all-day varies by line. |
| 4 | bus_transit | Bus Transit | bus_transit | thresholds unchanged |
| 5 | intl_food | International food | intl_food | OSM tag identical; density lower in HH — same thresholds work |
| 6 | coworking | Coworking + Wi-Fi cafés | coworking | same OSM tag |
| 7 | english_clinic | English-speaking clinic | english_clinic | same OSM tag; caveat unchanged |
| 8 | language_school | German classes | language_school | VHS Hamburg + private; OSM name regex "VHS Hamburg\|Volkshochschule" |
| 9 | library | Public library | library | Bücherhallen Hamburg; OSM `operator=Bücherhallen Hamburg` |
| 10 | packstation | Parcel pickup | packstation | same OSM tag |
| 11 | parkzone | Resident parking | parkzone | `bewohnerparkgebiete` WFS; fees/hours not in WFS so tile shows inside/outside + edge distance only |
| 12 | ~~wochenmarkt~~ | — | Open market | **DROPPED** (Q10 — no scrape or curation) |
| 13 | ~~xmas_market~~ | — | Christmas Market | **DROPPED** (Q10) |
| 14 | nightlife_density | Nightlife density | nightlife_density | OSM; numeric-only tile unchanged |
| 15 | sozialmonitoring_status | Neighbourhood status | ~~gesix_newcomer~~ | **NEW** — 4-band badge (hoch / mittel / niedrig / sehr niedrig) |
| 16 | sozialmonitoring_gesamt | Aufmerksamkeitsgebiet | — | **NEW** — Hamburg's overall handlungsbedarf flag (per Q5 two-tile split) |

Result: 13 active tiles vs Berlin's 15. Two Berlin tiles gain no equivalent (wochenmarkt + xmas_market); one Berlin tile (buergeramt) has no analogue given Q10-B; two new tiles (ferry + sozialmonitoring_gesamt) added; two tiles renamed (tram → ferry; gesix → sozialmonitoring_status).

**Thresholds for new tiles:**
```python
# ferry_transit
thresholds={"green_m": 500, "amber_m": 1000}
caveat=("HVV-integrated HADAG ferry piers (route_type=4). All-day service "
        "on lines 62, 64, 72; other lines are peak-only. Distance is walk to "
        "the nearest pier, not to a specific line.")

# sozialmonitoring_status
thresholds={}   # 4-band categorical: "hoch" → green, "mittel" → amber-green,
                # "niedrig" → amber-red, "sehr niedrig" → red
caveat=("Hamburg BSW Sozialmonitoring — 4-level Statusindex per Statistisches "
        "Gebiet (~2200 residents). 'Hoch' = strong socioeconomic status; "
        "'sehr niedrig' = neighbourhood flagged for city support. Refreshed "
        "annually; polygon grain is finer than Berlin's Planungsraum.")

# sozialmonitoring_gesamt
thresholds={}   # categorical: "kein Handlungsbedarf" → green, "Beobachtungsgebiet" →
                # amber, "Aufmerksamkeitsgebiet" → red
caveat=("Hamburg BSW Sozialmonitoring — combined Status+Dynamik verdict. "
        "'Aufmerksamkeitsgebiet' = the polygon around this flat is a city-"
        "designated area for social monitoring. Independent of the Status tile.")
```

### 3.2 Commuter lens — Hamburg tile list

Berlin's Commuter lens has 10 tiles. Hamburg's proposed set (9 tiles):

| # | key | label | Berlin equiv | Notes |
|---|---|---|---|---|
| 1 | commuter_rail_transit | S+U-Bahn reach | commuter_rail_transit | thresholds unchanged; AKN merged into S-Bahn count (per landscape §3.1) |
| 2 | commuter_ferry_transit | Ferry reach | ~~commuter_tram_transit~~ | **NEW**. Green ≤ 400 m, amber ≤ 800 m (tighter than Newcomer since commuter walks 2× daily) |
| 3 | commuter_bus_transit | Bus reach | commuter_bus_transit | thresholds unchanged |
| 4 | regional_rail_reach | Regional rail reach | regional_rail_reach | 13 curated HH stations from landscape §3.3 |
| 5 | cycling_network | Cycling network reach | cycling_network | OSM `highway=cycleway`; HH coverage comparable |
| 6 | parkzone | Resident parking | parkzone | same HH parkzone tile as Newcomer |
| 7 | car_sharing_reach | Car-sharing reach | car_sharing_reach | OSM `amenity=car_sharing` |
| 8 | ev_charging_reach | EV charger reach | ev_charging_reach | OSM `amenity=charging_station` |
| 9 | airport_reach | Airport reach (HAM) | airport_reach | HAM at 53.6304 / 9.98823; green ≤ 20 km, amber ≤ 35 km (unchanged from Berlin — Hamburg is smaller so most addresses will be green) |
| 10 | sozialmonitoring_status_commuter | Neighbourhood status | ~~gesix_commuter~~ | **NEW** — same signal as Newcomer's status tile, commuter-audience framing |
| 11 | sozialmonitoring_gesamt_commuter | Aufmerksamkeitsgebiet | — | **NEW** — per Q5 |

Result: 10 active tiles vs Berlin's 10 — one dropped (tram), one added (ferry), one added (gesamt), one renamed (gesix→sozialmonitoring_status).

### 3.3 Raw view — Hamburg tab contents

The Raw view keeps Berlin's tab structure (Education / Amenities / Emergency / Environment / Connectivity / Others). Per-tab cards for Hamburg:

- **Education:** Schulen (state + private, layer UNION), Kitas, Grundschul-Einzugsgebiet-per-Statistikgebiet (advisory only), **nearest-primary-school distance in km** (per Q6, no name/BSN drill-down since Hamburg catchments don't map per-school)
- **Amenities:** Krankenhäuser, Grünanlagen (parks), Spielplätze (playgrounds — separate WFS), Kleingärten + Friedhöfe (Grünplan companion layers), Trinkbrunnen (subset of `wc_mit_trinkbrunnen`, ~40 in HH), Badegewässer (14 sites) — **pools card dropped per Q3**
- **Emergency:** Feuerwehr Standorte (BF + FF layers UNIONed), quiet zones (Ruhige Gebiete + Ruheinseln companion). **No fire response-zone card in Hamburg** — `fire_zones_available=False` hides it
- **Environment:** Noise (dB bands per source — road/rail/air × day/night, 6 rows), heat (Klimabewertung 2023: PET-day + PET-night + green-day companion), trees (Straßenbaumkataster ~245k), Milieuschutz (SozErhVo in-force + in-preparation), arterial road distance, tempolimits (5-layer stacked lookup)
- **Connectivity:** S-Bahn / U-Bahn / **Ferry** / Bus / regional rail (13 curated) / HAM airport
- **Others:** Bezirk chip (7 HH Bezirke) + Standesamt (only curated admin card per Q10-B) + Sozialmonitoring context. **No Kundenzentrum, Finanzamt, Arbeitsagentur, Amt-für-Migration cards.**

### 3.4 What Hamburg is missing vs Berlin at day-1

Explicit tile-count delta so the frontend can render honest "not applicable in Hamburg" copy where appropriate:

- Newcomer: −2 tiles (wochenmarkt, xmas_market, buergeramt) +2 tiles (ferry, sozialmonitoring_gesamt) = net 13 vs Berlin 15
- Commuter: −1 tile (commuter_tram_transit) +2 tiles (ferry, sozialmonitoring_gesamt) = net 11 vs Berlin 10 (one tile more than Berlin; sozialmonitoring gets a two-tile split per Q5)
- Others tab: −4 cards (buergeramt, finanzamt, LEA, arbeitsagentur) = only Standesamt survives
- Amenities tab: −1 card (pools)
- Environment: air card dropped (`air_model="none"`)
- Emergency: fire response-zone line dropped (`fire_zones_available=False`)

Frontend renders the lens tile grid based on the loaded lens tile tuple — no per-city UI branching required for missing tiles (they simply aren't in the tuple).

---

## 4. Backend design

### 4.1 New `app/cities/hamburg.py`

Mirrors `berlin.py` structure. Skeleton:

```python
"""Hamburg CityConfig — Ship C. Same shape as berlin.py; every value verified
against the discovery doc 2026-09-20-hamburg-data-landscape.md.

Extending to a third city later means copying THIS file, not berlin.py — this
is the first city that exercises every Optional field."""

import os
import re
from pathlib import Path

from app.cities.base import (
    CityConfig, LensConfig, LensTileConfig, OthersAdminCardConfig,
)

# ---- WFS URLs (all verified 2026-09-20 via GetCapabilities) ----
_WFS_DOG_OAF        = "https://api.hamburg.de/datasets/v1/hh_wfs_dog/collections/hauskoordinaten"
_WFS_SCHULEN        = "https://geodienste.hamburg.de/HH_WFS_Schulen"
_WFS_EINZUGSGEB     = "https://geodienste.hamburg.de/HH_WFS_Regionaler_Bildungsatlas_Einzugsgebiete_Schulwahl"
_WFS_KITA           = "https://geodienste.hamburg.de/HH_WFS_KitaEinrichtung"
_WFS_KKH            = "https://geodienste.hamburg.de/HH_WFS_Krankenhaeuser"
_WFS_BRUNNEN        = "https://geodienste.hamburg.de/wfs_wc_mit_trinkbrunnen"
_WFS_GRUENPLAN      = "https://geodienste.hamburg.de/HH_WFS_Gruenplan"
_WFS_SPIELPLAETZE   = "https://geodienste.hamburg.de/wfs_spielplaetze"
_WFS_LAERM_STRASSE  = "https://geodienste.hamburg.de/HH_WFS_Strassenverkehr"    # verify at impl time (404'd during discovery)
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

# ---- Bezirk integer → name lookup (SozErhVo layer stores bezirk as int) ----
_BEZIRK_ID_TO_NAME = {
    1: "Hamburg-Mitte", 2: "Altona", 3: "Eimsbüttel",
    4: "Hamburg-Nord", 5: "Wandsbek", 6: "Bergedorf", 7: "Harburg",
}

# ---- Curated: 7 Standesämter (from landscape doc §4.2). Only admin office
#      that survives Q10-B. Annual re-check per hamburg.de/politik-und-verwaltung
#      /bezirke/bezirksthemen/standesamt (ponytail 2027-09).
_STANDESAMTS_BY_BEZIRK = { ... 7 entries from landscape §4.2 ... }

# ---- Regional rail (13 curated stations, landscape §3.3) ----
_REGIONAL_RAIL = ( ... 13 entries ... )

# ---- Hamburg-specific glossary for the LLM's German-word gloss step ----
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

# ---- LensConfig blocks: NEWCOMER_LENS + COMMUTER_LENS (tiles from §3.1 + §3.2) ----
...

HAMBURG = CityConfig(
    slug="hamburg",
    display_name="Hamburg",
    default_center=(53.5511, 9.9937),
    wfs_output_format="application/geo+json",
    wfs_srs_name="EPSG:4326",

    geocoder="oaf",
    geocoder_wfs_url=None,     # unused when geocoder="oaf"
    geocoder_layer=None,
    geocoder_field_map={},
    geocoder_oaf_url=_WFS_DOG_OAF,
    geocoder_oaf_field_map={"street": "strasse", "hnr": "hausnummer", "plz": "plz"},

    # ... all data source URLs, field maps, layer names from landscape doc ...
    # ... 2 lens configs (Newcomer + Commuter) with 13 + 10 tiles respectively ...

    noise_model="isoline",
    noise_isoline_road_day_layer="de.hh.up:strassenverkehr_tag_abend_nacht_2022",
    noise_isoline_road_night_layer="de.hh.up:strassenverkehr_nacht_2022",
    # rail + air layers to fill in after impl-time verification

    air_model="none",
    fire_zones_available=False,
    bezirk_id_to_name=_BEZIRK_ID_TO_NAME,

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

    ferry_stations_data_path=str(Path(__file__).resolve().parent / "data" / "hvv_hamburg_ferry.csv"),

    # These stay None for HH day-1 (Q10-B, Q3):
    #   buergeramt_wfs_url, finanzamts, arbeitsagenturs, lea_office,
    #   pools_wfs_url, xmas_market_url, parking_zones_field_map subset
    ...

    others_admin_cards=(
        OthersAdminCardConfig(key="standesamt", label="Standesamt (Marriage / Birth)", icon="standesamt"),
    ),
)
```

**Selfcheck (`if __name__ == "__main__"`):** mirrors `berlin.py`'s selfcheck — asserts Newcomer + Commuter tile-key ordering, admin card list, that ferry_transit is present and tram_transit is absent, that sozialmonitoring_wfs_url is wired but gesix_wfs_url is None.

### 4.2 `app/core/index.py` changes

All additions are gated by the corresponding `CityConfig` field being set. Berlin's boot behaviour byte-exact after the changes.

**New loaders (~200 LOC total):**

```python
def _load_ferry(self) -> None:
    """HADAG ferry piers from HVV GTFS extract. Vendored CSV like S/U-Bahn."""
    cfg = self.cfg
    self.ferry = []
    if not cfg.ferry_stations_data_path:
        return
    log_load("HVV ferry piers")
    import csv as _csv
    with open(cfg.ferry_stations_data_path, encoding="utf-8", newline="") as f:
        for row in _csv.DictReader(f):
            self.ferry.append({
                "name": row["name"],
                "lat": float(row["lat"]), "lon": float(row["lon"]),
                "lines": row.get("lines", ""),
                "peak_only": row.get("peak_only", "0") == "1",
            })
    print(f"{len(self.ferry)} ferry piers")

def _load_sozialmonitoring(self) -> None:
    """Hamburg BSW Sozialmonitoring — 941 Statistische-Gebiete polygons with
    pre-classified statusindex / dynamikindex / gesamtindex string bands."""
    cfg = self.cfg
    self.sozialmonitoring = []
    if not (getattr(cfg, "sozialmonitoring_wfs_url", None)
            and getattr(cfg, "sozialmonitoring_layer", None)):
        return
    log_load("Sozialmonitoring (Hamburg neighbourhood status)")
    try:
        for props, geom in load_polygon_layer(
                cfg, cfg.sozialmonitoring_wfs_url, cfg.sozialmonitoring_layer, 1500):
            self.sozialmonitoring.append((props, geom))
        print(f"{len(self.sozialmonitoring)} Statistische Gebiete")
    except Exception as e:
        print(f"failed ({type(e).__name__}: {e})")
```

**Modified loaders (behaviour-preserving for Berlin):**

- `_load_hospitals`: Berlin loops over `cfg.hospital_layers` (2 layers). Hamburg has 1 layer — the existing loop handles a 1-tuple fine, no change needed.
- `_load_fire`: reads existing `cfg.fire_stations_layer`. Hamburg has 2 layers (`berufsfeuerwehr` + `freiwillige_feuerwehr`); extend `CityConfig.fire_stations_layer` type from `Optional[str]` to `Optional[str | tuple[str, ...]]` and UNION-load. Berlin's single string still works.
- `_load_parking_zones`: unchanged. Hamburg's HH_WFS_bewohnerparkgebiete has no `zeiten`/`gebuehr`/`bemerkung` fields — the field_map values are `None`, existing `.get(fm.get("zeiten"))` returns None gracefully.
- `_load_buergeramts` / `_load_xmas_markets`: not called for Hamburg (URLs are None). Existing `if not (cfg.X_url and cfg.X_layer): return` guards hold.

**New lookup methods (~150 LOC):**

```python
def nearest_ferry(self, lon, lat):
    if not self.ferry:
        return None
    best = min(self.ferry, key=lambda p: haversine_m(lon, lat, p["lon"], p["lat"]))
    d = haversine_m(lon, lat, best["lon"], best["lat"])
    return {**best, "distance_m": round(d)}

def sozialmonitoring_at(self, lon, lat):
    """Point-in-polygon over the 941 SM polygons. Returns
    {statusindex, gesamtindex, dynamikindex, stadtteil, statgeb, berichtsjahr}
    or None. Berlin still calls gesix_at (unchanged); Hamburg calls this."""
    if not self.sozialmonitoring:
        return None
    fm = self.cfg.sozialmonitoring_field_map or {}
    pt = Point(lon, lat)
    for props, geom in self.sozialmonitoring:
        if geom.contains(pt):
            return {
                "statusindex":  props.get(fm.get("statusindex")),
                "gesamtindex":  props.get(fm.get("gesamtindex")),
                "dynamikindex": props.get(fm.get("dynamikindex")),
                "stadtteil":    (props.get(fm.get("stadtteil")) or "").strip(),
                "statgeb":      (props.get(fm.get("statgeb")) or "").strip(),
                "berichtsjahr": (props.get(fm.get("berichtsjahr")) or "").strip(),
            }
    return None

def noise_bands_at(self, lon, lat):
    """Called instead of noise_at() when cfg.noise_model == 'isoline'.
    Runs up to 6 point-in-polygon queries against the isoline layers and
    returns band strings per source. Berlin's noise_at() unchanged."""
    ...
```

**`geocode()`:** dispatch on `cfg.geocoder`:
```python
def geocode(self, street, hnr, plz):
    if self.cfg.geocoder == "oaf":
        from app.core.loaders.oaf_geocoder import geocode_oaf
        return geocode_oaf(self.cfg, street, hnr, plz)
    # Berlin path (WFS) — unchanged from today
    ...
```

**Boot order:** the `_expected_loaders` list in `Index.__main__` selfcheck gains `_load_ferry` (after `_load_regional_rail`) + `_load_sozialmonitoring` (after `_load_gesix`; Hamburg has one but not the other). Berlin's boot stdout unchanged (both new loaders return immediately when URL is None).

### 4.3 New module: `app/core/loaders/oaf_geocoder.py`

Small (~50 LOC). Uses existing `httpx` client with per-city output-format constants. Query pattern:

```python
def geocode_oaf(cfg, street, hnr, plz):
    fm = cfg.geocoder_oaf_field_map
    params = {
        fm["street"]: street,
        fm["hnr"]:    hnr,
        fm["plz"]:    plz,
        "limit":      1,
        "f":          "json",
    }
    r = httpx.get(cfg.geocoder_oaf_url + "/items", params=params, timeout=10.0)
    r.raise_for_status()
    data = r.json()
    feats = data.get("features") or []
    if not feats:
        # ß ↔ ss fold retry (same pattern as Berlin's WFS geocoder)
        alt = _ss_fold(street)
        if alt and alt != street:
            params[fm["street"]] = alt
            r = httpx.get(cfg.geocoder_oaf_url + "/items", params=params, timeout=10.0)
            feats = r.json().get("features") or []
    if not feats:
        return None
    lon, lat = feats[0]["geometry"]["coordinates"]
    return {"lon": lon, "lat": lat, "props": feats[0]["properties"]}
```

Fallback path C (nightly preload) is a stub in v1 — only wire if OAF rate-limits us in prod.

### 4.4 Modified: `app/core/wfs.py`

Add `srsName` to every WFS query when `cfg.wfs_srs_name != "EPSG:4326"` (Berlin) OR always include it explicitly (safer). One-line change to the query-string builder in `wfs()`. Berlin's response byte-exact because Berlin's endpoint auto-projects when srsName is absent (already tested).

### 4.5 Modified: `app/core/scorer.py`

New tier functions:
- `_tier_ferry_transit(distance_m, thresholds)` — same shape as `_tier_tram_transit`
- `_tier_sozialmonitoring_status(status_str, thresholds)` — maps 4-band string to tier
- `_tier_sozialmonitoring_gesamt(gesamt_str, thresholds)` — maps 3-band string to tier
- `_tier_noise_band(band_str, thresholds)` — maps "60-64" → tier; used when `noise_model=="isoline"`

Existing Berlin tier functions untouched.

### 4.6 Modified: `app/routes/lookup.py`

Response shape unchanged. The route dispatches on `cfg.slug` OR on the presence of `cfg.sozialmonitoring_wfs_url` to pick between `gesix_at()` and `sozialmonitoring_at()`. Frontend reads the returned block by key (`gesix` for Berlin, `sozialmonitoring` for Hamburg) — different keys, no ambiguity.

**Nearest-primary-school** (per Q6): Hamburg's `lookup.py` code path calls a new `nearest_gs_public_km_only(lon, lat)` helper that returns `{"school_name": None, "distance_km": round(d/1000, 2)}` — drops the schulname / bsn / catchment fields Berlin returns. Frontend education panel handles the reduced shape.

### 4.7 Modified: `app/routes/config.py`

Returns two new fields for cross-linking:

```python
@router.get("/api/config")
def config(cfg: CityConfig = Depends(get_city)):
    return {
        "slug":            cfg.slug,
        "display_name":    cfg.display_name,
        "default_center":  list(cfg.default_center),
        "attribution":     cfg.attribution,
        "noise_year":      cfg.noise_year,
        "other_cities":    [                      # NEW — powers cross-link pill
            {"slug": "berlin", "display_name": "Berlin", "url": "https://addrlens.de"},
            {"slug": "hamburg", "display_name": "Hamburg", "url": "https://hamburg.addrlens.de"},
        ],
    }
```

Berlin's SPA gains the pill; Hamburg's SPA gains the pill. Zero per-city JS branch.

---

## 5. Frontend design

### 5.1 `web/index.html`

Currently ~29 Berlin literal mentions (title, meta description, OG tags, JSON-LD `addressLocality`, hero SVG `<clipPath id="berlin-clip">`, footer attribution block).

**Refactor pattern:** most literals move behind `/api/config` and are injected client-side by `app.js` (already partially done — Berlin defaults ship inline for SSR/SEO, `/api/config` overrides at boot). Do the same for Hamburg:

- Title, meta description, OG title/description: SSR-ship Berlin defaults; Hamburg's `app/main.py` template-swap on boot based on `CITY` env var (same pattern as Umami injection at `main.py:120`)
- Hero SVG: replace `#berlin-clip` path with a per-city outline path selected from a `web/static/img/city-outlines/{slug}.svg` file. Add a Hamburg outline SVG (public-domain from OSM boundary relation).
- JSON-LD `addressLocality`: template-swap the string based on `cfg.display_name` at `_load_index_html` time (same swap point as Umami snippet injection).
- Footer attribution block: currently hard-codes Berlin's dataset list. Move to a per-city template block sourced from `cfg.attribution` values — the existing `#footer-city-attr` `<p>` gets swapped in `_load_index_html`.
- Hero placeholder search chip `Sybelstrasse 59, Charlottenburg, 10629 Berlin`: swap based on city (Hamburg default: `Reeperbahn 1, St. Pauli, 20359 Hamburg`).

### 5.2 `web/static/app.js`

Current Berlin literals:
- `showStatus('loading', "Reading Berlin's open data…")` at `app.js:64` → `showStatus('loading', ${cfg.display_name}...)` — cfg not yet loaded at that point; either wait for /api/config or read a `data-city` attr from `<body>` set at SSR-injection time
- `dn || 'Berlin'` at `app.js:148` — leave; fallback for a failed /api/config still needs a string
- Cache keys `berlin-lens-mode-v1`, `berlin-lens-compare-v1` etc. — leave. Per-city localStorage isolation happens automatically because the two subdomains have separate localStorage anyway

**Cross-link pill:** new tiny module `web/static/modules/city-switch.js` (~30 LOC). Renders a header pill "Also live in Berlin ↔" / "Also live in Hamburg →" from `cfg.other_cities`. One DOM insert at boot.

### 5.3 `web/static/modules/constants.js`

TILE_DEFS currently hard-codes Berlin-specific explanations for ~30 tiles (references to "Berlin's Baumbestand", "Berlin's Kindertagesstätten BOD dataset", etc.). Two approaches:

- **(a) Per-city constants file** — `constants.berlin.js` + `constants.hamburg.js`, `constants.js` picks one at boot from `document.body.dataset.city`. Simpler but doubles the file.
- **(b) Per-tile explanation on the CityConfig** — each `LensTileConfig.thresholds` gains an optional `explanation` string; `constants.js` becomes a fallback for tiles the server doesn't override.

Recommendation: **(a)** for v1. Hamburg's constants file lives at `web/static/modules/constants.hamburg.js`; the bootstrapper loads one based on `document.body.dataset.city`. Cheaper than (b) which changes the response shape.

Tiles unique to Hamburg (ferry_transit, sozialmonitoring_status, sozialmonitoring_gesamt) get their explanation only in the Hamburg constants file. Berlin's constants file gets a `ferry_transit` explanation as reserved (unused today but ready for future Berlin ferry work).

### 5.4 `web/static/modules/panels/*.js`

Hard-coded Berlin strings to remove:
- `education.js:66`: `<p class="sub">${esc(a.plz)} Berlin</p>` → `${esc(a.plz)} ${cfg.display_name}`
- `education.js:55`: `Berlin 2022 GESIx socioeconomic band` — swap based on cfg presence of gesix vs sozialmonitoring
- `environment.js`: provenance strings currently say `'Berlin BOD · Umweltatlas Luft'` — pull from `cfg.attribution[key]` instead
- `lens/ai.js:156`: `Berlin · AI-generated ${escapeHtml(ts)}` → `${cfg.display_name} · AI-generated ${ts}`
- `lens/ai.js:237`: `a.raw?.bez_name || a.raw?.bezirk || 'Berlin'` → `... || cfg.display_name`

All swaps read from the `cfg` object already in state (loaded from `/api/config`). No new plumbing.

### 5.5 New Hamburg-specific tile renderers

- **Ferry tile** — new render in `panels/connectivity.js` (or a new `panels/ferry.js`). Shows nearest pier name + distance + line list + peak/all-day badge.
- **Sozialmonitoring tiles** — two new renderers in `panels/others.js` (or extend existing gesix renderer to detect which field set the API returned). Status tile shows 4-band badge + stadtteil chip + berichtsjahr. Gesamt tile shows category label.

### 5.6 Cache-busting

The `no-cache, must-revalidate` middleware at `app/main.py:174` already handles per-file revalidation. Adding new modules requires no config change. The `?v=` query on `app.js` entry gets a rev bump when Hamburg lands.

---

## 6. AI-insight templates (inference/)

### 6.1 New files (per Q5 duplicate + edit)

- `inference/templates/lens_newcomer_hamburg_insight.py` — copy of `lens_newcomer_insight.py` (~500 LOC), then hand-edit:
  - System prompt: "Hamburg address-intelligence tool", "expat in first 90 days in Hamburg"
  - Section map: drop the `wochenmarkt` / `xmas_market` / `buergeramt` entries; add `ferry_transit` (Transport section) + `sozialmonitoring_status` (Neighbourhood section) + `sozialmonitoring_gesamt` (Neighbourhood section)
  - Exemplars: rewrite 4-6 examples with Hamburg addresses (Sternschanze, Ottensen, Wilhelmsburg, Blankenese) referencing Kundenzentrum (as a concept, not a lens tile), HVV, Bücherhallen, Elbe ferry
  - MUST-CITE rules: adapt rule 6 (parkzone framing — Hamburg bewohnerparkgebiete has no fee/hour data, different framing)
  - Cache version: `v1` (fresh — no prior Hamburg cache to invalidate)
- `inference/templates/lens_commuter_hamburg_insight.py` — copy of `lens_commuter_insight.py`, same edits with commuter tone

### 6.2 Wiring in `inference/main.py`

```python
TEMPLATES = {
    # existing Berlin templates unchanged
    "lens_newcomer_insight":            lens_newcomer_insight_tpl.run,
    "lens_commuter_insight":            lens_commuter_insight_tpl.run,
    "lens_young_family_insight":        lens_young_family_insight_tpl.run,
    "lens_quiet_living_insight":        lens_quiet_living_insight_tpl.run,
    # new Hamburg templates
    "lens_newcomer_hamburg_insight":    lens_newcomer_hamburg_insight_tpl.run,
    "lens_commuter_hamburg_insight":    lens_commuter_hamburg_insight_tpl.run,
}
```

Env `INFERENCE_REMOTE_TEMPLATES` default extended to include the 2 new Hamburg templates. Cache TTL + grid unchanged from Berlin.

### 6.3 Route dispatch in `app/routes/lens_insight.py`

Template lookup gains a city axis:

```python
_LENS_TEMPLATES = {
    ("berlin",  "young_family"): "lens_young_family_insight",
    ("berlin",  "newcomer"):     "lens_newcomer_insight",
    ("berlin",  "quiet_living"): "lens_quiet_living_insight",
    ("berlin",  "commuter"):     "lens_commuter_insight",
    ("hamburg", "newcomer"):     "lens_newcomer_hamburg_insight",
    ("hamburg", "commuter"):     "lens_commuter_hamburg_insight",
}
```

Cache key at `lens_insight.py:293` already includes city — no cache-collision risk between (berlin, newcomer) and (hamburg, newcomer).

---

## 7. OSM / HVV refresh scripts

### 7.1 `scripts/refresh_osm_amenities.py` — parameterise for city

Current defaults are Berlin-specific:
```python
GEOFABRIK_URL = "https://download.geofabrik.de/europe/germany/berlin-latest.osm.pbf"
```

Add CLI flag `--city hamburg` that maps to Hamburg's Geofabrik URL + output paths (`data/osm/hamburg-amenities.json`, `data/osm/hamburg-addresses.json`). Existing `--pbf-url` override still works. The `_EXCLUDE_CUISINE` set already contains `berlin` and `brandenburg`; add `hamburg` and `nordfriesisch` conservatively (verify OSM tag frequency first).

Two nightly systemd timers (one per city) instead of one; both write to their respective per-city snapshot dirs mounted into the Hamburg app container.

### 7.2 New `scripts/refresh_hvv.py`

Hamburg has no VBB-equivalent CSV. HVV publishes GTFS zip monthly at a UUID-changing URL. Script:

1. Fetch `https://suche.transparenz.hamburg.de/dataset/hvv-fahrplandaten-gtfs-<month>-<year>` HTML landing page
2. Scrape the `daten.transparenz.hamburg.de/.../Upload__hvv_Rohdaten_GTFS_Fpl_YYYYMMDD.ZIP` link
3. Download zip, extract `stops.txt` + `routes.txt` + `trips.txt` + `stop_times.txt`
4. Join stops → routes via trip → route_id
5. Emit:
   - `app/cities/data/hvv_hamburg_su.csv` — S+U-Bahn stops (route_type ∈ {1, 2}, name matches HH pattern) with `mode ∈ {"S", "U", "S+U"}`
   - `app/cities/data/hvv_hamburg_ferry.csv` — ferry piers (route_type=4) with `lines` (comma-separated) + `peak_only` flag derived from calendar.txt

Cadence: monthly cron (mirrors HVV's own re-issue schedule). Failure mode: keep previous CSV (no cold-fail; stations rarely change month-over-month).

### 7.3 Vendored CSV layout for Hamburg

- `app/cities/data/hvv_hamburg_su.csv` — same 4-column shape as `vbb_berlin_su.csv` (name, lat, lon, mode). Loads via existing `Index._load_su_bahn` unchanged.
- `app/cities/data/hvv_hamburg_ferry.csv` — new shape (name, lat, lon, lines, peak_only). Loaded by new `Index._load_ferry`.

---

## 8. Legal + attribution

### 8.1 New files

- `web/hamburg/impressum.html` — Hamburg-specific impressum. Same operator/contact block as Berlin's (same DDG §5 responsible party). Datenquellen block lists only Hamburg data sources (LGV / BUKEA / BSW / BSB / HVV / Geofabrik-Hamburg / OSM). Attribution triplet lives on 3 surfaces per project memory `feedback_attribution_three_surfaces` — landscape doc §5.3 covers the sources block; datenschutzerklaerung + impressum + index footer must all agree.
- `web/hamburg/datenschutzerklaerung.html` — same operator block; per-city data-source list.
- `legal/impressum-hamburg.md` + `legal/datenschutzerklaerung-hamburg.md` — Markdown source (mirrors Berlin's `legal/impressum.md` layout).

### 8.2 Route serving

`app/main.py:145` currently serves `web/impressum.html`. Add per-city branch:

```python
@app.get("/impressum", include_in_schema=False)
def impressum():
    p = WEB_DIR / app.state.city.slug / "impressum.html"
    if not p.exists():
        p = WEB_DIR / "impressum.html"    # Berlin fallback for existing links
    return FileResponse(p, media_type="text/html; charset=utf-8")
```

Hamburg's container serves `web/hamburg/impressum.html`; Berlin's serves `web/impressum.html` (unchanged path). No routing change on Berlin at all.

### 8.3 Sitemap + robots per city

- `web/hamburg/sitemap.xml` — Hamburg URLs only
- `web/hamburg/robots.txt` — Hamburg robots (same allow-list pattern as Berlin)
- App serves them from `web/<slug>/` when present, else falls back to `web/`

---

## 9. Ops + deploy

### 9.1 `docker-compose.prod.yml`

Add second app container:

```yaml
services:
  app:                                    # unchanged — Berlin
    ...
    environment:
      CITY: berlin
      PORT: 8001

  app-hh:                                 # NEW
    build: { context: ., dockerfile: ops/Dockerfile.app }
    env_file: [/srv/addrlens/.env.production]
    environment:
      CITY: hamburg
      PORT: 8002
      INFERENCE_URL: http://inference:8080
    volumes:
      - /srv/addrlens/data/osm-hamburg:/srv/data/osm      # per-city snapshot dir
    mem_limit: 700m
    memswap_limit: 1200m
    restart: unless-stopped
    depends_on:
      inference:
        condition: service_healthy
    networks:
      - addrlens_net

  cloudflared:                            # config-only change (see 9.2)
    ...
```

RAM budget: Berlin app ~700 MB, Hamburg app ~500 MB (smaller OSM snapshot + fewer preloaded polygons — no gesix 447 polygons, ~941 SM polygons instead; smaller trees dataset; ~10 protection zones vs ~80). Inference container ~500 MB. Total ~1.9 GB, comfortably under the Hetzner CX22's 4 GB.

### 9.2 Cloudflare Tunnel

Add second Public Hostname:
- Hostname: `hamburg.addrlens.de`
- Service: `http://app-hh:8002`
- No new tunnel — same tunnel token, second hostname routed via the existing cloudflared container

TLS certificate at Cloudflare edge; no cert work on the box.

### 9.3 Systemd + refresh timers

- `/etc/systemd/system/refresh-osm-hamburg.timer` — Sunday 04:00 CET (offset from Berlin's 03:00 to avoid Geofabrik hammering)
- `/etc/systemd/system/refresh-osm-hamburg.service` — invokes `docker compose ... run --rm --entrypoint python app-hh -m scripts.refresh_osm_amenities --city hamburg`
- `/etc/systemd/system/refresh-hvv.timer` — monthly (day 1, 05:00 CET)
- `/etc/systemd/system/refresh-hvv.service` — invokes `python -m scripts.refresh_hvv` (script writes to both `hvv_hamburg_su.csv` + `hvv_hamburg_ferry.csv`)

### 9.4 `.env.production`

Additive:
```
# Berlin (existing)
UMAMI_WEBSITE_ID=<berlin id>
UMAMI_SCRIPT_URL=<...>

# Hamburg (new — separate Umami site so analytics stay per-city)
UMAMI_WEBSITE_ID_HAMBURG=<hamburg id>
UMAMI_SCRIPT_URL_HAMBURG=<...>
```

`app/main.py` picks the right pair based on `CITY` at boot (2-line change).

### 9.5 Sentry per-city environment

Existing `SENTRY_DSN_APP` is one DSN. Two options: (a) share DSN, tag events with `environment: berlin` / `environment: hamburg` — one project, per-env filter; (b) two DSNs. **Recommend (a)** — cheaper Sentry billing, easier cross-city correlation on shared bugs. The `SENTRY_ENV` env var already exists at `app/main.py:75` — Hamburg container sets `SENTRY_ENV=hamburg-production`.

---

## 10. Testing

### 10.1 Existing suite parity

Every existing pytest is Berlin-scoped and stays Berlin-scoped. No test rewritten for multi-city.

### 10.2 New Hamburg selfcheck

`v0.1/app/cities/hamburg.py` gains its own `if __name__ == "__main__"` block mirroring Berlin's — asserts:
- Newcomer tile-key ordering (13 tiles; ferry_transit + sozialmonitoring_status + sozialmonitoring_gesamt present; buergeramt + wochenmarkt + xmas_market absent)
- Commuter tile-key ordering (10 tiles; commuter_tram_transit absent, commuter_ferry_transit present)
- Only 1 admin card (standesamt)
- `air_model == "none"`, `noise_model == "isoline"`, `fire_zones_available is False`
- `geocoder == "oaf"` and `geocoder_oaf_url` set

Runs via `CITY=hamburg python -m app.cities.hamburg`.

### 10.3 Live Hamburg boot smoke-test

`CITY=hamburg python -m app.selfcheck` — extend the existing selfcheck's live phase to accept a city arg and boot Hamburg's Index. Fails fast on any WFS endpoint that 404s or a field-name mismatch. Should be added to CI as a manual-trigger job (not on every PR — external WFS quota).

### 10.4 Tile-glossary regression

The existing `TILE_GLOSSARY_KEYS` CI gate (per project memory / PR #76) already validates Berlin's tile keys exist in `constants.js`. Extend for Hamburg: `TILE_GLOSSARY_KEYS_HAMBURG` list check runs against `constants.hamburg.js`.

### 10.5 Address-fallback regression

Existing outer-Berlin admin fallback test (PR #78 landmark) stays Berlin-only. Add analogous test for Hamburg: a Blankenese or Wilhelmsburg address that sits far from central Standesamt clusters — verify the `_offices_near_with_fallback` path still returns the single nearest under the max_radius cap. Hamburg's max_radius stays 15 km (Hamburg's diameter is ~30 km, tighter than Berlin's ~40 km; 15 km still safely covers).

### 10.6 Cross-city cache-key isolation

Already covered by `_cache_key("hamburg", ...) != _cache_key("berlin", ...)` asserts at `routes/history.py:190` and `routes/lens_insight.py:293` — no new tests needed.

---

## 11. Rollout plan

Two-stage rollout to bound blast radius:

**Stage 1 — Staging subdomain**
- Deploy `hamburg-staging.addrlens.de` via a third Cloudflare Public Hostname mapped to `app-hh` on `PORT=8002` (Staging + prod share the container; if a prod issue arises, the staging pill is easy to hide)
- Verify each Newcomer + Commuter lens on 5 addresses across all 7 Bezirke: Sternschanze (Altona), Ottensen (Altona), St. Pauli (Mitte), Winterhude (Nord), Blankenese (Altona), Wilhelmsburg (Mitte), Rahlstedt (Wandsbek)
- Verify Raw view for each address (all 6 tabs render honestly; missing tiles show honest copy)
- Verify AI-insight generation for both lenses on 3+ addresses; check that Hamburg exemplars flow through and the LLM cites HVV / Bücherhallen / ferry / Sozialmonitoring correctly
- One-week bake in staging

**Stage 2 — Production promotion**
- Drop staging Cloudflare hostname
- Re-map `hamburg.addrlens.de` to `app-hh:8002`
- Add cross-link pills to both cities' headers (frontend deploy — hits both containers)
- Announcement post + updated GitHub README with "Now live in Hamburg" line
- Sentry monitoring for first 72 h; rollback path is a Cloudflare hostname re-map + docker service stop (no destructive change on Berlin)

**Rollback plan**
- Any Hamburg failure: `docker compose stop app-hh` + remove `hamburg.addrlens.de` hostname at Cloudflare. Berlin unaffected.
- Any shared-code regression (unlikely — all Hamburg changes are additive with Optional gates): `git revert` the offending commit; Berlin container restart takes ~15 s.

---

## 12. Open questions (resolve during impl, not launch blockers)

1. **HVV GTFS licensing verbatim** — pull the current month's dataset metadata block, quote licence + attribution string verbatim in `cfg.attribution["hvv"]`. Placeholder for now: "Hamburger Verkehrsverbund GmbH (dl-de/by-2-0)".
2. **`HH_WFS_Strassenverkehr` endpoint verification** — 404'd during discovery. Confirm current URL at impl time; the archived capabilities XML gives layer names.
3. **Städtebauliche Erhaltungsverordnungen WFS** — only WMS surfaced. Search MetaVer at impl time; if no WFS, drop the "character-preservation" companion (Hamburg has few of these anyway).
4. **HaLm air stations** — worth wiring `air_model="station"` for a nearest-station banner? Not in v1 per Q10, but a note for post-launch iteration.
5. **Kundenzentrum tile revisit** — if Q10-B ships and Hamburg users complain about missing Anmeldung guidance, curate the 16-entry dict in v1.1. Landscape doc has the data ready.
6. **Sozialmonitoring dynamikindex tile** — held for v1.1 per §3.1; ship as a trend chip on the status tile once user feedback confirms interest.

---

## 13. Spec self-review

*(Per brainstorming skill checkpoint — before user review, look at this doc with fresh eyes.)*

**Placeholder scan.** Ellipses (`...`) appear in §4.1 code sketches — intentional (these are illustrative, not final code; the actual `hamburg.py` gets written in Phase 2 with data from the landscape doc). No TODO/TBD markers left in text.

**Internal consistency.**
- §3.1 says Newcomer has 13 tiles; §3.4 confirms −2 +2 vs Berlin's 15 → 15−2+2−2 = 13. Consistent. (Berlin 15 minus wochenmarkt+xmas_market+buergeramt = 12, then +ferry+sozialmonitoring_gesamt = 14 — recount: original list §3.1 shows 13 active tiles labelled 2-11 + 14-16. Numbers 1, 12, 13 are dropped; 3 (ferry), 15 (renamed), 16 (new). Berlin 15 → drop 3 (buergeramt, wochenmarkt, xmas_market) → 12 → rename 1 (tram→ferry) still 12 active + rename gesix (still 12) + add sozialmonitoring_gesamt = **13**. §3.1 last-line "13 active tiles" matches. ✓)
- Commuter §3.2: 10 tiles; §3.4 says "−1 tile +2 tiles = net 10 vs Berlin 10 (parity by count)". Recount: Berlin 10 → drop tram → 9 → add ferry → 10 → gesix rename stays 10 → add sozialmonitoring_gesamt = **11**. Discrepancy — §3.2 shows 10 entries + row 11 which is sozialmonitoring_gesamt_commuter. Fix: §3.4 should say "+2, net 11 vs Berlin 10". **Correction below applied inline.**
- §4.1 CityConfig snippet lists `air_model="none"` for Hamburg; §3.4 confirms air card dropped. Consistent.
- §5.3 recommends approach (a) constants file per city; §7 refresh scripts + §4.1 hamburg.py all rely on the CityConfig being loaded — no dependency conflict.

**Scope check.** Focused on Hamburg extension only. Explicitly excludes YF+QL lenses (Q4) and third-city scaffolding. Fits one implementation plan.

**Ambiguity check.**
- "Fallback to path C" (§4.3) — spec says "stub in v1, only wire if OAF rate-limits". A stub is unambiguous: an `else` branch in `geocode()` that raises `NotImplementedError` for now. Documenting the "wire later" trigger avoids YAGNI now.
- "Verify at impl time" markers (§12) — all bounded to specific WFS endpoints that returned 404 or WMS-only. Impl plan checkpoint required before those datasets ship.

**Inline correction (Commuter tile count):** §3.2 lists 10 tiles + sozialmonitoring_gesamt_commuter as row 11 = 11 tiles total. §3.4 line for Commuter updated: "**−1 tile (tram) +2 tiles (ferry, sozialmonitoring_gesamt) = net 11 vs Berlin 10** (one tile more than Berlin; sozialmonitoring gets a two-tile split per Q5)".

---

## 14. Next step

After user review + approval of this spec:
- Invoke `writing-plans` skill to produce `docs/superpowers/plans/2026-09-20-hamburg-onboarding-plan.md`
- Plan will decompose into ~15-25 discrete steps with TDD checkpoints, one commit per step
- Then execution phase per that plan

Do NOT proceed to writing-plans until user signs off on this spec.
