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
     - Left stack: Address · Assigned Grundschule (one per school in catchment) · Kitas metric · Nearest international. Every card is clickable — clicking plots that card's location(s) on the map with the card's icon in the card's colour. Only one card active at a time.
     - Right column: Map with catchment polygon overlay, address marker (pink, always visible), 800m ring, plus category-icon pins for the currently active card (school / kitas / intl). Map hint overlay top-left mirrors the Amenities pattern.
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
  "schools":   [ { "name", "bsn", "street", "hnr", "plz", "lat", "lon",
                   "phone", "website", "sesb_strand", "school_year" } ],
  "intl_grundschule": { "name", "bsn", "distance_m", "lat", "lon", "website" },
  "kitas":     { "count", "items": [ { "name", "lat", "lon" } ], "error"? },
  "provenance": { "catchment", "schools", "addresses", "kitas_osm" }
}
```

Every entity in the Education response carries `lat`/`lon` — the frontend needs those to plot pins when a card is clicked.

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

Both tabs share the same tile source, the same address/walk-ring styling, and the same "click a card to plot" interaction. Overlays differ per tab.

- **Tiles:** CARTO Voyager (`https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png`, subdomains `abcd`). Attribution: `© OpenStreetMap · © CARTO`.
- **Default overlays (both tabs, always visible):** address pin (pink `#EC4899`) · 800m walk ring (`#22C55E`, dashed).
- **Education-only always-on:** catchment polygon (`#4F46E5`, weight 2.5, fillOpacity .10) — this is the ship-criterion answer, not gated on card click.

**Click-triggered pins.** Each card, when active, plots its category as icon-pins built by the shared `iconPin(svg, color)` helper (30px circle in category colour, 2.5px white border, category SVG stroked in white inside). Only one category active per tab at a time. On selection, `fitBounds` zooms to include all pins + address, `.pad(0.15)` cushion. Second click on the same card clears the pins and resets the view (fitBounds on the catchment for Education, setView on the address for Amenities).

**Hint overlay (`.map-hint`).** Top-left of every map (position:absolute inside `.map-cell`). Idle text: `"Click a card to plot its location"`. Active text: category label (+ count for multi-point categories like Kitas or Amenities). Shared class between both tabs — do not fork it.

**Legend.** Removed — the hint + card highlighting cover the same job. A category legend would duplicate the cards it points to.

- **After every map draw:** `requestAnimationFrame(() => mapRef.invalidateSize())`.
- **After every card select / deselect (both tabs):** `requestAnimationFrame(() => mapRef.invalidateSize())`. Even the Education map benefits — no expand/collapse happens there today, but keeping the invalidateSize inside `selectEduCategory` costs nothing and future-proofs the pattern.
- **After every Amenities card expand/collapse:** `requestAnimationFrame(() => mapAmenRef.invalidateSize())` — the stack height just changed, Leaflet won't re-render tiles until told.
- **After tab switch:** `requestAnimationFrame(() => activeTabMap.invalidateSize())` — hidden Leaflet containers report zero dimensions.

---

## Micro-interactions per element (page-specific)

Hero + Education:
- Address chip click → fills input and submits form.
- Search icon animates on input focus (slide-right + scale).
- Look-up button tracks cursor position and shows a radial highlight (`--x/--y` CSS vars updated on mousemove).
- SESB badge (Joan-Miró, Nelson-Mandela, JFK, Judith-Kerr etc.) has a ping ring around it — visual cue that this is the single attribute expat parents scan for most.
- Kita count uses `countUp(el, to, 900ms)` with ease-out cubic — feels like a slot machine settling.
- Education card click → toggles `.active`, plots that card's location(s) as icon-pins on the map (school card → single indigo school pin; kitas card → all slate kita pins; intl card → single amber globe pin; address card → re-focus the map at zoom 16 on the address, no new pin). Only one card active at a time.

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
- Do not use plain coloured dots as map pins in either tab — pins must carry the category's icon so the map and card are visually linked.
- Do not put "from OpenStreetMap" in the card caption — attribution lives in `.prov` and the page footer; the caption should read "within ~800 m" and nothing more.
- Do not use `justify-content: space-between` for amenity list rows — distances shift horizontally when tooltips are absent. Use the 3-column grid.
- Do not expand more than one Amenities card at a time — expand state and map selection are one variable; multi-expand would need a full rethink of the map layer strategy.
- Do not plot kita or intl markers by default on the Education map — they appear only when the corresponding card is clicked. The always-on Education overlay is address + walk ring + catchment polygon and nothing else.
- Do not fork `.map-hint` per tab. It's a shared class; both tabs mount their hint into `#eduHint` / `#amenHint` but style is the same rule.
