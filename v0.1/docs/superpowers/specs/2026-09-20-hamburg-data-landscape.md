# Hamburg data landscape for AddrLens

**Author:** discovery spike, 2026-09-20
**Status:** Phase 0 deliverable — read-only research. Not a design doc, not a plan. Feeds `2026-09-20-hamburg-onboarding-design.md` (Phase 1, not yet written).
**Scope:** For every Berlin dataset, source, and admin directory that AddrLens uses today, report the Hamburg equivalent (or `MISSING`), the WFS URL, layer name, output format, field names, licence, feature count, and any structural divergence that will affect the eventual `CityConfig`.

Do not treat this doc as authoritative for coding — verify each `DescribeFeatureType` against the live endpoint at implementation time. Field names in the tables below come from `GetCapabilities` responses and MetaVer metadata cards; a handful are marked `unverified — requires DescribeFeatureType` and MUST be inspected before wiring.

---

## 1. Executive summary

Hamburg's Urban Data Platform (LGV) publishes a dense WFS ecosystem at `geodienste.hamburg.de` with metadata cross-listed on `metaver.de` and `suche.transparenz.hamburg.de`. It supports the same conceptual OGC WFS 2.0.0 workflow as Berlin's `gdi.berlin.de`, but four platform-wide differences apply to every request:

| Aspect | Berlin (`gdi.berlin.de`) | Hamburg (`geodienste.hamburg.de`) |
|---|---|---|
| Default CRS | EPSG:25833 | **EPSG:25832** — every AddrLens request must set `srsName=EPSG:4326` explicitly |
| GeoJSON output format string | `application/json` | **`application/geo+json`** — `application/json` returns HTTP 400 |
| XML namespaces | mostly `<layer>:` (single flat namespace per WFS) | **three coexist**: `de.hh.up:*` (majority), `app:*` (Kitas / Bezirke / Stadtteile / Badegewässer), `dog:*` (address gazetteer) — must be per-layer configurable, not global |
| Licence | Mixed `dl-de/by-2-0` and `dl-de/zero-2-0` per layer | **Universal `dl-de/by-2-0`** across every layer inspected — simpler attribution model, single credit line covers all city data |

The `CityConfig.wfs_output_format` field (introduced in `v0.1/app/cities/base.py:26` with the exact comment "Hamburg geodienste.hamburg.de expects `application/geo+json`") already anticipates this. The `srsName` and namespace differences are new axes.

Out of ~20 Berlin datasets audited, **16 have a verified Hamburg WFS equivalent** on `geodienste.hamburg.de` with usable output. **4 are missing or so structurally different they require redesign or drop** (address JSON, air-per-street, fire response zones, city-wide pool layer). Two Hamburg-specific signals not present in Berlin are worth adding: **Sozialmonitoring dynamikindex** (annual socioeconomic trend, no Berlin equivalent) and **HADAG ferry** (real commute mode via HVV GTFS).

Curated admin office directories: **all 5 Berlin office types (Bürgeramt / Standesamt / Finanzamt / LEA / Arbeitsagentur) have a Hamburg analogue**, but Hamburg publishes none as WFS points. Full hand-curation required, extending Berlin's pattern of the four curated dicts to five (Hamburg's Bürgeramt-equivalent is called **Kundenzentrum** / "Hamburg Service vor Ort"). 16 Kundenzentrum + 7 Standesamt + 14 Finanzamt + 1 Amt-für-Migration + 7 Arbeitsagentur = **45 offices** to seed by hand from `hamburg.de` directories, mirroring Berlin's `_STANDESAMTS_BY_BEZIRK` / `_FINANZAMTS` / `_ARBEITSAGENTURS` / `_LEA_OFFICE` pattern.

---

## 2. WFS endpoints — dataset-by-dataset mapping

Every row below is verified against a live `GetCapabilities` response unless flagged `unverified`. Output-format column: `geo+json` = `application/geo+json` supported; otherwise the format actually returned.

### 2.1 Addresses (address geocoding — used by `/api/lookup` and `/api/suggest`)

| Aspect | Value |
|---|---|
| Berlin equivalent | `gdi.berlin.de/services/wfs/adressen_berlin`, layer `adressen_berlin:adressen_berlin`, `str_name / hnr / plz` |
| Hamburg WFS | `https://geodienste.hamburg.de/HH_WFS_DOG?SERVICE=WFS&REQUEST=GetCapabilities` |
| typeName | `dog:Hauskoordinaten` (address points) — plus `dog:Strassen`, `dog:Postleitzahlgebiete`, `dog:Ortsteile` |
| Output format | **GML 3.1.1 / 3.2.1 ONLY — no GeoJSON, no CSV** |
| Licence | dl-de/by-2-0 |
| Authority | LGV + Statistikamt Nord (Gazetteer joint operation) |
| Count | ~350k address points (unpublished; product doc estimate) |
| **Divergence** | **Big pipeline change**. Berlin's flat-JSON pipe (`wfs()` → `json()["features"]`) won't work. Options: (a) GML parser (fastkml / lxml) branch in `app.core.wfs.wfs()`, (b) route Hamburg addresses via the **OGC API Features endpoint** at `https://api.hamburg.de/datasets/v1/...` which returns JSON, (c) prefetch full GML nightly into an in-memory index (mirrors what `app.core.address_index` already does for the /api/suggest side). Option (c) or (b) preferred. |

**Recommendation:** Use OGC API Features endpoint for the runtime geocoder path (analogous to Berlin's WFS geocoder in `Index.geocode`). Continue prefetching a nightly address JSON snapshot (via the OSM address extractor in `scripts/refresh_osm_amenities.py` — Hamburg has address density ~65-75 % of Berlin's, projected 250-320k `addr:housenumber` OSM entries) for the /api/suggest prefix index. This avoids a runtime GML parser in `app.core.wfs`.

### 2.2 Schools + primary-school catchments

| Aspect | Schools | Catchments |
|---|---|---|
| Berlin equivalent | `wfs/schulen` → `schulen:schulen` + `schulen:schulen_esb` | (bundled with schools) |
| Hamburg WFS | `https://geodienste.hamburg.de/HH_WFS_Schulen?SERVICE=WFS&REQUEST=GetCapabilities` | `https://geodienste.hamburg.de/HH_WFS_Regionaler_Bildungsatlas_Einzugsgebiete_Schulwahl?SERVICE=WFS&REQUEST=GetCapabilities` |
| typeNames | `de.hh.up:staatliche_schulen`, `de.hh.up:nicht_staatliche_schulen`, `de.hh.up:hh_schulen_eingaenge` | `de.hh.up:einzug_einzugsgebiete_primarstufe`, `de.hh.up:einzug_einzugsgebiete_sekundarstufe` |
| Output format | geo+json, GML, CSV | geo+json, GML, CSV |
| Licence | dl-de/by-2-0 | dl-de/by-2-0 |
| Authority | Behörde für Schule und Berufsbildung (BSB) via LGV | BSB |
| Count | ~470 state + ~90 private | ~500 primary + ~200 secondary catchments |
| Fields (metadata; verify via DescribeFeatureType) | Name, Schulnummer, Zweigstelle flag, Schulform, Erwachsenenbildung flag, ReBBZ-Standort, Schüleranzahl, Straße/HNR/PLZ/Ort, Telefon, Fax, E-Mail, Homepage | `bezirk`, `schulid` (unverified) |
| **Divergence** | Public/private is layer-split, not an attribute like Berlin's `traeger='öffentlich'`. Requires UNION of two `load_point_layer_raw` calls. Bilingual/SESB-analog concept doesn't apply — Hamburg has fewer international-school programs and no direct equivalent to Berlin's SESB. | **Hamburg catchments are per statistical district of residence, not one polygon per primary school.** Berlin's `esb_to_gs` reverse index (`Index._load_catchments_and_schools`) does not translate. The "your primary school" question needs a different query (probably nearest-primary + advisory copy that Hamburg families should verify with BSB directly). |

### 2.3 Kitas

| Aspect | Value |
|---|---|
| Berlin equivalent | `wfs/kita`, layer `kita:kita`, `e_name / e_platz / t_art / ang_1` |
| Hamburg WFS | `https://geodienste.hamburg.de/HH_WFS_KitaEinrichtung?SERVICE=WFS&REQUEST=GetCapabilities` |
| typeName | `app:KitaEinrichtungen` (note `app:` namespace, not `de.hh.up:`) |
| Output format | geo+json, GML, CSV |
| Licence | dl-de/by-2-0 |
| Authority | Behörde für Arbeit, Gesundheit, Soziales, Familie und Integration (BAGFI) |
| Count | ~1100 (unpublished; hamburg.de count) |
| Fields | Kita/Krippe/Hort/Vorschule categorisation confirmed in metadata; capacity / operator / Konzeption fields unverified — requires DescribeFeatureType |
| **Divergence** | Namespace `app:` differs — first case where the loader must know the namespace per layer. |

### 2.4 Hospitals

| Aspect | Value |
|---|---|
| Berlin equivalent | `wfs/krankenhaeuser`, two layers `plankrankenhaeuser` + `weitere_krankenhaeuser` |
| Hamburg WFS | `https://geodienste.hamburg.de/HH_WFS_Krankenhaeuser?SERVICE=WFS&REQUEST=GetCapabilities` |
| typeName | `de.hh.up:gesundheit_krankenhaeuser` (single layer) |
| Output format | geo+json, GML, CSV |
| Licence | dl-de/by-2-0 |
| Authority | Behörde für Wissenschaft, Gesundheit und Verbraucherschutz (BWGV) |
| Count | ~35 |
| Fields (per metadata) | geplante Bettenzahl, teilstationäre Plätze, Notfall/Unfallversorgung, Geburtshilfe, Fachabteilungen |
| **Divergence** | One layer, not two. `Index._load_hospitals` splits by `_layer` kind tag ("plan" / "weitere") — Hamburg has no such split, so a single-layer path is cleaner. |

### 2.5 Trinkwasserbrunnen (drinking fountains)

| Aspect | Value |
|---|---|
| Berlin equivalent | `wfs/trinkwasserbrunnen`, ~240 standalone points |
| Hamburg WFS | `https://geodienste.hamburg.de/wfs_wc_mit_trinkbrunnen?SERVICE=WFS&REQUEST=GetCapabilities` |
| typeName | `de.hh.up:wc_mit_trinkbrunnen` |
| Output format | geo+json, GML, CSV |
| Licence | dl-de/by-2-0 |
| Authority | BUKEA / Stadtreinigung Hamburg |
| Count | 54 total (44 SRH + 10 Hamburg Wasser), of which some fraction actually have a Trinkbrunnen (property of the WC installation) |
| **Divergence** | **Semantically thinner than Berlin's dataset.** In Hamburg, a fountain is a property of a public toilet, not a standalone amenity. The Young Family lens "fountain nearby" concept doesn't have the same weight — 40-ish citywide fountains vs Berlin's 240 means green-tier reach is rare. **Option:** drop from Hamburg Young Family lens (when YF ships later), or keep with adjusted thresholds + honest caveat "Hamburg has only ~40 fountains city-wide". |

### 2.6 Grünanlagen + Spielplätze (parks + playgrounds)

| Aspect | Parks | Playgrounds |
|---|---|---|
| Berlin equivalent | `wfs/gruenanlagen` → `gruenanlagen:gruenanlagen` + `gruenanlagen:spielplaetze` (combined WFS) | (same WFS) |
| Hamburg WFS | `https://geodienste.hamburg.de/HH_WFS_Gruenplan?SERVICE=WFS&REQUEST=GetCapabilities` | `https://geodienste.hamburg.de/wfs_spielplaetze?SERVICE=WFS&REQUEST=GetCapabilities` |
| typeName | `de.hh.up:verzeichnis_oeffentlicher_gruenanlagen`, `de.hh.up:kleingartenanlagen`, `de.hh.up:friedhoefe` | `de.hh.up:spielplaetze_hh` |
| Output format | geo+json, GML, CSV | geo+json, GML, CSV |
| Fields (Grünplan) | IDNR, Grünflächenart, Lage, Fläche, Bezirk, Stadtteil, Eigentum | (unverified — requires DescribeFeatureType) |
| Licence | dl-de/by-2-0 | dl-de/by-2-0 |
| Authority | BUKEA | BUKEA |
| **Divergence** | Two endpoints instead of Berlin's combined one. `Index._load_catchments_and_schools`-style parallel loader pattern applies. Grünplan is quarterly-refreshed (Jan/Apr/Jul/Oct). Bonus: Kleingartenanlagen + Friedhöfe are separate layers Berlin combines under one grünanlagen bucket — Hamburg gives finer control. | |

### 2.7 Strategische Lärmkarten (façade noise)

| Aspect | Value |
|---|---|
| Berlin equivalent | `wfs/ua_stratlaerm_2022`, per-façade point levels — attributes `ges_den`, `str_den`, `sch_den`, `flg_den`, `_n` night variants |
| Hamburg WFS (road) | `https://geodienste.hamburg.de/HH_WFS_Strassenverkehr?SERVICE=WFS&REQUEST=GetCapabilities` — **capabilities URL returned HTTP 404 during research 2026-09-20**; archived at `https://archiv.transparenz.hamburg.de/hmbtgarchive/HMDK/hh_wfs_strassenverkehr_162854_snap_2.XML`. Endpoint may have been renamed; verify at impl time |
| typeName (road) | `de.hh.up:strassenverkehr_tag_abend_nacht_2022` (LDEN), `de.hh.up:strassenverkehr_nacht_2022` (LNight) |
| Rail | Separate service — endpoint name unverified |
| Aircraft | OGC API Features at `https://api.hamburg.de/datasets/v1/strategische_laermkarten` per BUKEA metadata |
| Output format | GML confirmed; GeoJSON via OAF |
| Licence | dl-de/by-2-0 |
| Authority | BUKEA |
| Year | 2022 (round 4 EU-mapping) |
| **Divergence (structural)** | **Isophone polygons per source, NOT per-façade points.** Berlin publishes a dB value on each address's building façade; Hamburg publishes 55-59 dB / 60-64 dB / 65-69 dB / … / ≥75 dB polygons per source. Berlin's `noise_at()` (a single point-in-polygon returning attributes) becomes **6 spatial joins per address per tile** (road×day, road×night, rail×day, rail×night, air×day, air×night). Different tile logic: instead of "your façade reads 58 dB", it's "your address falls inside the road-day 55-59 dB band + rail-night 50-54 dB band + air-day <50 band". |

**Recommendation:** rewrite `noise_at()` for Hamburg as a per-source-point-in-polygon rollup; return `{road_den_band: "55-59", road_n_band: "50-54", rail_den_band: "50-54", …}` and translate to tier in the scorer. Berlin path unchanged.

### 2.8 Air quality (NO₂ street-level)

| Aspect | Value |
|---|---|
| Berlin equivalent | `wfs/ua_luftreinhalteplan_2018_2025`, per-Straßenabschnitt NO₂ 2020 modelling — every street segment gets a `no2_2020` value |
| Hamburg option A: HaLm stations | `https://luft.hamburg.de/` — 15 monitoring stations city-wide, WMS + WFS references in metaver docuuid `F2418743-...`; standalone WFS URL not resolvable in this research session (unverified) |
| Hamburg option B: per-segment modelling | **MISSING.** No equivalent to Berlin's Luftreinhalteplan trend-scenario raster. Hamburg publishes only station-level readings, not a per-street modelled dataset. |
| Licence | dl-de/by-2-0 |
| Authority | BUKEA / Institut für Hygiene und Umwelt |
| **Divergence** | **Big miss.** Berlin's `air_at()` returns a per-street NO₂ value; Hamburg has no equivalent modelling. Options: (a) drop the NO₂ tile from Hamburg lenses, (b) use nearest-station distance as a proxy (weak — 15 stations covering ~750 km², ~10 km spacing typical), (c) commission or wait for a Hamburg air-modelling dataset (won't happen for launch). **Recommend (a) drop tile with honest "Hamburg does not publish per-street air modelling" caveat.** |

### 2.9 Umweltatlas heat / bioclimate (PET 14:00)

| Aspect | Value |
|---|---|
| Berlin equivalent | `wfs/ua_klimabewertung_2022`, per-block `pet14h_tag_klar` PET class string |
| Hamburg WFS | `https://geodienste.hamburg.de/wfs_stadtklimaanalyse_hamburg_2023?Service=WFS&Request=GetCapabilities` |
| typeName (PET day) | `de.hh.up:bewertung_tags_siedlung_verkehr` — PET at 14:00 for built-up land |
| typeName (PET night) | `de.hh.up:bewertung_nachts_siedlung_verkehr` — mean Lufttemperatur 04:00 |
| typeName (green day) | `de.hh.up:bewertung_tags_gruenfl` — Aufenthaltsqualität in green spaces |
| Companion layers | `windvektoren_4_uhr`, `flurwinde_kaltluftabfluesse`, `besondere_funktion_luftaustausch`, `kaltlufteinwirkbereich`, `gebaeude_bestand_planung_stand_12_2022` |
| Output format | geo+json, GML, CSV |
| Licence | dl-de/by-2-0 |
| Authority | BUKEA via LGV |
| **Divergence** | **Direct 1:1 analogue.** Same PET-14:00 methodology as Berlin. Field-name map differs (`bewertung_tags_...` vs Berlin's `pet14h_tag_klar`); polygon grain differs slightly (Hamburg uses analysis raster/polygon vs Berlin's residential block). Bonus: Hamburg publishes PET-night + green-space quality as separate layers — Berlin doesn't. Could enrich the Young Family / Quiet Living heat tile with a night-heat companion (post-launch). |

### 2.10 Baumbestand (street trees)

| Aspect | Value |
|---|---|
| Berlin equivalent | `wfs/baumbestand`, layer `strassenbaeume`, fields `art_dtsch / kronedurch / baumhoehe / pflanzjahr / standalter / strname` — ~435k features |
| Hamburg WFS | `https://geodienste.hamburg.de/HH_WFS_Strassenbaumkataster?SERVICE=WFS&REQUEST=GetCapabilities` |
| typeName | `de.hh.up:strassenbaumkataster` |
| Output format | geo+json, GML, CSV |
| Fields (verified via DescribeFeatureType) | `baumid` (int), `baumnummer` (string), `gattung` / `gattung_latein` / `gattung_deutsch`, `art` / `art_latein` / `art_deutsch`, `sorte` / `sorte_latein` / `sorte_deutsch`, `pflanzjahr` (int, has `0` sentinels for pre-inventory trees), `kronendurchmesser` (int), `kronendurchmesser_z` (string, uncertainty flag), `stammumfang` (int), `stammumfang_z` (string), `strasse`, `hausnummer`, `ortsteil_nr` (int), `stadtteil`, `bezirk`, `daten_aus_vorjahr` (int flag), `geom` (MultiPoint) |
| Licence | dl-de/by-2-0 |
| Authority | BUKEA |
| Refresh | 1 January annually |
| Count | ~245k street trees (published figure) — coverage smaller than Berlin's 435k, in line with city size |
| **Divergence** | **No `hoehe` (height) field.** Berlin's Quiet Living `street_trees` tile uses crown-diameter for canopy area (physics unchanged), but Berlin's tree drilldown shows tallest tree height — Hamburg cannot. Compute age from `pflanzjahr` + current year (null-handle `pflanzjahr = 0` sentinels). Taxonomy is split 6-way (`gattung / art / sorte × latein / deutsch`) vs Berlin's 2-way — richer, needs per-city rendering. Companion **Straßenbaumkataster Hamburger Hafen** available for waterfront addresses (skip for launch). |

### 2.11 Ruhige Gebiete (§47d BImSchG quiet zones)

| Aspect | Value |
|---|---|
| Berlin equivalent | `wfs/ruhigegebiete_2018`, layer `ruhigegeb2018_2023`, fields `name / g_art / groesse_ha / gebnr` |
| Hamburg WFS | `https://geodienste.hamburg.de/HH_WFS_Ruhige_Gebiete?SERVICE=WFS&REQUEST=GetCapabilities` — plus companion `HH_WFS_Ruheinseln` for smaller informal "quiet islands" |
| typeName | `de.hh.up:ruhige_gebiete_hamburg` |
| Output format | geo+json, GML, CSV |
| Licence | AccessConstraints empty in caps; MetaVer records dl-de/by-2-0 |
| Authority | BUKEA |
| Fields | Polygon name; LDen threshold (<50 dB) & min size (50 ha) per §47d definition; exact attribute keys unverified — requires DescribeFeatureType |
| **Divergence** | Direct 1:1 analogue. Ruheinseln companion is a nice-to-have. |

### 2.12 Erhaltungssatzungsgebiete (§172 BauGB)

| Aspect | Value |
|---|---|
| Berlin equivalent | `wfs/erhaltungsverordnungsgebiete` — two layers `erhaltgeb_em` (Milieuschutz) + `erhaltgeb_es` (character preservation), fields `gebietsname / schluessel / f_in_kraft / bezirk / fl_ha` |
| Hamburg WFS (soziale/Milieuschutz) | `https://geodienste.hamburg.de/HH_WFS_SozErhVO?SERVICE=WFS&REQUEST=GetCapabilities` |
| typeNames | `de.hh.up:sozerhvo_inkraft` (in force) + `de.hh.up:sozerhvo_inaufstellung` (in preparation) |
| Fields (verified) | `gebietsname` (string), `bezirk` (**integer code**), `datum` (dateTime), `fundstelle` (string), `internet` (string), `geom` (MultiSurface inkraft, Surface inaufstellung) |
| Hamburg WFS (städtebauliche/character) | `HH_WMS_Erhaltungsverordnung` — WMS only; WFS not surfaced in search (unverified) |
| Licence | dl-de/by-2-0 |
| Authority | Behörde für Stadtentwicklung und Wohnen (BSW) |
| Count | ~7 in force + ~3 in preparation (as of 2026-09; Hamburg has been expanding — WFS is authoritative, don't hard-code) |
| **Divergence** | **`bezirk` is an integer code, not a string name — needs 7-entry lookup `{1: "Hamburg-Mitte", 2: "Altona", …}`. No `size_ha` field — compute from geometry.** Coverage is ~1/8 of Berlin's (Berlin has ~80+ Milieuschutzgebiete, Hamburg ~10). Most Hamburg addresses will get the negative case; tile copy needs adjustment so a "not in a Milieuschutz" answer doesn't read as alarming (Berlin frames it as "standard tenancy rules apply" — carry that framing over). |

### 2.13 Bezirks-/Stadtteilgrenzen

| Aspect | Value |
|---|---|
| Berlin equivalent | `wfs/alkis_bezirke`, layer `bezirksgrenzen`, field `namgem` — 12 Bezirke |
| Hamburg WFS | `https://geodienste.hamburg.de/HH_WFS_Verwaltungsgrenzen?SERVICE=WFS&REQUEST=GetCapabilities` |
| typeNames | `app:bezirke` (7 Bezirke) + `app:stadtteile` (104 Stadtteile) |
| Output format | geo+json, GML, CSV |
| Licence | dl-de/by-2-0 |
| Authority | LGV |
| Count | 7 + 104 |
| **Divergence** | 7 Bezirke vs 12 (Standesamt-per-Bezirk dict is smaller). 104 Stadtteile is the Ortsteil-analog. `app:` namespace. |

### 2.14 Fire stations + response zones

| Aspect | Value |
|---|---|
| Berlin equivalent | `wfs/feuerwehr` — two layers `a_feuerwehr_standorte` (points) + `b_feuerwehr_einsatzbereiche` (polygons) |
| Hamburg WFS (stations) | `https://geodienste.hamburg.de/HH_WFS_feuerwehrstandorte?SERVICE=WFS&REQUEST=GetCapabilities` |
| typeNames | `de.hh.up:berufsfeuerwehr` (professional) + `de.hh.up:freiwillige_feuerwehr` (volunteer) |
| Response zones | **MISSING as citywide layer.** Only a Eimsbüttel-district pilot (F13, F15) exists as a proof-of-concept metadata record. |
| Output format | geo+json, GML, CSV |
| Licence | dl-de/by-2-0 |
| Authority | Behörde für Inneres und Sport |
| **Divergence** | Zone-per-address point-in-polygon is impossible for Hamburg. `Index.fire_rescue` returns a `zone_name` + `zone_code` — for Hamburg, these fall back to `None` and only the nearest-station + top-3 sub-fields are meaningful. Tile copy needs to acknowledge "responsibility zone data not published in Hamburg". |

### 2.15 Tempolimits (speed exceptions)

| Aspect | Value |
|---|---|
| Berlin equivalent | `wfs/tempolimits`, single polymorphic layer `hoechstgeschwindigkeit`, fields `wert_ves / zeit_t / durch_t` |
| Hamburg WFS | `https://geodienste.hamburg.de/HH_WFS_Zulaessige_Hoechstgeschwindigkeiten?SERVICE=WFS&REQUEST=GetCapabilities` |
| typeNames | 5 layers: `zulaessige_hoechstgeschwindigkeiten` (baseline), `tempo30zonen`, `tempo20zonen`, `verkehrsberuhigte_bereiche`, `zulaessige_hoechstgeschwindigkeiten_sonderregelung` (time-restricted / school / noise) |
| Output format | geo+json, GML, CSV |
| Licence | dl-de/by-2-0 |
| Authority | Behörde für Verkehr und Mobilitätswende (BVM) |
| **Divergence** | **5 layers instead of 1.** AddrLens needs a per-layer priority stack (`sonderregelung > tempo20 > tempo30 > verkehrsberuhigt > baseline`). Berlin's `tempolimit_at` returns the nearest exception; Hamburg's needs a stacked-lookup returning the strictest applicable rule. Cleaner data model but 5× the loader calls. |

### 2.16 Übergeordnetes Straßennetz (arterial roads)

| Aspect | Value |
|---|---|
| Berlin equivalent | `wfs/strnetz`, layer `uebergeordnetes_strnetz`, fields `strassenname / strassenklasse1` |
| Hamburg WFS | `https://geodienste.hamburg.de/HH_WFS_Strassen_und_Wegenetz?SERVICE=WFS&REQUEST=GetCapabilities` (33 FeatureTypes) |
| typeNames | `bab_ast` (Autobahn), `bundesstrassen_freie_strecke`, `bundesstrassen_ortsdurchfahrt`, `stadtstrassen`, `strassennetz_gesamt` (union) |
| Output format | geo+json, GML, CSV |
| Licence | dl-de/by-2-0 |
| Authority | BVM via LGV |
| **Divergence** | Berlin uses one layer split by `strassenklasse1`; Hamburg uses one layer per class. Aggregate at load time or pick `strassennetz_gesamt`. |

### 2.17 Schwimmbäder (public pools)

| Aspect | Value |
|---|---|
| Berlin equivalent | `wfs/schwimmbaeder_berlin`, layer `schwimmbaeder`, full metadata per pool |
| Hamburg WFS | `https://geodienste.hamburg.de/HH_WFS_Sportstaetten?SERVICE=WFS&REQUEST=GetCapabilities` (single layer mixing all sport facilities) |
| typeName | `de.hh.up:sportstaetten` |
| Fields (partial) | Name, Adresse, Träger, Ausstattung — no pool-specific hours/category |
| Bäderland (operator) | **Not in WFS.** 24 pools directory published at `https://www.baederland.de/baeder/alle-baeder/` (HTML) |
| Licence | dl-de/by-2-0 (WFS) |
| Authority | Bezirksamt Hamburg-Mitte (WFS) / Bäderland Hamburg GmbH (operator) |
| **Divergence** | **Missing as filterable first-class dataset.** Options: (a) scrape baederland.de and hand-seed a curated dict (like Berlin's admin offices — 24 entries), (b) drop pools tile from Hamburg. **Recommend (a)**: pools are a Quiet Living / recreational signal users expect; 24 entries is manageable curation. |

### 2.18 Badegewässer (natural swim spots)

| Aspect | Value |
|---|---|
| Berlin equivalent | `wfs/badegewaesser`, layer `aa_badestellen`, fields `badegewaes / eu_einst / link / cyano` |
| Hamburg WFS | `https://geodienste.hamburg.de/HH_WFS_Badegewaesser?SERVICE=WFS&REQUEST=GetCapabilities` |
| typeNames | `app:badegewaesser` (14 sites, 16 spots) + `app:badegewaesser_proben` (sample time series) |
| Output format | geo+json, GML, CSV |
| Licence | dl-de/by-2-0 |
| Authority | BUKEA |
| **Divergence** | Two layers; cyano warnings live on the `_proben` samples layer — join by site ID. `app:` namespace. |

### 2.19 Parkraumbewirtschaftung (resident parking)

| Aspect | Value |
|---|---|
| Berlin equivalent | `wfs/parkraumbewirtschaftung`, layer `parkzonen`, fields `parkzone / bezirk / zeiten / gebuehr / bemerkung` (fees & hours in-WFS) |
| Hamburg WFS | `https://geodienste.hamburg.de/HH_WFS_bewohnerparkgebiete?SERVICE=WFS&REQUEST=GetCapabilities` |
| typeName | `de.hh.up:bewohnerparkgebiete` |
| Output format | geo+json, GML, CSV |
| Licence | dl-de/by-2-0 (per MetaVer) |
| Authority | LGV / Landesbetrieb Verkehr |
| **Divergence** | **Hourly fees + enforcement hours are NOT in the WFS**, only in the Verordnung PDF. Berlin exposes both directly. AddrLens will need a small static enrichment dict per Hamburg zone (or omit fee/hours info from the tile for launch, showing only "inside/outside zone" + edge distance). |

### 2.20 Extra Hamburg-only signal: Sozialmonitoring (GESIx-analog)

| Aspect | Value |
|---|---|
| Berlin equivalent | `wfs/gssa_gesix2022`, per-Planungsraum `gesix_wert` numeric → app bins into quintile — 447 polygons, 5-year refresh |
| Hamburg WFS | `https://geodienste.hamburg.de/wfs_sozialmonitoring?SERVICE=WFS&REQUEST=GetCapabilities` |
| typeName | `de.hh.up:sozialmonitoring` |
| Fields (verified via DescribeFeatureType) | `jahr` (int), `jahr_timestamp` (dateTime), `bevoelkerung` (int), `berichtsjahr` (string), `statgeb` (string, Statistisches Gebiet ID), `stadtteil` (string), **`statusindex`** (string, 4-level: "hoch / mittel / niedrig / sehr niedrig"), **`dynamikindex`** (string, 3-level: "positiv / stabil / negativ"), `gesamtindex` (string), `geom` (MultiSurface) |
| Output format | geo+json, GML, CSV |
| Default CRS | EPSG:25832 (also 4326 available) |
| Licence | dl-de/by-2-0 |
| Authority | Behörde für Stadtentwicklung und Wohnen (BSW) |
| Count | **941 polygons** (Statistische Gebiete, ~2200 residents each; 857 analysed for polygons with ≥300 residents) |
| Refresh | **Annual** (Berlin's GESIx is 5-yearly) |
| **Divergence & bonus** | **Categorical string, not numeric.** Berlin's quintile-from-numeric-rank logic doesn't apply — Hamburg publishes the classification pre-computed. Simpler tile: 4-band badge (hoch/mittel/niedrig/sehr niedrig). **Bonus**: `dynamikindex` is a second signal Berlin doesn't have — surfaces as a trend chip ("stable" / "improving" / "declining"). Polygon grain is 2× finer than Berlin's (2200 vs 10000 residents) — noisier per-polygon read; frontier copy should acknowledge. |

---

## 3. HVV transit + Geofabrik

### 3.1 HVV GTFS (S-Bahn / U-Bahn / Bus / Ferry / RE / RB / AKN — one feed)

| Aspect | Value |
|---|---|
| Berlin equivalent | VBB UMBW.zip → UMBW.csv (S/U only, `mode` column) + separate BOD tram WFS |
| Hamburg dataset | `hvv Fahrplandaten (GTFS)` — monthly re-issue on Transparenzportal |
| Landing page | `https://suche.transparenz.hamburg.de/dataset/hvv-fahrplandaten-gtfs-mai-2025-bis-dezember-2025` (URL varies per monthly issue) |
| Direct file (2025-05 issue) | `https://daten.transparenz.hamburg.de/Dataport.HmbTG.ZS.Webservice.GetRessource100/GetRessource100.svc/1a176fcb-4971-4baf-bae8-545dc9d4454d/Upload__hvv_Rohdaten_GTFS_Fpl_20250505.ZIP` — **URL contains a UUID that changes monthly**, fetcher must resolve current issue via landing page |
| Format | GTFS static (agency / stops / routes / trips / stop_times / calendar / shapes) |
| Licence | **dl-de/by-2-0** (not CC-BY-4.0 like VBB) — attribution: "Hamburger Verkehrsverbund GmbH" |
| Modes included | S-Bahn (route_type=1 subway or 2 rail depending on network), U-Bahn (1), Bus (3), **Fähre (4)**, RE + RB (2), AKN |
| File size | ~40 MB zipped |
| Refresh | Monthly (Berlin's VBB updates ~annually) |
| Suitability | **GREEN** — single feed replaces VBB CSV + tram WFS. Filter `stops.txt` by `location_type=1` and join to `routes.txt` for mode taxonomy. Reproducible in a `scripts/refresh_hvv.py` mirroring `scripts/refresh_vbb.py`. |

### 3.2 HADAG ferry (Elbe-crossing commuter transit)

- **Embedded in the HVV GTFS** — no separate feed. HADAG lines appear under `routes.txt` with `route_type=4` (ferry) plus standard `stops.txt` entries for each Anleger.
- **21 landing bridges** covering lines 61, 62, 64, 68, 72, 73, 75.
  - All-day: 62 (Landungsbrücken–Finkenwerder), 64 (Finkenwerder–Teufelsbrück), 72 (Landungsbrücken–Elbphilharmonie)
  - Peak/weekday commuter: 61 (Neuhof), 68 (Airbus factory), 73 (Wilhelmsburg), 75 (Steinwerder)
- **Architectural implication:** new mode `ferry` in `CityConfig` (Optional per city, so Berlin config leaves it None). Hamburg's Newcomer + Commuter lens tile lists include a ferry tile that replaces the tram tile slot. Tile threshold: 5-10 min walk to nearest pier (piers are relatively sparse — Elbe-side only — so tighter than Berlin's tram thresholds).

### 3.3 Regional rail (curated list — same pattern as Berlin's `regional_rail_stations`)

| name | lat | lon | Notes |
|---|---|---|---|
| Hamburg Hauptbahnhof | 53.55278 | 10.00639 | ICE + all RE/RB, HVV hub |
| Hamburg-Altona | 53.55194 | 9.93500 | ICE + RE |
| Hamburg Dammtor | 53.56083 | 9.98944 | RE + IC |
| Hamburg-Harburg | 53.45611 | 9.99169 | RE Hannover / Bremen |
| Hamburg-Bergedorf | 53.48944 | 10.20639 | RE 1 to Rostock |
| Hamburg-Rahlstedt | 53.60333 | 10.15806 | RB 81 |
| Hamburg-Tonndorf | 53.59306 | 10.13361 | RB 81 |
| Wilhelmsburg | 53.4989 | 10.0069 | RE Elbe crossing |
| Pinneberg | 53.65917 | 9.79139 | RE / RB west |
| Elbgaustraße | 53.6103 | 9.9036 | RB west |
| Neugraben | 53.4728 | 9.8611 | Metronom / RB |
| Aumühle | 53.5300 | 10.3167 | RB 21 east terminus |
| Buxtehude | 53.4747 | 9.6931 | Metronom / S3 |

(AKN Eisenbahn treated as regional-rail per operating pattern; AKN stops arrive via HVV GTFS but classify under this tuple.)

### 3.4 Hamburg Airport (HAM)

| Field | Value |
|---|---|
| Name | Hamburg Airport Helmut Schmidt |
| IATA | HAM |
| ICAO | EDDH |
| Lat / Lon | 53.6304 / 9.98823 |

### 3.5 Geofabrik Hamburg OSM extract

| Aspect | Value |
|---|---|
| PBF URL | `https://download.geofabrik.de/europe/germany/hamburg-latest.osm.pbf` — verified |
| File size | ~51 MB (2026-09-19 snapshot) — 68 % of Berlin's ~75 MB |
| Refresh | Daily ~21:00 CET (Geofabrik's own cadence; AddrLens keeps weekly Sunday 03:00 CET timer for parity with Berlin) |
| Licence | ODbL 1.0, © OpenStreetMap contributors |
| Address density estimate | ~250-320k `addr:housenumber` entries projected (Berlin: ~414k) |
| Amenity coverage | Community-tagged density spot-check: intl_food GREEN, coworking AMBER (OSM undercounts everywhere), Packstationen GREEN — same tile behaviour as Berlin |
| Newcomer tag mapping | Bücherhallen Hamburg = `amenity=library` + `operator=Bücherhallen Hamburg`; VHS = `amenity=school`/`college` + name-regex "Volkshochschule" or "VHS"; ferry piers = `amenity=ferry_terminal` OR `public_transport=stop_position + ferry=yes` (dedupe by proximity); intl schools = `isced:level=*` + name-regex "International School" (fewer + more concentrated west of Alster than Berlin — reframe tile as "nearest + commute" rather than count-in-radius) |

### 3.6 Wochenmarkt + Weihnachtsmarkt

- **Wochenmarkt structured feed: MISSING.** Only per-Bezirk HTML pages on hamburg.de (~40 markets across 5 pages). Options: (a) HTML-scrape once at pipeline build, geocode via Nominatim, store static JSON seed (mirrors Berlin's Weihnachtsmarkt-at-boot pattern in `weihnachtsmarkt.py` loader); (b) drop wochenmarkt tile from Hamburg Newcomer lens.
- **Weihnachtsmarkt structured feed: MISSING.** Only hamburg.de editorial listing (~16-28 markets). Options: (a) hand-curated static JSON seed refreshed each October (short season, low churn), (b) drop tile.

**Recommendation:** curated static seed for both. Small effort (< 50 markets total between the two), tile parity preserved, upstream source cited honestly.

---

## 4. Admin office directories (hand-curated — no WFS shortcut)

**Structured feed check:** No usable WFS/GeoJSON of Hamburg office point locations exists. `WFS Behördenfinder Hamburg` bundles only admin-area polygons under a use restriction ("ausschließlich für den Einsatz im Behördenfinder Hamburg zulässig"). The `Zuständigkeitsdaten der Hamburger Verwaltung` XML dump is service/process-oriented, not point data. **Full curation required** — same pattern as Berlin's `_STANDESAMTS_BY_BEZIRK` / `_FINANZAMTS` / `_ARBEITSAGENTURS` / `_LEA_OFFICE`, extended to 5 dicts (Berlin's Bürgeramt has WFS, Hamburg's Kundenzentrum does not).

All coordinates rounded to 4 decimals (~11 m). All addresses cross-checked against `hamburg.de` or `hamburg.com` official directories; coordinates via `nominatim.openstreetmap.org` (ODbL, © OSM contributors). **Curation freshness: 2026-09-20 — annual re-check comment ("ponytail") to be added to hamburg.py in the same style as berlin.py's Standesamt dict.**

### 4.1 Kundenzentrum (Hamburg's Bürgeramt-equivalent — "Hamburg Service vor Ort")

16 branches citywide. Source: `hamburg.com/residents/civil-services-guide/hamburg-service-vor-ort/opening-hours-973318`.

| name | address | lat | lon | Bezirk |
|---|---|---|---|---|
| Kundenzentrum Alstertal | Wentzelplatz 7, 22391 Hamburg | 53.6519 | 10.0918 | Wandsbek |
| Kundenzentrum Altona | Ottenser Marktplatz 10, 22765 Hamburg | 53.5478 | 9.9332 | Altona |
| Kundenzentrum Barmbek-Uhlenhorst | Poppenhusenstraße 6, 22305 Hamburg | 53.5859 | 10.0440 | Hamburg-Nord |
| Kundenzentrum Bergedorf | Weidenbaumsweg 21, 21029 Hamburg | 53.4887 | 10.2065 | Bergedorf |
| Kundenzentrum Billstedt | Öjendorfer Weg 9, 22111 Hamburg | 53.5405 | 10.1068 | Hamburg-Mitte |
| Kundenzentrum Blankenese | Sülldorfer Kirchenweg 2a, 22587 Hamburg | 53.5643 | 9.8134 | Altona |
| Kundenzentrum City (Hamburg-Mitte) | Spitalerstraße 4, 20095 Hamburg | 53.5527 | 10.0044 | Hamburg-Mitte |
| Kundenzentrum Eimsbüttel | Grindelberg 62–66, 20144 Hamburg | 53.5747 | 9.9790 | Eimsbüttel |
| Kundenzentrum Harburg | Harburger Rathausforum 3, 21073 Hamburg | 53.4591 | 9.9780 | Harburg |
| Kundenzentrum Langenhorn | Langenhorner Markt 7, 22415 Hamburg | 53.6498 | 10.0136 | Hamburg-Nord |
| Kundenzentrum Hamburg-Mitte | Caffamacherreihe 1–3, 20355 Hamburg | 53.5544 | 9.9845 | Hamburg-Mitte |
| Kundenzentrum Niendorf | Garstedter Weg 11, 22453 Hamburg | 53.6207 | 9.9536 | Eimsbüttel |
| Kundenzentrum Hamburg-Nord | Lenhartzstraße 28, 20249 Hamburg | 53.5894 | 9.9834 | Hamburg-Nord |
| Kundenzentrum Rahlstedt | Rahlstedter Straße 151, 22143 Hamburg | 53.6018 | 10.1569 | Wandsbek |
| Kundenzentrum Süderelbe | Neugrabener Markt 5, 21149 Hamburg | 53.4693 | 9.8530 | Harburg |
| Kundenzentrum Wandsbek | Schloßstraße 60, 22041 Hamburg | 53.5717 | 10.0708 | Wandsbek |

### 4.2 Standesamt (7 branches, one per Bezirk)

| bezirk | name | address | lat | lon |
|---|---|---|---|---|
| Altona | Standesamt Altona | Platz der Republik 1, 22765 Hamburg | 53.5470 | 9.9357 |
| Eimsbüttel | Standesamt Eimsbüttel | Grindelberg 62–66, 20144 Hamburg | 53.5747 | 9.9790 |
| Hamburg-Mitte | Standesamt Hamburg-Mitte | Caffamacherreihe 1–3, 20355 Hamburg | 53.5544 | 9.9845 |
| Hamburg-Nord | Standesamt Hamburg-Nord | Kümmellstraße 5–7, 20249 Hamburg | 53.5899 | 9.9845 |
| Wandsbek | Standesamt Wandsbek | Schloßstraße 60, 22041 Hamburg | 53.5717 | 10.0708 |
| Bergedorf | Standesamt Bergedorf | Gräpelweg 8, 21029 Hamburg (Haus im Park — temporary swing-space, re-check annually) | 53.4891 | 10.2190 |
| Harburg | Standesamt Harburg | Harburger Rathausplatz 1, 21073 Hamburg | 53.4591 | 9.9795 |

### 4.3 Finanzamt (14 branches, 4 buildings — address collisions common)

| name | address | lat | lon |
|---|---|---|---|
| Finanzamt Hamburg-Altona | Holstenplatz 18, 22765 Hamburg | 53.5617 | 9.9477 |
| Finanzamt Hamburg-Am Tierpark | Hugh-Greene-Weg 6, 22529 Hamburg | 53.5948 | 9.9450 |
| Finanzamt Hamburg-Barmbek-Uhlenhorst | Hamburger Straße 23, 22083 Hamburg | 53.5750 | 10.0339 |
| Finanzamt Hamburg-Eimsbüttel | Hugh-Greene-Weg 6, 22529 Hamburg | 53.5948 | 9.9450 |
| Finanzamt Hamburg-Hansa | Steinstraße 10, 20095 Hamburg | 53.5502 | 10.0033 |
| Finanzamt Hamburg-Harburg | Harburger Ring 40, 21073 Hamburg | 53.4610 | 9.9768 |
| Finanzamt Hamburg-Mitte | Steinstraße 10, 20095 Hamburg | 53.5502 | 10.0033 |
| Finanzamt Hamburg-Nord | Borsteler Chaussee 45, 22453 Hamburg | 53.6049 | 9.9827 |
| Finanzamt Hamburg-Oberalster | Nordkanalstraße 22, 20097 Hamburg | 53.5486 | 10.0170 |
| Finanzamt Hamburg-Ost | Nordkanalstraße 22, 20097 Hamburg | 53.5486 | 10.0170 |
| Finanzamt für Großunternehmen in Hamburg | Nordkanalstraße 22, 20097 Hamburg | 53.5486 | 10.0170 |
| Finanzamt für Prüfungsdienste und Strafsachen | Hugh-Greene-Weg 6, 22529 Hamburg | 53.5948 | 9.9450 |
| Finanzamt für Steuererhebung | Steinstraße 10, 20095 Hamburg | 53.5502 | 10.0033 |
| Finanzamt für Verkehrsteuern und Grundbesitz | Gorch-Fock-Wall 11, 20355 Hamburg | 53.5572 | 9.9829 |

**Note:** Nordkanalstr. 22 hosts 3 Finanzämter; Steinstr. 10 hosts 3; Hugh-Greene-Weg 6 hosts 3. Frontend should dedupe by address and stack office names — a display concern Berlin doesn't have. Nearest-Finanzamt returns 1 entry; drilldown shows all co-located names.

### 4.4 Amt für Migration (LEA-equivalent — 1 main office)

| name | address | lat | lon |
|---|---|---|---|
| Amt für Migration (Zentrale Ausländerangelegenheiten) | Hammer Straße 30–34, 22041 Hamburg | 53.5686 | 10.0617 |

**Note:** Formerly "Ausländerbehörde", renamed post-2015. Location was Amsinckstr. 28 in the past — verify with hamburg.de call center (040 115) before shipping. Closed Fridays (Mon-Thu only). Sits in Wandsbek Bezirk despite "Zentrale" naming.

### 4.5 Agentur für Arbeit Hamburg (7 branches)

| name | address | lat | lon |
|---|---|---|---|
| Agentur für Arbeit Hamburg (Hauptagentur) | Kurt-Schumacher-Allee 16, 20097 Hamburg | 53.5515 | 10.0167 |
| Agentur für Arbeit Hamburg-Altona | Kieler Straße 39, 22769 Hamburg | 53.5658 | 9.9438 |
| Agentur für Arbeit Hamburg-Bergedorf | Johann-Meyer-Straße 55, 21031 Hamburg | 53.4906 | 10.2064 |
| Agentur für Arbeit Hamburg-Eimsbüttel | Eppendorfer Weg 24, 20259 Hamburg | 53.5695 | 9.9575 |
| Agentur für Arbeit Hamburg-Harburg | Harburger Ring 35, 21073 Hamburg | 53.4607 | 9.9789 |
| Agentur für Arbeit Hamburg-Nord | Langenhorner Chaussee 92–94, 22415 Hamburg | 53.6411 | 10.0135 |
| Agentur für Arbeit Hamburg-Wandsbek | Pappelallee 30, 22089 Hamburg | 53.5677 | 10.0604 |

### 4.6 Bezirksamt centres (7 — for Bezirk chip centroids)

| bezirk_name | Bezirksamt address | centre_lat | centre_lon |
|---|---|---|---|
| Hamburg-Mitte | Caffamacherreihe 1–3, 20355 Hamburg | 53.5544 | 9.9845 |
| Altona | Platz der Republik 1, 22765 Hamburg | 53.5470 | 9.9357 |
| Eimsbüttel | Grindelberg 62–66, 20144 Hamburg | 53.5747 | 9.9790 |
| Hamburg-Nord | Kümmellstraße 5–7, 20249 Hamburg | 53.5899 | 9.9845 |
| Wandsbek | Schloßstraße 60, 22041 Hamburg | 53.5717 | 10.0708 |
| Bergedorf | Wentorfer Straße 38, 21029 Hamburg | 53.4887 | 10.2100 (verify to 4 decimals before ship) |
| Harburg | Harburger Rathausplatz 1, 21073 Hamburg | 53.4591 | 9.9795 |

### 4.7 Bezirk integer → name lookup (needed for SozErhVo layer)

The SozErhVo WFS stores `bezirk` as an integer code. Statistikamt Nord numbering:

| bezirk_id | bezirk_name |
|---|---|
| 1 | Hamburg-Mitte |
| 2 | Altona |
| 3 | Eimsbüttel |
| 4 | Hamburg-Nord |
| 5 | Wandsbek |
| 6 | Bergedorf |
| 7 | Harburg |

Verify against a live SozErhVo GetFeature response — this ordering is the LGV/Statistikamt-Nord convention but is not published on the SozErhVo endpoint itself.

---

## 5. Cross-cutting summary

### 5.1 Missing / degraded — must drop or redesign per lens tile

| Berlin dataset | Hamburg status | Recommended mitigation |
|---|---|---|
| Per-street NO₂ air modelling | **MISSING** — only 15 stations | Drop air tile from Hamburg lenses; honest caveat |
| Fire response zones (Einsatzbereiche) | **MISSING** citywide; Eimsbüttel pilot only | Drop zone field from `fire_rescue()` return for Hamburg; keep nearest-station-only |
| Pool WFS with filterable hours/category | **MISSING** — mixed sport-facility layer | Curate Bäderland 24-entry static dict (mirrors admin office pattern) |
| Wochenmarkt structured feed | **MISSING** | Curate static JSON seed from HTML scrape |
| Weihnachtsmarkt structured feed | **MISSING** | Curate static JSON seed, annual October refresh |
| Address WFS with GeoJSON output | GML only | Route Hamburg geocoder via OGC API Features endpoint; keep OSM prefix index for /api/suggest |
| Trinkwasserbrunnen standalone | Thinner — 40 combined with WC | Adjusted thresholds + caveat; skip if Young Family lens delayed |
| Noise per-façade points | Isophone polygons per source | Rewrite `noise_at()` for Hamburg as per-source point-in-polygon rollup returning bands |
| Primary-school catchments per school | Per statistical district of residence | Skip "your school = X" query; use nearest-primary + BSB advisory copy |

### 5.2 Structural per-city field-map additions to CityConfig

New / adjusted `CityConfig` fields required for Hamburg (draft — final list emerges in the design spec):

- `wfs_srs_name: str` — default `"EPSG:4326"` for Berlin (WFS auto-projects), explicit for Hamburg (`srsName=EPSG:4326` param on every request)
- `wfs_namespace_map: dict[str, str]` per layer, or embed namespace in the layer typeName string — currently Berlin has flat `schulen:schulen` style; Hamburg needs `de.hh.up:...`, `app:...`, `dog:...`. Simplest: use full typeName as-is and don't parse (Berlin's config already does this).
- `ferry_wfs_url` + `ferry_layer` + `ferry_field_map` — new Optional connectivity mode
- `pools_curated: tuple` — Optional; when set, replaces the WFS pool loader (Hamburg only)
- `bezirk_id_to_name: dict[int, str]` — Optional; only for cities where bezirk is stored as int code (Hamburg only)
- `fire_zones_available: bool` — implicit today via Optional URL, but tile logic needs to know
- `noise_model: Literal["point", "isoline"]` — controls whether `noise_at()` returns attributes or bands
- `air_model: Literal["street", "station", "none"]` — controls whether air tile shipped at all

Everything else fits into Berlin's existing Optional fields (`Optional[str]` URLs, `dict` field maps).

### 5.3 Attribution + licence — Hamburg block

Universal `dl-de/by-2-0` for all WFS. Bulk attribution string:

> Freie und Hansestadt Hamburg — Landesbetrieb Geoinformation und Vermessung (LGV), datenverantwortlich BUKEA / BSB / BSW / BVM / BWGV / BAGFI / BIS je Datensatz. Lizenz: Datenlizenz Deutschland — Namensnennung 2.0.

Per-authority credits needed on the per-tile provenance line, mirroring Berlin's per-dataset attribution dict. Hamburg-specific extras:

- HVV GTFS: "Hamburger Verkehrsverbund GmbH (dl-de/by-2-0)"
- Geofabrik: "© OpenStreetMap contributors (ODbL) via Geofabrik Hamburg weekly extract"
- Sozialmonitoring: "Freie und Hansestadt Hamburg / BSW — Sozialmonitoring Integrierte Stadtteilentwicklung (dl-de/by-2-0)"
- Bäderland (curated pool dict): "Curated from baederland.de (public reference)"
- Kundenzentrum / Standesamt / Finanzamt / LEA / Arbeitsagentur: "Curated from hamburg.de directories (public reference)"

---

## 6. Open questions for Phase 1 (architectural spec)

These decisions belong in the spec, not the landscape doc, but flagging so they are not lost:

1. **Address geocoder path** — OGC API Features vs GML parser in `app.core.wfs.wfs()`. Recommendation above is OAF; confirm before spec is written.
2. **Noise tile redesign** — do Hamburg noise tiles return bands ("55-59 dB LDEN") or bin bands to a tier the way Berlin bins numeric dB? Affects tile copy + `constants.js` TILE_DEFS.
3. **Pools static curation** — 24 Bäderland entries manually seeded, or scrape baederland.de at build time?
4. **Wochenmarkt + Weihnachtsmarkt** — curate once vs scrape periodically? Recommendation: curate once for launch; revisit if Hamburg publishes a real feed.
5. **`gesamtindex` vs `statusindex`** — Sozialmonitoring publishes both. Which drives the tile? `statusindex` is the 4-level "hoch/mittel/niedrig/sehr niedrig" which maps cleanly to a badge; `gesamtindex` combines status + dynamik into an overall "aufmerksam / kein Handlungsbedarf" flag. Recommend `statusindex` for the primary tile + `dynamikindex` as a companion trend chip.
6. **International-school tile framing** — Hamburg has ~6 international schools mostly west of the Alster. Newcomer lens tile should switch from "count-in-radius" to "nearest school + commute time" — needs a new tile logic branch.
7. **Bezirk integer lookup as CityConfig field vs constant** — 7-entry dict; small enough to inline into `hamburg.py`. Confirmed as inline.

---

## 7. Verification checklist for Phase 1

Before writing the design spec, run these live checks (5-10 min each):

- [ ] `HH_WFS_Strassenverkehr` — verify the correct endpoint URL (404'd in this research; check archived capabilities or search MetaVer for the current URL)
- [ ] `Städtebauliche Erhaltungsverordnungen` — find the WFS endpoint (only WMS surfaced in research)
- [ ] `HaLm` air-stations WFS — confirm URL
- [ ] Amt für Migration location — call 040 115 or check hamburg.de "Frag den Michel" widget to confirm Hammer Str. 30-34 is current (not Amsinckstr. 28)
- [ ] Kundenzentrum Wilhelmsburg — hamburg.com list excludes it; verify against hamburg.de whether it's still open (mobile-team only?)
- [ ] Bezirk integer → name mapping — GetFeature one SozErhVo entry, confirm the code matches expected Bezirk name
- [ ] Bergedorf Bezirksamt coordinates — re-geocode Wentorfer Str. 38
- [ ] HVV GTFS licence line — pull the current monthly file's metadata block, quote verbatim for attribution

---

## 8. Sources (all cited during discovery — verified 2026-09-20)

### WFS + OGC API Features
- HH_WFS_DOG (address gazetteer): https://geodienste.hamburg.de/HH_WFS_DOG?REQUEST=GetCapabilities&SERVICE=WFS
- HH_WFS_Schulen: https://geodienste.hamburg.de/HH_WFS_Schulen?SERVICE=WFS&REQUEST=GetCapabilities
- HH_WFS_Regionaler_Bildungsatlas_Einzugsgebiete_Schulwahl: https://geodienste.hamburg.de/HH_WFS_Regionaler_Bildungsatlas_Einzugsgebiete_Schulwahl?SERVICE=WFS&REQUEST=GetCapabilities
- HH_WFS_KitaEinrichtung: https://geodienste.hamburg.de/HH_WFS_KitaEinrichtung?SERVICE=WFS&REQUEST=GetCapabilities
- HH_WFS_Krankenhaeuser: https://geodienste.hamburg.de/HH_WFS_Krankenhaeuser?SERVICE=WFS&REQUEST=GetCapabilities
- wfs_wc_mit_trinkbrunnen: https://metaver.de/trefferanzeige?docuuid=07439748-e62d-43ce-b68a-e93fff03683b
- HH_WFS_Gruenplan: https://geodienste.hamburg.de/HH_WFS_Gruenplan?REQUEST=GetCapabilities&SERVICE=WFS
- wfs_spielplaetze: https://geodienste.hamburg.de/wfs_spielplaetze?SERVICE=WFS&REQUEST=GetCapabilities
- HH_WFS_Strassenverkehr (archived): https://archiv.transparenz.hamburg.de/hmbtgarchive/HMDK/hh_wfs_strassenverkehr_162854_snap_2.XML
- Strategische Lärmkarten §47c metadata: https://metaver.de/trefferanzeige?docuuid=030A8F47-EBEF-4669-94FC-0299BB7D5C88
- HaLm (Hamburger Luftmessnetz): https://luft.hamburg.de/allgemeine-informationen/wir-ueber-uns-775726
- wfs_stadtklimaanalyse_hamburg_2023: https://geodienste.hamburg.de/wfs_stadtklimaanalyse_hamburg_2023?Service=WFS&Request=GetCapabilities
- HH_WFS_Strassenbaumkataster: https://geodienste.hamburg.de/HH_WFS_Strassenbaumkataster?SERVICE=WFS&REQUEST=GetCapabilities
- HH_WFS_Ruhige_Gebiete: https://geodienste.hamburg.de/HH_WFS_Ruhige_Gebiete?SERVICE=WFS&REQUEST=GetCapabilities
- HH_WFS_SozErhVO: https://geodienste.hamburg.de/HH_WFS_SozErhVO?SERVICE=WFS&REQUEST=GetCapabilities
- HH_WMS_Erhaltungsverordnung: https://geodienste.hamburg.de/HH_WMS_Erhaltungsverordnung?SERVICE=WMS&REQUEST=GetCapabilities
- HH_WFS_Verwaltungsgrenzen: https://geodienste.hamburg.de/HH_WFS_Verwaltungsgrenzen?SERVICE=WFS&REQUEST=GetCapabilities
- HH_WFS_feuerwehrstandorte: https://geodienste.hamburg.de/HH_WFS_feuerwehrstandorte?SERVICE=WFS&REQUEST=GetCapabilities
- HH_WFS_Zulaessige_Hoechstgeschwindigkeiten: https://geodienste.hamburg.de/HH_WFS_Zulaessige_Hoechstgeschwindigkeiten?SERVICE=WFS&REQUEST=GetCapabilities
- HH_WFS_Strassen_und_Wegenetz: https://geodienste.hamburg.de/HH_WFS_Strassen_und_Wegenetz?REQUEST=GetCapabilities&SERVICE=WFS
- HH_WFS_Sportstaetten: https://geodienste.hamburg.de/HH_WFS_Sportstaetten?SERVICE=WFS&REQUEST=GetCapabilities
- HH_WFS_Badegewaesser: https://geodienste.hamburg.de/HH_WFS_Badegewaesser?SERVICE=WFS&REQUEST=GetCapabilities
- HH_WFS_bewohnerparkgebiete: https://geodienste.hamburg.de/HH_WFS_bewohnerparkgebiete?SERVICE=WFS&REQUEST=GetCapabilities
- wfs_sozialmonitoring: https://geodienste.hamburg.de/wfs_sozialmonitoring?SERVICE=WFS&REQUEST=GetCapabilities
- Sozialmonitoring metadata: https://metaver.de/trefferanzeige?docuuid=92BCB98D-47E1-4FC6-858E-7DF6DE9C1FD8

### HVV + Geofabrik
- HVV GTFS 2025-05 to 2025-12: https://suche.transparenz.hamburg.de/dataset/hvv-fahrplandaten-gtfs-mai-2025-bis-dezember-2025
- HVV developer info: https://www.hvv.de/de/fahrplaene/abruf-fahrplaninfos/datenabruf
- Geofabrik Hamburg download page: https://download.geofabrik.de/europe/germany/hamburg.html
- Geofabrik technical / refresh cadence: https://download.geofabrik.de/technical.html
- HADAG: https://en.wikipedia.org/wiki/HADAG · http://hadag.de/en/harbour-ferries.html

### Admin directories
- Hamburg Service vor Ort branches: https://www.hamburg.com/residents/civil-services-guide/hamburg-service-vor-ort/opening-hours-973318
- Standesämter Hamburg: https://www.hamburgerhochzeit.de/standesaemter-hamburg/ · https://www.hamburg.de/politik-und-verwaltung/bezirke/bezirksthemen/standesamt
- Finanzämter (Wikipedia): https://de.wikipedia.org/wiki/Liste_der_Finanz%C3%A4mter_in_Hamburg · https://finanzaemter.org/finanzaemter-in-hamburg/
- Amt für Migration: https://www.hamburg.de/politik-und-verwaltung/behoerden/behoerde-fuer-inneres-und-sport/aemter/amt-fuer-migration · https://auslaenderbehoerde.org/en/immigration-authority-hamburg/
- Agentur für Arbeit Hamburg: https://www.arbeitsagentur.de/vor-ort/hamburg
- WFS Behördenfinder Hamburg (bounded-use polygon service): https://metaver.de/trefferanzeige?docuuid=AE816592-05BE-474A-9635-4B86923C102B
- Zentraler AdressService Hamburg (OAF): https://api.hamburg.de/datasets/v1
- Zuständigkeitsdaten der Hamburger Verwaltung (XML dump): https://transparenz.hamburg.de/dataset/zustaendigkeitsdaten-der-hamburger-verwaltung11
- ALKIS Verwaltungsgrenzen: https://metaver.de/trefferanzeige?docuuid=E8C0EE63-1C9C-4408-A925-E20A13769F6F
- Statistische Gebiete: https://metaver.de/trefferanzeige?docuuid=DB93B23B-D3F1-4460-8C62-DD1961893767

### Markets
- Wochenmärkte Hamburg (HTML only): https://www.hamburg.de/wochenmarkt-hamburg/
- Weihnachtsmarkt editorial (HTML only): https://www.hamburg.de/tourismus/weihnachten-hamburg/weihnachtsmarkt-hamburg

Geocoding: `nominatim.openstreetmap.org/search?format=json&q=<address>&limit=1` (ODbL, © OSM contributors).
