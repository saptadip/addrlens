# Page: Dashboard (single-address lookup)

> This file **overrides** MASTER.md when building the address-lookup dashboard.
> Reference implementation lives at `phase1/index.html`.

**Route:** `GET /` served by `phase1/server.py`
**Purpose:** Ship criterion — a family answers "which school will my child go to if I take this flat?" in <10 seconds.

---

## Page structure (top → bottom)

1. **Header row** — logo (indigo gradient tile) + brand name + tiny subtitle · right side: style pill (`Style · Micro-interactions`). This row is NOT a card, it sits on the page background.
2. **Hero card** (search) — `.hero` — warm ivory `#FEF7F0`, always. Contains: H1, one-line lede, search form (icon-in-field input + gradient button), row of three example chips.
3. **Tabs** — segmented pill control below the hero: `Education` (default) · `Amenities`. Panels below.
4. **Result grid** (in each panel) — appears only after a lookup. Flex-row on desktop.
   - **Education panel** (`#panel-edu`):
     - Left stack: Address · Assigned Grundschule (one per school in catchment) · Kitas metric · Nearest international.
     - Right column: Map with catchment polygon overlay, address marker, kita dots, intl-school marker, 800m ring.
   - **Amenities panel** (`#panel-amen`):
     - Left stack: five collapsible cards — Playgrounds · Pharmacies · Supermarkets · GPs/Doctors · Transit stops — in that order. Each collapsed by default (`count within ~800 m` + chevron); click expands to reveal the item list with per-item info tooltips.
     - Right column: Map with address marker and 800m ring, plus category-icon pins for the currently expanded category (only one at a time). Map height auto-matches the sum of card heights.
5. **Footer** — attribution line (Geoportal Berlin + OSM). Never a card.

Empty state (before any search) and Loading / Error states also render into the results slot but use neutral white surfaces (`--card`), not `--result-bg` — they aren't part of a coherent result.

---

## Colour rules (final, locked)

| Slot | Rest | Hover |
|---|---|---|
| Hero (`.hero`) | `#FEF7F0` (warm ivory) | *no change* |
| Every result card (`.cell`, `.map-cell`) | `#EEF2FF` (soft periwinkle) | `#DDE7FF` |
| Icon badge inside a result card | `#FFFFFF` + soft indigo shadow | `linear-gradient(135deg,#818CF8,#4F46E5)` + white icon |
| Empty state / Loading / Error | `#FFFFFF` (neutral, not part of results) | *no change* |

**Rule the user cares most about:** result cards must all share the same colour so they read as one result set — do not colour-code them per section.

---

## Content contract (from `/api/lookup`)

```jsonc
{
  "address":   { "street", "hnr", "plz", "lon", "lat", "raw" },
  "catchment": { "esb", "district", "polygon" /* GeoJSON MultiPolygon */ },
  "schools":   [ { "name", "bsn", "street", "hnr", "plz",
                   "phone", "website", "sesb_strand", "school_year" } ],
  "intl_grundschule": { "name", "bsn", "distance_m", "lat", "lon", "website" },
  "kitas":     { "count", "items": [ { "name", "lat", "lon" } ], "error"? },
  "provenance": { "catchment", "schools", "addresses", "kitas_osm" }
}
```

## Content contract (from `/api/amenities?lat=&lon=`)

```jsonc
{
  "amenities": {
    "playgrounds":  { "count", "items": [ { "name", "lat", "lon", "distance_m", "info" } ], "error"? },
    "pharmacies":   { ... same shape ... },
    "supermarkets": { ... },
    "gps":          { ... },
    "transit":      { ... }
  },
  "provenance": "© OpenStreetMap contributors (ODbL)"
}
```

- `info` is a single short line built server-side by `_summarize(cat, tags)` (see server.py). May be empty when OSM has no useful tags; the tooltip is then not rendered.
- Frontend fetches this eagerly right after `/api/lookup` returns, in parallel with rendering the Education panel — so switching to the Amenities tab is not gated on network I/O.

Render each field with a visible provenance line at the bottom of the card (`.prov`) — dl-de attribution requirement AND trust signal.

---

## Map details

Both tabs share the same tile source and the same address / 800m-ring styling. Overlays differ per tab.

- **Tiles:** CARTO Voyager (`https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png`, subdomains `abcd`). Attribution: `© OpenStreetMap · © CARTO`.
- **Address + walk ring (both tabs):** address pin (pink `#EC4899`) · 800m walk ring (`#22C55E`, dashed).

**Education overlays:** catchment polygon (`#4F46E5`, weight 2.5, fillOpacity .10) · intl-school marker (amber `#F59E0B`) · kita dots (slate `#94A3B8`).

**Amenities overlays:** category-icon pins for the currently expanded card only. Each pin is a 30px circle in the category colour (see MASTER.md), 2.5px white border, with the same category SVG stroked in white inside. On selection, `fitBounds` zooms to include all pins + address, with a `.pad(0.15)` cushion. Small hint overlay top-left of map: `"${label}: N shown · M total"` when a category is active, `"Click a card to plot its locations"` when idle.

- **After every map draw:** `requestAnimationFrame(() => mapRef.invalidateSize())`.
- **After every Amenities card expand/collapse:** `requestAnimationFrame(() => mapAmenRef.invalidateSize())` — the stack height just changed, Leaflet won't re-render tiles until told.
- **After tab switch:** `requestAnimationFrame(() => activeTabMap.invalidateSize())` — hidden Leaflet containers report zero dimensions.
- **Legend (Education):** always visible under the map, on the same `--result-bg` surface. Amenities uses the hint overlay + card highlighting instead — a category legend would duplicate the cards.

---

## Micro-interactions per element (page-specific)

Hero + Education:
- Address chip click → fills input and submits form.
- Search icon animates on input focus (slide-right + scale).
- Look-up button tracks cursor position and shows a radial highlight (`--x/--y` CSS vars updated on mousemove).
- SESB badge (Joan-Miró, Nelson-Mandela, JFK, Judith-Kerr etc.) has a ping ring around it — visual cue that this is the single attribute expat parents scan for most.
- Kita count uses `countUp(el, to, 900ms)` with ease-out cubic — feels like a slot machine settling.

Amenities:
- Card click anywhere (except tooltip) → toggles expand. Body shows/hides via `.active` class; chevron rotates 180° in 200ms.
- Expanding a card also selects it on the map: pins in the category colour, map fits bounds to include pins + address.
- Second click on the same card collapses AND clears pins. Only one card active at a time.
- Info tooltip: click the small ⓘ circle to open a popover (native `<details>` / `<summary>`) with a one-line OSM-derived summary. Click again on the same summary to close. Clicking the summary does NOT bubble to the card (guarded via `e.target.closest('.info-tip')` in the card click handler).

---

## Do NOT do

- Do not add a hover state to the hero card.
- Do not vary result-card backgrounds — they must all be `--result-bg`.
- Do not remove the provenance footer or the per-card provenance line — dl-de attribution + trust.
- Do not swap the map tiles to plain OSM without user request; the Voyager palette is chosen to sit calmly against the periwinkle cards.
- Do not add a dark-mode toggle without an explicit design pass — the palette isn't tuned for it.
- Do not use plain coloured dots as amenity map pins — pins must carry the category's icon so the map and card row are visually linked.
- Do not put "from OpenStreetMap" in the card caption — attribution lives in `.prov` and the page footer; the caption should read "within ~800 m" and nothing more.
- Do not use `justify-content: space-between` for amenity list rows — distances shift horizontally when tooltips are absent. Use the 3-column grid.
- Do not expand more than one Amenities card at a time — expand state and map selection are one variable; multi-expand would need a full rethink of the map layer strategy.
