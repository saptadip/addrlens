# Clickable Lens Tiles — Design (Spec D)

**Date:** 2026-08-10
**Status:** Approved for implementation planning
**Predecessors:** Spec A (Young Family lens), Spec B (Bureaucracy lens) — both shipped. This spec extends both.
**Sequel:** Spec C (LLM re-narration through lenses) — future.

## Context

Spec A and Spec B shipped a Life Mode with two lenses (Young Family, Bureaucracy) rendering as opinionated tile grids. Tiles today are informative summaries — tier + rule + numeric on the face — but **not interactive**: users cannot click a tile to see which specific kitas / pediatricians / offices the tier is based on, nor pin them on the map. The raw-mode Amenities tab already establishes the interactive card pattern (2-col tiles + Leaflet map, click-tile → modal-overlay + pin update, per-item ⓘ popovers with detail rows).

Spec D brings the same interaction language to the Life Mode lenses:

- Every tile becomes clickable.
- Clicking a tile opens a modal (an absolute overlay over the tile grid, mirroring `.amen-modal`) with the underlying feature list.
- Each feature row has a small ⓘ info button (reusing `<details class="info-tip">` + `.info-body.details-block`) that pops out granular per-feature details.
- A dedicated Leaflet map (`#lens-map`) sits beside the tile grid; feature pins appear when a geo tile opens; map pin ↔ list row sync both ways.
- Aggregate tiles (noise / heat / air) get an info-only modal with a short explanation of the metric, no map interaction.

Response schema gains a `features` array per tile plus optional `metadata` (currently only refuge's tree stats use it). Spec A + Spec B response contracts are extended in a strictly additive way — no field renames, no shape breaks.

Primary audience unchanged from Spec A/B: English-speaking expats new to Germany (`microservice-refactor-plan.md` §0).

## Scope

**In scope:**

- Every lens tile becomes a `<button class="lens-tile">` with keyboard + mouse activation.
- 2-col Life Mode layout: lens tiles column (~57%) + Leaflet map column (~43%), mobile-collapsed vertically.
- `.lens-modal` — absolute overlay covering the tiles column on tile click. Backdrop blur, `✕` close, Escape close.
- Per-feature `<details class="info-tip">` info popovers — reuse existing `.info-tip` + `.info-body.details-block` markup + CSS.
- Numbered map pins (1, 2, 3…) colored by tier; two-way sync — click row → pan to pin; click pin → highlight row.
- New helper functions in `app/core/scorer.py`: `_prune`, `_int_or_none`, `_valid_latlon`, `_shape_kita`, `_shape_playground`, `_shape_paediatric_gp`, `_shape_office`, `_shape_refuge_quiet`.
- Both `young_family_lens` and `bureaucracy_lens` composers extended to emit `features` per tile + `metadata` on refuge.
- Pure + live selfcheck coverage for the new shape helpers + feature arrays.
- Amendments (See-also pointers only) at the top of Spec A and Spec B design docs.

**Out of scope (deliberate):**

- Making compare-view dots clickable — too dense with map.
- LLM narration inside the modal — Spec C (future).
- Search or filter within the feature list — no cap on features, no filter.
- Sanitizing user-visible free text beyond `escapeHtml` — passthrough of raw OSM/BOD strings.
- Deep-link URLs like `#lens-tile=kita` — future.
- Per-user bookmarking of features — future.
- New attribution keys — sources are unchanged from Spec A/B; the modal surfaces existing sources at higher resolution.
- Response feature-count cap — Berlin v1 payloads are under mobile-3G tolerance without a cap.

## Locked decisions

- **2-col layout inline** mirroring raw-mode Amenities (`.grid` + `.map-cell` pattern). Ratio ~1.15 : 0.85. Vertical stack under 900 px.
- **All tiles clickable** — geo tiles pin features + open detail modal; aggregate tiles (noise / heat / air) open info-only modal with an explanation string.
- **Tile size:** 200 px medium rectangles, grid `repeat(auto-fit, minmax(200px, 1fr))`, gap 12 px, min-height 100 px. Caveat leaves the tile face; moves to the modal.
- **Tile is `<button>`** — native keyboard + mouse activation; no ARIA fixup needed.
- **Feature shape:** required `{name, lat, lon, distance_m}`. Optional common: `{address?, phone?, website?, hours?, walk_min?}`. Tile-specific extras (kita capacity/operator_type/approach; playground area_m2/renovated_year; pediatrician wheelchair; refuge size_ha/kind).
- **All features within the tier fn's input radius**, sorted asc by `distance_m`, no cap. Nearest-single tiles (finanzamt, standesamt, lea) always emit exactly 1 feature.
- **Feature drop rule:** at `_shape_*` time, drop features missing any of `{name, lat, lon, distance_m}`. Better empty list than broken row.
- **Info popover** — native `<details class="info-tip">` disclosure with `<div class="info-body details-block">` — reuse existing CSS (`app.css:409-421`). Portal + `dropOrphanTooltips` mechanism reused. Feature rows with no optional fields omit the ⓘ button.
- **Numbered pins** — feature index +1 rendered inside the pin (`lensNumberedPin(idx, color)` helper). Row shows the matching number in a `.feature-marker` circle.
- **Two-way sync** — click a row (outside `.info-tip`) → map pans + zooms to that pin. Click a pin → briefly highlights the matching row.
- **Pin colors** track tile tier: green `--success`, amber `--amber`, red `--danger`, unknown gray `#9CA3AF`. Address pin stays pink (`#EC4899`).
- **Dedicated `#lens-map`** — separate Leaflet instance from raw-mode `#map`; own address marker + pin lifecycle; destroyed via `lensMap.remove()` on Life Mode OFF or address change.
- **Aggregate-tile explanations** hardcoded in JS (`LENS_TILE_EXPLANATIONS` const, keyed by tile.key). Not shipped in the response — static per-key, so client-side is honest.
- **Doc trail:** this spec is new. Spec A + Spec B design docs get a one-line "See also" pointer at the top. Their plans + follow-ups are left untouched (historical artifacts).

## Architecture (delta vs Spec A + Spec B)

*Where the code lives:*

- `app/core/scorer.py` — add shape helpers (`_prune`, `_int_or_none`, `_valid_latlon`, `_shape_kita`, `_shape_playground`, `_shape_paediatric_gp`, `_shape_office`, `_shape_refuge_quiet`, `_shape_refuge_trees`). Extend both composers (`young_family_lens`, `bureaucracy_lens`) to emit `features` per tile and `metadata` on refuge.
- `app/routes/lookup.py` — no changes. Response gains `tile.features` automatically through the scorer.
- `app/selfcheck.py` — extend live-selfcheck asserts for the new fields (Kastanienallee 12 kita features + Bergmannstraße 27 pediatrician features + Standesamt Pankow single feature).
- `web/index.html` — no changes. `#lens-view` continues to be lazy-created by JS.
- `web/static/app.js` — largest delta:
  - New: `renderLensModalBody(tile)`, `renderLensFeature(tileKey, feature, idx)`, `_lensFeatureDetailHtml(tileKey, feature)`, `renderLensTreesBlock(trees)`, `openLensModal(tileKey)`, `closeLensModal()`, `_updateLensMapPins(tile)`, `_highlightLensRow(idx)`, `initLensMap(addr)`, `lensNumberedPin(idx, color)`.
  - New consts: `LENS_TILE_EXPLANATIONS`, `TIER_PIN_COLORS`. Module-level state: `lensMap`, `lensAddressMarker`, `lensMapFeaturePins`.
  - Update: `renderLensSingle(addr)` — 2-col output with `.lens-body` + `.lens-tiles-col` + `.lens-map-col`. `renderLensTile(tile)` — `<button data-tile-key>`, drop caveat from face.
  - Update: `renderAllPanels` — after lens-view innerHTML set, call `initLensMap(eduData.address)`; on Life Mode OFF, `lensMap.remove()` + `dropOrphanTooltips()`.
  - Delegated handlers: `.lens-tile` click → `openLensModal`; `.lens-modal-close` click → `closeLensModal`; `.lens-feature:not(.info-tip *)` click → focus pin. Escape → `closeLensModal`.
- `web/static/app.css` — new selectors for `.lens-body`, `.lens-tiles-col`, `.lens-map-col`, `#lens-map`, `.lens-tile` (hover/focus), `.lens-modal` + sub-selectors, `.lens-feature`, `.feature-marker`, `.modal-trees`, `.modal-explanation`, media query. Reuse existing `.info-tip` / `.info-body.details-block` / `.det-row` — zero new CSS for the info popover.

*Data flow (single-address, tile click):*

```
User loads address
   │
   ▼
GET /api/lookup       (each tile now carries `features: [...]`)
   │
   ▼
Frontend renders lens-view 2-col layout:
   [ tiles-col (grid of 200 px tiles) ] [ map-col (Leaflet #lens-map) ]
   Map shows address (pink pin) + no other pins.
   │
   ▼
User clicks a tile
   │
   ▼
openLensModal(tileKey):
   - .lens-modal (absolute, inset:0, backdrop blur) shown over .lens-tiles-col
   - modal.innerHTML = renderLensModalBody(tile)
     • head: icon-badge + label + tier badge
     • rule + numeric + caveat (if any) + explanation (aggregate tiles only)
     • features list: <li class="lens-feature"> with number + name + distance + ⓘ info-tip
     • trees stats block (refuge only)
     • sources footer
   - focus moves to close button
_updateLensMapPins(tile):
   - clears prior feature pins (keeps address pin)
   - adds one numbered pin per feature via lensNumberedPin(idx, TIER_PIN_COLORS[tier])
   - fits bounds to include address + all feature pins (padding 30 px)
   - #lens-map-hint updates with tile label + feature count
   │
   ▼
User clicks a feature row (outside .info-tip)
   │
   ▼
   - lensMap.setView([feature.lat, feature.lon], max(currentZoom, 16))
   - the row briefly highlights (CSS transition)
   │
   ▼
User clicks a map pin
   │
   ▼
   - Leaflet popup opens with name + distance
   - _highlightLensRow(idx) — scroll the row into view + brief background pulse
   │
   ▼
User clicks a feature's ⓘ button
   │
   ▼
   - <details> opens; .info-body renders label/value rows
   - Tooltip portal moves the .info-body to document.body to escape modal overflow clipping (existing mechanism)
   │
   ▼
User closes the modal (✕, Escape, or clicks outside)
   │
   ▼
closeLensModal():
   - modal.hidden = true; modal.innerHTML = ''
   - dropOrphanTooltips() — sweep any open info popovers
   - lensMapFeaturePins cleared; map re-centered on address
   - focus returns to the last-clicked tile
```

*Data flow (compare view):* unchanged from Spec B. 7×N / 5×N dot matrix stays non-clickable, no map, no modal.

*Response-size cost:* +15-25 KB additional payload for dense inner-Berlin addresses (kita features ~1.8 KB, playgrounds ~1.8 KB, bureaucracy tiles ~10 KB). Baseline `/api/lookup` was ~32 KB post-Spec-B → ~50-55 KB post-this. Within mobile-3G tolerance (~4 s at 250 kbps). No cap for v1; `ponytail:` follow-up if outer-city payloads become large.

## Features schema

*Overall tile shape (per lens response):*

```json
{
  "key": "kita",
  "label": "Kita reachability",
  "icon": "kita",
  "tier": "green",
  "rule": "≥3 kitas within 400m",
  "numeric": "5 within 400m · nearest 180m",
  "caveat": "",
  "sources": ["Geoportal Berlin / Kindertagesstätten"],

  "features": [ /* 0..N feature dicts, sorted asc by distance_m */ ],
  "metadata": { /* optional; only refuge uses this in v1 */ }
}
```

`features` always present (empty for aggregate tiles). `metadata` present only when tile-scoped extras are non-feature-shaped (currently only refuge tree stats).

*Feature shape per tile family:*

| Tile | Required | Optional common | Tile-specific extras |
|---|---|---|---|
| `kita`         | name, lat, lon, distance_m | — | `capacity` (int), `operator_type` (str), `approach` (str) |
| `playground`   | name, lat, lon, distance_m | — | `area_m2` (int), `renovated_year` (int) |
| `pediatrician` | name, lat, lon, distance_m | `address`, `phone`, `website`, `hours` | `wheelchair` (bool, surfaced only if `true`) |
| `noise`, `heat`, `air` | — (features `[]`) | — | — |
| `refuge`       | (0 or 1 feature) name, lat, lon, distance_m | — | `size_ha` (float), `kind` (str). Plus tile-level `metadata.trees` |
| `buergeramt`   | name, lat, lon, distance_m | `address`, `website`, `walk_min` | — |
| `finanzamt`, `standesamt`, `lea`, `arbeitsagentur` | name, lat, lon, distance_m | `address`, `walk_min` | — |

*Example — kita feature:*

```json
{
  "name": "Kita Sonnenschein",
  "lat": 52.5388, "lon": 13.3948,
  "distance_m": 180,
  "capacity": 65,
  "operator_type": "freie Träger",
  "approach": "Situationsansatz"
}
```

*Example — pediatrician feature (from OSM, Bergmannstraße 27):*

```json
{
  "name": "Praxis für Kinderheilkunde Dr. Berns",
  "address": "Bergmannstraße 5, 10961 Berlin",
  "lat": 52.4893, "lon": 13.3889,
  "distance_m": 430,
  "phone": "+49 30 693 80 05",
  "website": "https://kinderarztpraxis-berns.de",
  "hours": "Mo-Fr 09:00-12:00; Mo,Tu,Th 15:00-18:00",
  "wheelchair": true
}
```

*Example — bureaucracy feature:*

```json
{
  "name": "Bürgeramt Prenzlauer Berg",
  "address": "Berliner Allee 252, 13088 Berlin",
  "website": "https://service.berlin.de/dienstleistung/121151/",
  "lat": 52.5290, "lon": 13.4530,
  "distance_m": 500,
  "walk_min": 8
}
```

*Example — refuge tile (with quiet zone + tree stats metadata):*

```json
{
  "key": "refuge",
  "tier": "green",
  "rule": "quiet ≤ 400m OR crown ≥ 25%",
  "numeric": "Volkspark Prenzlauer Berg at 350m · 27% crown",
  "features": [
    {
      "name": "Volkspark Prenzlauer Berg",
      "lat": 52.5340, "lon": 13.4340,
      "distance_m": 350,
      "size_ha": 29,
      "kind": "Erholungsgebiet"
    }
  ],
  "metadata": {
    "trees": {
      "count": 42, "avg_age_yr": 35, "tallest_m": 22, "crown_coverage_pct": 27,
      "top_species": [{"name": "Silberlinde", "n": 12}, {"name": "Winterlinde", "n": 8}]
    }
  }
}
```

*New helpers in `app/core/scorer.py`:*

```python
def _prune(d: dict) -> dict:
    """Drop keys whose value is None or empty string. Keeps 0, False, [], {}."""
    return {k: v for k, v in d.items() if v not in (None, "")}

def _int_or_none(x) -> Optional[int]:
    """Coerce BOD raw field (int-in-string) to int; None if unparseable."""
    try:    return int(x) if x not in (None, "") else None
    except (ValueError, TypeError): return None

def _valid_latlon(d: dict) -> bool:
    lat, lon = d.get("lat"), d.get("lon")
    return isinstance(lat, (int, float)) and isinstance(lon, (int, float)) \
       and -90 <= lat <= 90 and -180 <= lon <= 180

def _shape_kita(o: dict, fm: dict) -> Optional[dict]:
    p = o.get("props") or {}
    r = _prune({
        "name": (o.get("name") or "").strip(),
        "lat":  o.get("lat"), "lon": o.get("lon"),
        "distance_m": o.get("distance_m"),
        "capacity": _int_or_none(p.get(fm["capacity"])),
        "operator_type": (p.get(fm["operator_type"]) or "").strip(),
        "approach": (p.get(fm["approach"]) or "").strip(),
    })
    if not r.get("name") or not _valid_latlon(r) or r.get("distance_m") is None:
        return None
    return r

# Same pattern for _shape_playground, _shape_paediatric_gp, _shape_office,
# _shape_refuge_quiet, _shape_refuge_trees — each: _prune-build the dict,
# validate name / lat / lon / distance_m, return None on any drop signal.
# The implementation plan spells out each fn's body verbatim.
```

*Composer wiring:*

Each composer (`young_family_lens`, `bureaucracy_lens`) picks per-tile shape functions after computing the tier. Pseudocode:

```python
tile = {
    "key": key, "label": label, "icon": icon,
    "tier": res["tier"], "rule": res["rule"], "numeric": res["numeric"],
    "caveat": caveat,
    "sources": _sources_for(cfg, key, res["tier"]),
}
if key == "kita":
    tile["features"] = [f for f in
        (_shape_kita(o, cfg.kita_field_map) for o in kitas) if f]
elif key == "playground":
    tile["features"] = [f for f in
        (_shape_playground(o) for o in pg_items) if f]
elif key == "pediatrician":
    tile["features"] = [f for f in
        (_shape_paediatric_gp(o) for o in paediatric) if f]
elif key == "refuge":
    tile["features"] = _shape_refuge_quiet(quiet_zone,
                              thresholds["refuge"]["amber_quiet_m"])
    tile["metadata"] = {"trees": _shape_refuge_trees(trees)}
elif key in {"buergeramt", "arbeitsagentur"}:
    tile["features"] = [f for f in
        (_shape_office(o) for o in offices) if f]
elif key in {"finanzamt", "standesamt", "lea"}:
    # nearest-single: input is a dict, not a list
    single = _shape_office(office) if office else None
    tile["features"] = [single] if single else []
else:
    tile["features"] = []          # noise, heat, air
tiles.append(tile)
```

## Frontend

### DOM structure inside `#lens-view` (single-address view)

```
<div class="lens-picker-row">
  {picker}   {audience-hint}
</div>
<div class="lens-body">
  <div class="lens-tiles-col">
    <div class="lens-grid">
      <button class="lens-tile ..." data-tile-key="kita">...</button>
      ...
    </div>
    <div class="lens-modal" id="lens-modal" hidden></div>   ← absolute overlay
  </div>
  <div class="lens-map-col">
    <div class="map-hint" id="lens-map-hint">Click a tile to plot its locations</div>
    <div id="lens-map"></div>
  </div>
</div>
<footer class="lens-provenance">...</footer>
```

### CSS additions

```css
/* 2-col split, mirrors raw-mode .grid + .map-cell */
.lens-body        { display:flex; gap:14px; margin-top:0; }
.lens-tiles-col   { position:relative; flex:1.15 1 0; min-width:0; }
.lens-map-col     { flex:.85 1 0; min-width:0; position:relative; }
#lens-map         { height:100%; min-height:500px; border-radius:16px; overflow:hidden; }

@media (max-width: 900px) {
  .lens-body      { flex-direction:column; }
  #lens-map       { min-height:320px; }
}

/* Tiles — <button>, tighter grid + padding */
.lens-grid        { grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap:12px; }
.lens-tile        { min-height:100px; padding:12px 14px 12px 18px; cursor:pointer;
                    border:0; text-align:left; width:100%; }
.lens-tile:hover  { background: var(--result-bg-hover); }
.lens-tile:focus-visible { outline:2px solid var(--brand); outline-offset:2px; }

/* Modal — mirrors .amen-modal */
.lens-modal       { position:absolute; inset:0;
                    background: rgba(238,242,255,.98); backdrop-filter: blur(8px);
                    border-radius:16px; padding:20px 24px; overflow-y:auto; z-index:10; }
.lens-modal[hidden] { display:none; }
.lens-modal-close { position:absolute; top:14px; right:14px; width:34px; height:34px;
                    border-radius:50%; border:none; background:rgba(255,255,255,.9);
                    color:var(--muted); cursor:pointer; font-size:16px; }
.lens-modal-close:hover { color:var(--ink); }

.lens-modal .modal-head        { display:flex; align-items:center; gap:14px; margin-bottom:12px; }
.lens-modal .modal-head h3     { margin:0; font:700 20px 'Plus Jakarta Sans', sans-serif; flex:1; }
.lens-modal .icon-badge        { width:44px; height:44px; border-radius:12px;
                                 display:flex; align-items:center; justify-content:center;
                                 background:var(--neumo-bg); }
.lens-modal .icon-badge svg    { width:22px; height:22px; }
.lens-modal .modal-rule        { font-weight:600; color:var(--ink); margin-bottom:4px; }
.lens-modal .modal-numeric     { color:var(--ink-2); margin-bottom:12px; }
.lens-modal .modal-caveat      { font-style:italic; color:var(--muted); font-size:13px;
                                 padding:8px 12px; background:var(--neumo-bg);
                                 border-radius:8px; margin-bottom:12px; }
.lens-modal .modal-explanation { color:var(--ink-2); padding:10px 14px;
                                 background:var(--neumo-bg); border-radius:10px;
                                 margin-bottom:12px; line-height:1.4; }

/* Feature list */
.modal-features-list           { list-style:none; padding:0; margin:0 0 12px 0;
                                 display:flex; flex-direction:column; gap:8px; }
.lens-feature                  { display:flex; align-items:center; gap:10px;
                                 padding:10px 12px; background:rgba(255,255,255,.6);
                                 border-radius:10px; cursor:pointer;
                                 transition: background .18s ease; }
.lens-feature:hover            { background:rgba(255,255,255,.85); }
.lens-feature.highlighted      { background:#EEF2FF; transition:background .3s ease; }
.lens-feature .feature-marker  { width:22px; height:22px; border-radius:50%;
                                 display:flex; align-items:center; justify-content:center;
                                 background:var(--neumo-bg); color:var(--ink-2);
                                 font-weight:700; font-size:11px; flex-shrink:0; }
.lens-feature .feature-name    { flex:1; font-weight:600;
                                 overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.lens-feature .feature-distance{ color:var(--muted); font-size:12px; flex-shrink:0; }

/* Trees block (refuge only) */
.modal-trees                   { padding:10px 14px; background:var(--neumo-bg);
                                 border-radius:10px; margin-bottom:12px; }
.modal-trees-summary           { font-weight:600; }
.modal-trees-species           { color:var(--ink-2); font-size:13px; margin-top:4px; }

/* Provenance footer */
.lens-modal .modal-provenance  { color:var(--muted); font-size:12px;
                                 padding-top:8px; border-top:1px solid var(--border); }

/* Map hint pill (mirrors raw-mode .map-hint) */
.lens-map-col .map-hint        { position:absolute; top:12px; left:12px; z-index:500;
                                 background: rgba(255,255,255,.94);
                                 padding:7px 12px; border-radius:8px;
                                 font-size:12px; font-weight:600; color:var(--ink-2);
                                 box-shadow: var(--sh-1); pointer-events:none; }

/* .info-tip, .info-body.details-block, .det-row, .det-label, .det-val — reused as-is */
```

### JS additions

```javascript
// ---- constants ----
const LENS_TILE_EXPLANATIONS = {
  noise: "L_DEN is EU-standard day-evening-night noise averaging. WHO recommends ≤55 dB in residential areas; above 60 dB is linked to sleep disturbance.",
  heat:  "Berlin's Umweltatlas classifies each block's bioclimate (PET at 14:00 in summer). 'Belastung' = burden; higher classes indicate more heat stress.",
  air:   "NO₂ measured µg/m³ per street segment (Umweltatlas trend scenario). WHO 2021 annual guideline is 10; Germany's legal limit is 40.",
};
const TIER_PIN_COLORS = {
  green: '#22C55E', amber: '#F59E0B', red: '#EF4444', unknown: '#9CA3AF',
};

// ---- module-level state ----
let lensMap = null;
let lensAddressMarker = null;
let lensMapFeaturePins = [];  // Leaflet markers for current tile's features
let lensLastTileKey = null;    // for focus-restore

// ---- render ----
function renderLensSingle(addr) { /* rewritten to output .lens-body 2-col */ }
function renderLensTile(tile)   { /* <button data-tile-key>, drop caveat from face */ }
function renderLensModalBody(tile) { /* full detail — head, rule, numeric, caveat, explanation, features, trees, sources */ }
function renderLensFeature(tileKey, feature, idx) { /* <li> row + ⓘ info-tip */ }
function _lensFeatureDetailHtml(tileKey, feature) { /* label/value rows */ }
function renderLensTreesBlock(trees) { /* refuge trees stats */ }

// ---- map ----
function initLensMap(addr) { /* fresh Leaflet instance at #lens-map with address marker */ }
function _updateLensMapPins(tile) { /* clear old, add numbered pins, fitBounds */ }
function lensNumberedPin(idx, color) { /* L.divIcon with number badge */ }

// ---- interaction ----
function openLensModal(tileKey) { /* set modal, call _updateLensMapPins, focus close btn */ }
function closeLensModal()       { /* hide modal, clear pins, dropOrphanTooltips, restore focus */ }
function _highlightLensRow(idx) { /* scroll .lens-feature[data-feature-idx=idx] into view + brief .highlighted */ }
```

### Interaction summary

| Trigger | Behavior |
|---|---|
| Click `.lens-tile` | `openLensModal(tileKey)` → modal shown, map pins updated (geo tiles only), close button focused |
| Click `.lens-feature` (outside `.info-tip`) | `lensMap.setView([feat.lat, feat.lon], max(currentZoom, 16))` |
| Click a feature's `<summary>` (ⓘ) | Native `<details>` toggle — popup opens; portal moves it to `document.body` |
| Click a Leaflet marker | Leaflet popup opens; `_highlightLensRow(idx)` scrolls + briefly highlights matching row |
| Click `.lens-modal-close` (✕) | `closeLensModal()` |
| Press Escape | If `<details>` is open → native browser closes it. Else `closeLensModal()`. |
| Toggle Life Mode OFF | `renderAllPanels()` clears `#lens-view.innerHTML`; `lensMap.remove()`; `dropOrphanTooltips()` |
| Change address | `renderAllPanels()` re-renders lens; `initLensMap(new_addr)` rebuilds map |

### Accessibility

- Tile buttons — native `<button>`, keyboard Tab + Enter/Space.
- Modal — `role="dialog"` + `aria-modal="true"` + `aria-labelledby="lens-modal-title"` bound to modal `<h3>`.
- Close button — `aria-label="Close details"`.
- Escape closes modal (or the innermost open `<details>` if one is open).
- Feature list — `<ul><li>` structure; screen readers walk it.
- Info popover — native `<details>` disclosure is a11y-complete out of the box.
- Numbered map pins — `divIcon` HTML has `aria-label="Feature N: {name}"` (a11y-friendly for keyboard-focused maps; low priority since Leaflet's default keyboard support is limited).
- Focus trap inside modal is v2 follow-up — Escape close + close-button are enough.

## Error handling & provenance

### Failure modes

| Source | Failure mode | Detection / handling |
|---|---|---|
| Malformed raw item (missing name/lat/lon/distance_m) | Feature dropped at `_shape_*` boundary; tile still ships with shorter `features` list |
| Optional fields carry garbage (e.g., `phone: "___"`) | Passthrough; frontend renders HTML-escaped; no validation |
| Leaflet init failure (CDN blocked, offline) | `initLensMap` catches; `lensMap = null`; `#lens-map` inner text replaced with "Map unavailable"; tile clicks still open modals |
| `metadata.trees` empty or errored | Modal's trees block conditionally rendered; skipped if all keys null / `trees.error` set |
| Response `features` missing entirely (backend regression) | Frontend defaults to `[]` via `tile.features || []` |
| Feature `website` is a `javascript:` scheme | `_lensFeatureDetailHtml` validates the URL with `/^https?:\/\//i` after `trim()` and drops the website row if the scheme is anything else. HTML-attribute encoding alone does NOT block `javascript:` clicks — the regex check is what prevents the click-to-XSS. Applied in `web/static/app.js` (commit `446a048`). |

### Feature-shape invariants (enforced in `_shape_*`)

Every emitted feature MUST have:

- `name`: non-empty string after `.strip()`
- `lat`, `lon`: finite floats in `[-90, 90]` × `[-180, 180]`
- `distance_m`: non-negative int

Missing any → `_shape_*` returns `None` → composer filters via `[f for f in (...) if f]`.

### Frontend graceful degradation

- `features: []` on a geo tile → modal renders "No matching items nearby." block (rare in practice).
- `features: []` on an aggregate tile → modal renders explanation string; no pins.
- Feature with missing lat/lon inside modal render (defensive) → skip that pin only; row still renders with `escapeHtml`-safed name.
- `sources: []` → provenance line omitted from modal (no dangling "Sources: ").
- `metadata: undefined` → trees block skipped silently.
- `caveat: ""` → caveat block skipped.
- `openLensModal(unknownKey)` → early return; no crash.
- Info popover cleanup: `closeLensModal()` calls `dropOrphanTooltips()`. `setLifeMode(false)`, lens-picker switch, address change — all call `dropOrphanTooltips()`.

### Provenance

- Unchanged. Per-tile `sources` array reused. Modal shows them as `Sources: A · B · C`, italic muted.
- No new attribution keys; this spec exposes existing sources at higher resolution.

### Response-size posture

- Worst realistic case: ~15-25 KB additional payload. Baseline ~32 KB → ~50-55 KB after Spec D. Within mobile-3G budget.
- No feature-count cap for v1. If future cities produce large lists, add a `ponytail:`-tagged cap in the composer (sort asc, truncate at N=20).

### Two-lens independence

Unchanged from Spec A/B. Each lens computed in its own `try/except` block in `lookup.py`. Features-shape errors are contained per-tile via the drop rule.

## Testing

### Pure selfcheck — `app/core/scorer.py __main__`

1. **`_prune`** — drops `None`, `""`; keeps `0`, `False`, `[]`, `{}`.
2. **`_int_or_none`** — handles str-int, int, None, unparseable.
3. **`_valid_latlon`** — Berlin range accepts; out-of-range / non-numeric / missing rejects.
4. **`_shape_kita`** — realistic BOD input returns full-shape dict; missing name / lat / lon / distance_m returns `None`.
5. **`_shape_playground`** — with area_m2 + renovated_year; without.
6. **`_shape_paediatric_gp`** — composes address from OSM tags; surfaces phone/website/hours; `wheelchair: true` only if `tags.wheelchair == "yes"`.
7. **`_shape_office`** — walk_min computed via `_walk_minutes(distance_m)` and rounded.
8. **`_shape_refuge_quiet`** — returns `[]` when distance > `amber_quiet_m`; `[feature]` when within.
9. **Composer output — `young_family_lens`** — every tile has `features` key; aggregates return `[]`; refuge carries `metadata.trees`.
10. **Composer output — `bureaucracy_lens`** — every tile has `features`; nearest-single tiles have exactly 1 feature; every feature has `walk_min`.
11. **`_lensFeatureDetailHtml` smoke tests** (JavaScript side — implicit via QA; no Python selfcheck).

Print `scorer.py: features shape + composer OK` at end of the new block.

### Cities isolation

Unchanged. No new `CityConfig` fields — this spec is purely additive to the composer + response shape.

### Live selfcheck (Berlin-guarded, extends `run_live_selfcheck`)

**Kastanienallee 12:**

```python
_by = {t["key"]: t for t in lens_yf["tiles"]}

# Kita features
_kita = _by["kita"]
assert len(_kita["features"]) >= 3
_f = _kita["features"][0]
assert _f["name"] and _f["distance_m"] > 0
assert 52.3 < _f["lat"] < 52.7 and 13.0 < _f["lon"] < 13.8
assert any("capacity" in f for f in _kita["features"]), \
    "at least one kita should carry BOD e_platz capacity"

# Aggregate tiles → features == []
assert _by["noise"]["features"] == []
assert _by["heat"]["features"]  == []
assert _by["air"]["features"]   == []

# Refuge metadata carries trees
assert _by["refuge"].get("metadata", {}).get("trees") is not None
```

**Bergmannstraße 27:**

```python
_ped = next(t for t in lens_b["tiles"] if t["key"] == "pediatrician")
_berns = next((f for f in _ped["features"] if "Berns" in f.get("name", "")), None)
assert _berns is not None
assert _berns.get("phone", "").startswith("+49")
assert _berns.get("website", "").startswith("http")
assert "Mo" in _berns.get("hours", "")
```

**Bureaucracy at Kastanienallee 12:**

```python
_by_bur = {t["key"]: t for t in lens_bur["tiles"]}
assert len(_by_bur["standesamt"]["features"]) == 1
assert "Pankow" in _by_bur["standesamt"]["features"][0]["name"]
assert len(_by_bur["lea"]["features"]) == 1
assert "LEA" in _by_bur["lea"]["features"][0]["name"]
for f in _by_bur["buergeramt"]["features"]:
    assert isinstance(f.get("walk_min"), int)
```

Print `young_family features OK` and `bureaucracy features OK` before the existing summary lines.

### Frontend live-browser QA (per §14.12) — 12-item checklist

1. **Initial state.** Load Kastanienallee 12, Life Mode ON. Verify 2-col split: tiles column (~55%) + map column (~45%). Address pink pin visible on map. Hint: "Click a tile to plot its locations".
2. **Geo tile click — kita.** Click Kita tile. Modal opens over tiles column with backdrop blur. Head shows icon + label + GREEN badge. Features list has ≥3 numbered rows. Map now shows numbered green pins + address pin; map re-fit bounds.
3. **Row → map sync.** Click feature #2's name (not the ⓘ). Map pans + zooms to that pin. Popup opens with name + distance.
4. **Pin → row sync.** Click a map pin. Leaflet popup opens. The matching row briefly highlights (background pulse) and scrolls into view if off-screen.
5. **Info popover.** Click ⓘ on a kita row. Popup shows label/value rows: Places / Operator / Approach (whichever are populated). Click ⓘ again → popup closes. Popup positioning: absolute above the row, doesn't clip the modal.
6. **Modal close via ✕.** Modal disappears. Feature pins clear. Map re-centers on address. Hint text resets.
7. **Modal close via Escape.** Open a tile, press Esc. Modal closes; pins clear. (If an ⓘ popover is open, Esc closes that first — native `<details>` behavior.)
8. **Aggregate tile — noise.** Click Noise tile. Modal opens with tier + rule + numeric + explanation paragraph + sources. Map unchanged — no new pins. Hint text unchanged.
9. **Pediatrician detail — Bergmannstraße 27.** Change address, click Pediatrician tile. Row for Dr. Berns visible. Click ⓘ. Popup shows Address / Walk-time / Phone (tel-link) / Website (Visit ↗) / Hours / Access.
10. **Refuge tile.** Click Refuge. Modal shows quiet-zone row (if contributed) + trees stats block (count + crown % + avg age + top species). Map pin at quiet zone if applicable.
11. **Bureaucracy — Standesamt tile at Kastanienallee 12.** Switch to Bureaucracy lens. Click Standesamt. Single row "Standesamt Pankow" with address + walk_min. Single pin.
12. **Lifecycle sanity.** Open tile modal → open ⓘ popover → toggle Life Mode OFF. Lens-view innerHTML clears; modal + popover + pins all disappear. Verify via DevTools that no orphaned `.info-body` elements remain in `document.body`.

Screenshots ephemeral per §14.12.

### Non-goals in tests

- Automated frontend tests — QA is manual, per §14.12.
- Full contract validation of every field on every feature at every address — representative smoke tests on kita + pediatrician + standesamt suffice.
- Response-size regression testing — no CI harness.
- Snapshot tests for modal DOM — manual visual inspection.

## Non-goals

- Compare-view dot-click behavior.
- LLM narration inside the modal (Spec C).
- Search / filter in the feature list.
- URL / phone / hours normalization (raw passthrough).
- Deep-link URLs (`#lens-tile=kita`).
- Per-user bookmarking.
- New attribution keys — sources unchanged.
- Response feature-count cap.
- Sanitizing user-visible free text beyond `escapeHtml`.
- Focus trap inside modal — v2.

## References

- `CLAUDE.md` — Berlin ADI micro-service architecture.
- `docs/superpowers/specs/2026-08-09-young-family-lens-design.md` — Spec A. **See also this Spec D** for interactive tile behavior + `features` response schema extension.
- `docs/superpowers/specs/2026-08-09-bureaucracy-lens-design.md` — Spec B. **See also this Spec D** — same extension.
- `docs/superpowers/follow-ups/2026-08-09-young-family-lens.md`, `docs/superpowers/follow-ups/2026-08-09-bureaucracy-lens.md` — deferred minors; unchanged by this spec.
- Raw-mode Amenities modal pattern — `app/static/app.js:1790-1832` (`openAmenModal`, `closeAmenModal`), `app.css:196-232` (`.amen-modal`), `app.css:409-421` (`.info-tip`, `.info-body`).
- Amenities info-popover render — `app/static/app.js:1801` (`<details class="info-tip">` markup), `app/static/app.js:696` (`amenDetailHtml`), `app/static/app.js:1547` (tooltip portal mechanism).
- Leaflet helpers — `iconPin(svg, color)` at `app/static/app.js:1983`, tile-attr constants.
- `app/core/scorer.py` — existing composers to extend.
- `app/core/index.py` — `Index.kitas_near_bod`, `Index.buergeramt_near`, `Index.arbeitsagentur_near`, `Index.finanzamt_nearest`, `Index.standesamt_for`, `Index.trees_bbox`, `Index.nearest_quiet_zone`.
