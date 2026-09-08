# Design System Master File

> **LOGIC:** When building a specific page, first check `docs/design-system/berlin-family-address-intelligence/pages/[page-name].md`.
> If that file exists, its rules **override** this Master file.
> If not, strictly follow the rules below.

---

**Project:** Berlin Address Lens (`addrlens`) — public brand name; the repo/design-system folder keeps the older "berlin-family-address-intelligence" slug for URL stability.
**Last update:** 2026-08-03
**Chosen style:** **Micro-interactions** (selected after comparing 9 style variants — Glassmorphism, Claymorphism, Brutalism, Neumorphism, Skeuomorphism, Soft UI Evolution, Vibrant & Block-based, Micro-interactions, Material You)
**Why this style:** restrained visual base (near-white background, subtle multi-layer shadows, clean sans-serif) so **personality lives in the interactions** — this reads professional and trustworthy, matches the "consequential-decision tool" positioning, and never gets in the way of the data.

---

## Global Rules

### Color Palette — final

```css
:root{
  /* page + surface */
  --bg:                 #FAFBFC;   /* page background */
  --card:               #FFFFFF;   /* neutral surfaces: empty state, loading, error */
  --hero-bg:            #FEF7F0;   /* warm ivory — hero/search card, NEVER shifts on hover */
  --result-bg:          #EEF2FF;   /* soft periwinkle — every result card shares this */
  --result-bg-hover:    #DDE7FF;   /* one step deeper, same hue — all result cards hover to this */

  /* ink */
  --ink:                #111827;
  --ink-2:              #374151;
  --muted:              #6B7280;

  /* brand + status */
  --brand:              #4F46E5;   /* indigo — accent bar, icon color, button gradient stop */
  --brand-2:            #818CF8;   /* indigo-400 — button gradient start */
  --success:            #22C55E;
  --danger:             #EF4444;
  --amber:              #F59E0B;

  /* line + shadow */
  --border:             #E5E7EB;
  --focus:              0 0 0 3px rgba(79,70,229,.25);
  --sh-1:               0 1px 2px rgba(17,24,39,.06);
  --sh-2:               0 4px 8px rgba(17,24,39,.06), 0 12px 24px rgba(17,24,39,.06);
}
```

### Category colours (map pins)

Applied to map pins and any category-specific accents. Each category has one
canonical colour, used everywhere it appears (pin, active-card accent, etc.).

**Education tab:**

| Category | Colour | Hex |
|---|---|---|
| Address (always-on) | pink | `#EC4899` |
| Assigned Grundschule | brand indigo | `#4F46E5` |
| Kitas | slate | `#94A3B8` |
| Nearest international | amber | `#F59E0B` |

**Amenities tab:**

| Category | Colour | Hex |
|---|---|---|
| Playgrounds | green | `#22C55E` |
| Pharmacies | red | `#EF4444` |
| Supermarkets | amber | `#F59E0B` |
| GPs / Doctors | teal | `#14B8A6` |
| Transit stops | violet | `#8B5CF6` |

**Non-negotiable palette rules:**
1. **Hero card** (contains the search input) uses `--hero-bg`. It has **no hover state**. It's the fixed anchor.
2. **All result cards** (address, school, kita, intl, map — every child of the results grid) use `--result-bg`. They must all use the **same colour** so they read as one coherent result set.
3. Result cards hover to `--result-bg-hover` — one shade deeper in the same hue family. Transition: `background .2s ease`.
4. Icon badges inside result cards sit on white (`#FFFFFF`) with `box-shadow: 0 1px 2px rgba(79,70,229,.10)` so they pop against the periwinkle bg. On card hover they flip to the brand gradient (`linear-gradient(135deg,#818CF8,#4F46E5)`) with white icon.

### Typography

- **Body + display:** Plus Jakarta Sans (400/500/600/700/800) — Google Fonts.
  Geometric-humanist hybrid: warmer than Inter, higher x-height for reading at
  15px, slightly more character in the display weights. Fallbacks:
  `system-ui, sans-serif`.
- **Display voice:** tighter tracking (`letter-spacing: -.02em`) at large sizes; no serif.
- **CSS import:**
  ```css
  @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
  ```
- **Base size:** 15px (results-dense reading); line-height 1.55.

### Spacing

Standard density. Gap 14px between cards; page gutter 22px on desktop; max page width 1240px.

### Shadow scale

- `--sh-1` — resting cards, loading/error pills.
- `--sh-2` — cards on hover, hero at rest, dropdowns.
- No `--sh-3+`; the design gets its depth from motion, not from stacked shadows.

---

## Layout Pattern — non-negotiable

**Left-stack + height-synced map**, chosen after explicit user comparison.
Applies to both the Education tab and the Amenities tab — same shape, same
`.grid` / `.stack` / `.map-cell` classes.

```css
.grid { display: flex; flex-direction: column; gap: 14px; }
.stack { display: flex; flex-direction: column; gap: 14px; min-width: 0; }
@media (min-width: 900px) {
  .grid  { flex-direction: row; align-items: stretch; }
  .stack { flex: 1.15 1 0; min-width: 0; }
  .map-cell { flex: .85 1 0; min-width: 0; }
}
```

- Left column: cards, stacked vertically.
  - Education: address → assigned-school(s) → kita metric → nearest-international.
  - Amenities: playgrounds → pharmacies → supermarkets → GPs → transit.
- Right column: single map cell. Its height must equal the exact sum of the left stack (flex `align-items: stretch` at the parent, `#map { flex: 1; height: 100%; min-height: 0 }` inside).
- **After the map is drawn**, call `requestAnimationFrame(() => mapRef.invalidateSize())` so Leaflet remeasures the stretched container.
- **After any card expand/collapse** (Amenities), call `mapRef.invalidateSize()` again in a `requestAnimationFrame` — the stack height just changed, and Leaflet won't re-render tiles until told.
- Mobile (<900px): single column, map gets explicit `min-height: 340px`.

---

## Click-to-plot card pattern (both tabs)

Every result card is clickable. Click = select the card AND plot its
associated location(s) on the map as icon-pins in the card's colour.
Click the same card again = deselect + clear pins. Only **one** card
is active at a time across the whole tab (single-selection keeps the
map readable and keeps state simple).

The `.cell.active` class is shared between tabs and drives the same
visual treatment: brighter background (`--result-bg-hover`), 2px
brand-tinted ring, indigo accent bar (`::before`) scaled in from top,
icon-badge flipped to the brand gradient. Same class also controls
"expanded" on Amenities cards (see below).

**Default map state (both tabs):** address pin (pink) + 800m walk
ring + catchment polygon (Education only). No category pins until a
card is clicked. A `.map-hint` overlay top-left of the map tells the
user what to do (`"Click a card to plot its location"` idle; category
label + count when active).

### Amenity-specific: collapsed cards

Amenities cards additionally **collapse** to a scannable overview by
default. Rationale: five categories with detail lists would flood
the viewport; collapsed cards read like a dashboard, expanded cards
read like a directory. The `.active` class drives BOTH the expanded
body AND the map selection — they are one variable, not two.

- **Collapsed** shows: icon-badge + label + chevron (▾) on the head row, then the count metric (`N within ~800 m`). Nothing else.
- **Expanded** adds the item list, "+N more within 800 m" overflow line, and per-card provenance line. Chevron rotates 180° with a 200ms transition.
- **Active/expanded state** shares `.active` class with map selection — icon badge flips to brand gradient, background steps to `--result-bg-hover`, brand accent bar (`::before`) scales in from top.
- Clicks on the tooltip trigger (`.info-tip`) must NOT bubble to the card's expand handler.

### List-row alignment

List rows use a 3-column grid so the distance column ends at the same
x-position regardless of whether an item carries an info tooltip:

```css
.amen-list li {
  display: grid;
  grid-template-columns: 1fr auto 20px;  /* name | distance | tooltip slot */
  align-items: center;
  gap: 10px;
}
```

Items without info still occupy the third column as empty — never fall back
to `justify-content: space-between`; that shifts the distance mid-row when
the tooltip is absent.

### Info tooltip

Each item that has useful OSM tag data shows a small circle "ⓘ" (info SVG,
20px hit area). Built with native `<details>` + `<summary>` — no popover
library. Panel positions absolute below-right, 240px wide, white surface
with `--sh-2`-ish drop shadow. Parent card **must** use
`overflow: visible` or the panel will clip.

Content is a single short line built server-side by `_summarize(cat, tags)`,
so the frontend renders whatever the backend produces without any per-category
formatting logic. Empty string = no tooltip rendered (no useful tags).

---

## Tabs

Two tabs at the top of the results area: `Education` (default) · `Amenities`.
Segmented pill control (`.tabs` / `.tab.active`) with a **dark ink container**
(`--ink`, #111827) so the bar reads as clearly foregrounded against the
near-white page. Inactive tabs use `rgba(255,255,255,.65)` text so they
recede but stay legible; the active tab is solid white with brand-indigo
text. Panels fade in on switch (`panelIn` keyframe, 300ms ease-out).

**Lazy load with eager fetch:** the Amenities Overpass fetch fires
immediately after `/api/lookup` returns, in parallel with the user reading
the Education panel. When the user clicks the Amenities tab, the data is
almost always already there — the tab click is not gated on network I/O.

**Tab switch must call `mapRef.invalidateSize()` for the tab it's revealing**
(both maps live inside hidden panels; hidden Leaflet containers report zero
dimensions until re-measured).

---

## Motion — Micro-interactions

Personality lives here. Restraint on visuals, delight on gestures.

| Interaction | Detail |
|---|---|
| Card entrance | `opacity 0→1` + `translateY(12px→0)`, 400ms ease-out, staggered 60ms per sibling |
| Card hover | `translateY(-3px)` + shadow `sh-1→sh-2` + background `--result-bg → --result-bg-hover` + accent bar (::before, 3px indigo) scales `Y 0→1` from top |
| Icon badge hover (inside card hover) | rotates `-6deg` + scales `1.08`, background flips white → brand gradient, icon color → white |
| Search input focus | field-icon slides right & scales `1.15`, input `padding-left: 40px → 44px`, border becomes brand + focus ring |
| Chip hover | springy `translateY(-2px)` with `cubic-bezier(0.34, 1.56, 0.64, 1)`; bg → indigo-50 |
| Look-up button | cursor-tracking radial highlight (`::before` with `--x/--y` CSS vars set via mousemove), text nudges `translateX(3px)` on hover |
| SESB badge | outer ring `ping` — box-shadow scales `0→10px` and fades over 2s, infinite |
| Links | underline animates in from right on hover (transform-origin trick) |
| Loading | classic 18px indigo spinner (700ms linear) |
| Reduced motion | all keyframes disabled via `@media (prefers-reduced-motion: reduce)` |

**Easing tokens:**
- Springy / bounce: `cubic-bezier(0.34, 1.56, 0.64, 1)` (chips, icon badges, card entrance)
- Standard: `ease` (backgrounds, colors)
- Linear: spinners only

---

## Icons

Inline SVG only. Stroke-based (Lucide-style), `stroke-width: 2`, `stroke-linecap: round`, `stroke-linejoin: round`. Never emoji as icons.

Set defined inline in `index.html` under `const ico = {...}`. Currently:
- Education icons: `home`, `school`, `baby`, `globe`
- Amenity icons: `playground`, `pharmacy`, `cart` (supermarkets), `gp` (stethoscope), `transit` (train)
- Utility: `info` (ⓘ, inside tooltip trigger), `chev` (▾, chevron rotates 180° when a card is expanded)

The **same SVG** that fronts each amenity card is reused as the map pin glyph
for that category — so users can visually match "the transit card" to "the
purple pins on the map" at a glance. Map pin construction: a 30px circle
filled with the category colour, 2.5px white border, drop shadow, category
SVG stroked in white inside.

---

## Style Guidelines (Micro-interactions)

- **Keywords:** subtle base, gesture-triggered feedback, tactile, contextual response, responsive to hover/focus/press.
- **Best for:** consequential-decision tools, professional SaaS, dashboards where trust matters.
- **Palette temperature:** cool-neutral base, warm anchor on the input area, restrained accent colour (single indigo) with functional colour semantics (green success / red danger / amber warning).

---

## Anti-patterns (do NOT use)

- ❌ Emojis as icons.
- ❌ Different background colours across result cards (breaks the "one coherent group" cue).
- ❌ Adding a hover state to the hero card.
- ❌ Dark mode (not designed for it yet).
- ❌ Instant state changes (0ms transitions).
- ❌ Layout-shifting hovers (only `translateY` and `scale`, never things that push siblings).
- ❌ Missing `prefers-reduced-motion` guard.
- ❌ Contrast under 4.5:1 for body text.

---

## Component recipes

The final HTML is `phase1/index.html` — treat it as the reference implementation. Copy patterns from there rather than re-deriving. Component classes:

- Base: `.hero`, `.cell`, `.map-cell`, `.icon-badge`, `.metric-big` / `.metric-big .n`, `.chip`, `.btn`, `.loading` / `.spinner`, `.error`, `.empty`
- Education badges: `.badges` / `.badge`, `.b-public` / `.b-dist` / `.b-sesb`
- Tabs: `.tabs` / `.tab` / `.tab.active` / `.panel` / `.panel.active`
- Amenities: `.amen-cell` (with `.active` for expanded/selected), `.amen-map-cell`, `.amen-map-hint`, `.amen-body`, `.amen-list` / `.amen-list li .nm` / `.amen-list li .dist`, `.amen-pin` (map marker), `.info-tip` / `.info-body` (tooltip), `.chev` (chevron)

---

## Pre-delivery checklist

- [ ] Hero card `--hero-bg`, no hover state.
- [ ] Every result card uses `--result-bg`, hovers to `--result-bg-hover`.
- [ ] Map cell obeys the same colour rules as other result cards.
- [ ] Icon badge sits on white at rest, flips to brand gradient on card hover.
- [ ] `mapRef.invalidateSize()` called in a `requestAnimationFrame` after `drawMap` AND after every card expand/collapse AND on tab switch.
- [ ] Both tabs: map pins use category icon + category colour (not plain dots).
- [ ] Both tabs: cards clickable, `.cell.active` for the currently plotted category.
- [ ] Both tabs: default map is minimal (address + ring + catchment); category pins appear only on click.
- [ ] Both tabs: `.map-hint` overlay top-left tells user what to do / what's plotted.
- [ ] Amenity cards use `overflow: visible` (info tooltip needs to escape).
- [ ] Amenity list rows use `grid-template-columns: 1fr auto 20px` (distances aligned).
- [ ] Amenities Overpass fetch fires eagerly right after `/api/lookup` returns.
- [ ] All icons inline SVG (no emoji).
- [ ] Focus visible on every interactive element.
- [ ] `prefers-reduced-motion` respected.
- [ ] Contrast ≥ 4.5:1 for body text.
- [ ] Responsive at 375, 768, 1024, 1440.
