# Phase 0 — WFS Validation Report

**Date:** 2026-07-31
**Question:** Does the Berlin Schulen WFS return usable Einschulbereich polygons rather than school points with a district code?
**Answer:** **YES — green light with one honest caveat.**

## Endpoints (current, verified live)

| Purpose | URL | Feature type | Geometry | CRS |
|---|---|---|---|---|
| Schools + Einschulbereiche | `https://gdi.berlin.de/services/wfs/schulen` | `schulen:schulen_esb` | **MultiPolygon** | EPSG:25833 |
| Schools (points, all types) | `https://gdi.berlin.de/services/wfs/schulen` | `schulen:schulen` | Point | EPSG:25833 |
| Address geocoder | `https://gdi.berlin.de/services/wfs/adressen_berlin` | `adressen_berlin:adressen_berlin` | Point | EPSG:25833 |

Licence: **dl-de/zero-2.0** (Schulen) / **dl-de/by-2.0** (Adressen — attribution required).

## Data shape

- **394 Einschulbereich polygons** for the current school year, refreshed by Sen(Stadt)
- **385 public Grundschulen** with `bsn` = Berliner Schulnummer
- Attributes on each polygon: `esb` (4-digit id like `0315`), `bez` (district code), `bezname` (district name)
- **Bonus:** `bsn` and `esb` share a numbering scheme — polygon `esb=0315` maps to school `bsn=03G15`. Two ways to link (spatial + string), which is a robustness win.

## Mapping quality across all 394 polygons

| Polygons | Public Grundschulen inside | Share |
|---|---|---|
| 344 | **exactly 1** — clean 1:1 catchment | **87.3%** |
| 19 | 2 | 4.8% |
| 1 | 3 | 0.3% |
| 30 | 0 — no public Grundschule inside polygon | 7.6% |

**What the caveat cases mean:**
- **2–3 schools inside one polygon (~5%)**: real ambiguity. Handle by: (a) checking the district office's binding address directory for that street, (b) exposing both options with a "verify with Bezirksschulamt" note, or (c) using the `bsn↔esb` naming heuristic to pick the primary.
- **0 schools inside polygon (~8%)**: likely commercial/industrial/parkland zones with few residential addresses, or split-district edge cases. Test with real residential addresses in these polygons before shipping; expose "outside standard catchment — contact Bezirksschulamt" if it happens on a live query.

## End-to-end smoke test — 5 real addresses

Every one resolved cleanly to a plausible, real primary school:

| Address | District | Catchment school (verified via WFS) |
|---|---|---|
| Kastanienallee 12, 10435 | Pankow | Schule am Senefelderplatz (03G15) |
| Bergmannstraße 27, 10961 | Friedrichshain-Kreuzberg | Reinhardswald-Grundschule (02G21) |
| Boxhagener Straße 15, 10245 | Friedrichshain-Kreuzberg | Modersohn-Grundschule (02G10) |
| Sonnenallee 100, 12045 | Neukölln | Rixdorfer Schule (08G01) |
| Kurfürstendamm 195, 10707 | Charlottenburg-Wilmersdorf | Joan-Miró-Grundschule (04G04) |

Independent verification for the two districts most relevant to expat families (Pankow, F-K) should be trivial — walk into each Bezirksschulamt with these 5 addresses and confirm the assignments match. If they do, the doc's "manual reconciliation of twelve district directories" fallback is unnecessary for ~90% of the city, and only needed to fix the edge cases.

## Implication for the roadmap

- **The doc's headline Pillar-1 feature is buildable directly from the WFS.** No manual reconciliation needed for the 87% clean-mapping case.
- **Phase 1 MVP is unblocked.** Ship "address → assigned public Grundschule" today; add district-directory fallback for the edge cases in Phase 2.
- **Update Phase 0 gate 1: PASSED.** Only Phase 0 gate 2 (agency willingness to pay) remains.

## Reproducing this check

```bash
pip3 install --user shapely
python3 phase0/catchment_check.py       # full report
python3 phase0/catchment_check.py test  # runnable self-check (asserts)
```

## Attribution required in the app footer

```
Geoportal Berlin / Schulen  (dl-de/zero-2.0)
Geoportal Berlin / Adressen Berlin  (dl-de/by-2.0)
```
