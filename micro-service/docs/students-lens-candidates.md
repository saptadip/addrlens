# Students Lens — Dataset Candidates

Berlin Open Data dataset shortlist for a new **Students** lens and upgrades to the existing **Young Family** and **Newcomer** lenses.

Source: Berlin CKAN catalog `https://datenregister.berlin.de/api/3/action/package_search` (same backend the ODIS *Open Data MCP Server* wraps — see `https://odis-berlin.de/projekte/2026-07-mcp-server/` and `https://github.com/technologiestiftung/open-data-mcps`). Cross-checked against current lens tiles in `app/cities/berlin.py` and inference templates in `inference/templates/`.

## Existing coverage baseline

- **Young Family (9 tiles):** `kita`, `playground`, `pediatrician`, `transit`, `supermarket`, `noise`, `heat`, `air`, `refuge`.
- **Newcomer (~12 tiles):** `buergeramt`, `coworking`, `english_clinic`, `gesix`, `intl_food`, `transit_newcomer`, `language_school`, `library`, `packstation`, `wochenmarkt`, `nightlife`, `ev_charging`.
- **Bureaucracy (5 tiles):** `buergeramt`, `finanzamt`, `standesamt`, `lea`, `arbeitsagentur`.

## Top 10 candidates

| # | Dataset (CKAN slug) | Format | Best fit | Rationale |
|---|---|---|---|---|
| 1 | `wohnlagen-nach-adressen-zum-berliner-mietspiegel-2024-wfs-eddbff85` | WFS | Students, Newcomer | Official Mietspiegel Wohnlage (simple / mittel / gut) per address — rent affordability signal. Address-keyed, joins directly to the geocode. |
| 2 | `standorte-offentlicher-sportanlagen-wfs-a291318f` | WFS | Students, Young Family | Public sports facilities (gyms, courts, tracks). Walkable-sports tile. |
| 3 | `schwimmbader-der-berliner-bader-betriebe-wfs-2b934eb7` | WFS | Students, Young Family | Public indoor and outdoor pools. Cheap student leisure and family swim. |
| 4 | `fahrradstrassen-wfs-3af900bb` | WFS | Students, Newcomer | Fahrradstraßen (bike-priority streets). Rideability proxy. |
| 5 | `fahrradreparaturstationen-wfs-ffeaba56` | WFS | Students | Free public bike repair stations. Small tile, strong student affinity. |
| 6 | `verkehrsmengen-dtvw-2023-wfs-9fc4ea36` | WFS | Students (all lenses) | Daily average traffic per street (DTVw). Bike safety and street calm indicator. |
| 7 | `grunanlagenbestand-berlin-einschliesslich-der-offentlichen-spielplatze-wfs-737fd0a4` | WFS | Young Family (upgrade), Students | Full parks + playground inventory. Upgrades current `playground` and `refuge` tiles with official polygons. |
| 8 | `kuhle-raume-hitzeschutz-wfs-89e7079b` | WFS | Young Family (upgrade), Newcomer, Students | Official public cooling rooms for heat waves — pairs with existing `heat` tile. |
| 9 | `kurse` (Kurse der Berliner Volkshochschulen) | JSON, XML | Newcomer, Students | Live VHS course catalogue — sits next to `language_school` and `library` tiles. |
| 10 | `ubersicht-der-coworking-spaces-in-berlin` | XLSX | Newcomer (upgrade), Students | Official Berlin coworking list — richer, provenance-tracked source than OSM. |

## Assignment by lens

### New "Students" lens
Primary new tiles from this list:
- Rent affordability — #1 `wohnlagen-2024`
- Sports facilities within walk — #2 `sportanlagen`
- Public pools within walk — #3 `schwimmbader`
- Bike-priority streets nearby — #4 `fahrradstrassen`
- Bike repair station within walk — #5 `fahrradreparaturstationen`
- Traffic calm (DTVw) on address street — #6 `verkehrsmengen-dtvw-2023`

Reused from other lenses: `transit`, `supermarket`, `library`, `nightlife`, `coworking`, `intl_food`.

Optional: VHS courses (#9) as a "learning nearby" indicator.

**Gap:** Hochschulen / universities have no WFS in the catalog (only PDF Leistungsberichte). Fall back to OSM `amenity=university`, following the same OSM-fallback pattern used elsewhere.

### Young Family upgrades
- Add #8 `kuhle-raume-hitzeschutz` → new tile "cooling refuge during heat wave", extending existing `heat` tile with actionable locations.
- Add #3 `schwimmbader` → new tile "public pool within walk".
- Supplement `refuge` / `playground` (currently OSM-first) with #7 `grunanlagenbestand` for official polygon coverage.

### Newcomer upgrades
- Add #1 `wohnlagen-2024` → new tile "Mietspiegel Wohnlage of this address"; helps arrivals judge rent fairness.
- Add #4 `fahrradstrassen` → integrate into `transit_newcomer` or a new `bike_infrastructure` tile.
- Replace OSM-based `coworking` with #10 official list for provenance-tracked accuracy.

## Caveats and follow-ups

- All 8 WFS layers above ultimately resolve to `gdi.berlin.de/services/wfs/*`. During the current maintenance outage they return the stub HTML page. The snapshot-cache resilience pattern applies to these the same way as to the layers already used by the app.
- `Schulen - [WFS]` is K-12 only; there is no Hochschulen WFS. OSM remains the only source.
- Per §14 conventions in `../berlin-family-address-intelligence-product-doc.md`, each new tile needs:
  - a matching `inference/templates/<tile>_insight.py` prompt template with pure selfcheck asserts,
  - a `CityConfig.attribution` entry with full open-data licence tag,
  - inclusion in the target lens' `TileSpec` list in `app/cities/berlin.py`,
  - `provenance` map keyed by dataset in the route response.
- Each new WFS URL should be added as a `_WFS_*` constant at the top of `app/cities/berlin.py` and threaded through `CityConfig`, following the existing pattern for `_WFS_SCHULEN`, `_WFS_KITA`, etc.
- Recommended verification workflow: probe each candidate WFS via `curl "…?service=WFS&request=GetCapabilities"` once gdi returns, confirm the exact `typeName` and coordinate system, then wire into `Index` with an appropriate loader strategy (preload for small point layers, per-request bbox for large ones).
