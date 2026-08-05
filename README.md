# Berlin Address Lens

Turn a Berlin address into what it actually means for a family: **assigned
Grundschule**, SESB bilingual strand, kitas within a stroller walk, nearest
international school, façade-level street noise, and a stroller-access score
for the flat itself. Compare up to five addresses side by side.

Open data only. No listing scraping. English first.

Full concept, roadmap and legal frame: [`berlin-family-address-intelligence-product-doc.md`](berlin-family-address-intelligence-product-doc.md).
Engineering conventions for future ships live in **§14** of that doc — read it
before adding features.

---

## Requirements

- Python 3.9+
- `shapely`: `pip3 install --user shapely`

That's it. No frameworks, no build step, no bundler.

---

## Run

The latest working build is in `phase2/`:

```
cd phase2
python3 server.py              # http://localhost:8000
PORT=8001 python3 server.py    # or a custom port
```

Open the URL. Type a Berlin address as `Street Nr, PLZ` (e.g. `Kastanienallee
12, 10435`) or click one of the sample chips.

Phase 1 (education-only MVP) still runs the same way from `phase1/`.

---

## Test

```
python3 server.py test
```

Loads live catchments, schools and kitas, runs assertions covering the happy
path, rule-based tier transitions (noise, stroller), and BOD/OSM merge dedupe.
Network-dependent assertions skip cleanly if a WFS is unreachable.

---

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | HTML app |
| GET | `/health` | Liveness (`{ok:true, polygons:N}`) |
| GET | `/api/lookup?address=…` | Catchment school, SESB, kitas, nearest international |
| GET | `/api/amenities?lat=&lon=` | Playgrounds, parks, pharmacies, supermarkets, GPs, hospitals, transit |
| GET | `/api/noise?lat=&lon=` | Façade L_DEN + L_Night from the 2022 strategic noise map |

All JSON responses carry a `provenance` field. Errors return `{error: "..."}`
with a plain-English message and appropriate HTTP status.

---

## Directory layout

| Dir | What it contains |
|---|---|
| `phase0/` | Validation prototypes — catchment-WFS check, agency outreach kit |
| `phase1/` | MVP: single address → Pillar 1 (education) |
| `phase2/` | Comparison board, noise, stroller score, BOD-first sourcing |
| `design-system/` | Dashboard mockup and design notes |
| `berlin-family-address-intelligence-product-doc.md` | Concept · features · data · legal · roadmap · **engineering conventions (§14)** |

Older phases are preserved as-shipped. New work goes in a new `phaseN/`
directory (see §14.1 of the product doc).

---

## Data sources

- **Berlin Geoportal** (`dl-de/by-2.0`, some `dl-de/zero-2.0`) — schools,
  Einschulbereiche, addresses, kitas, green spaces, playgrounds, 2022
  strategic noise map.
- **OpenStreetMap** (`ODbL`) — pharmacies, supermarkets, GPs, transit stops,
  playground/park supplements where the city dataset is known to undercount.
- **No listings.** The product is a decision layer over a location, never
  a portal (§7 of the doc).

Attribution appears in the footer and per-panel; full attribution strings in
the doc's Appendix.

---

## Contributing

Read **§14 Engineering conventions** in the product doc first. Short version:

- Stdlib + shapely only. No frameworks, no build step.
- One `server.py` + one `index.html` per phase. Copy the previous phase,
  extend additively.
- BOD first, OSM as fallback / supplement — per-item source tag on every
  feature.
- Provenance on every panel and every API response.
- Selfcheck in `server.py` covers rule-based logic + integration merges.
- Live-browser QA (initial state / error state / happy path) before shipping
  any UI change.
- Mark deliberate shortcuts with `ponytail:` comments naming the ceiling.
