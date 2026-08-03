# Design System Master File

> **LOGIC:** When building a specific page, first check `design-system/berlin-family-address-intelligence/pages/[page-name].md`.
> If that file exists, its rules **override** this Master file.
> If not, strictly follow the rules below.

---

**Project:** Berlin Family Address Intelligence (`addrlens`)
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

**Non-negotiable palette rules:**
1. **Hero card** (contains the search input) uses `--hero-bg`. It has **no hover state**. It's the fixed anchor.
2. **All result cards** (address, school, kita, intl, map — every child of the results grid) use `--result-bg`. They must all use the **same colour** so they read as one coherent result set.
3. Result cards hover to `--result-bg-hover` — one shade deeper in the same hue family. Transition: `background .2s ease`.
4. Icon badges inside result cards sit on white (`#FFFFFF`) with `box-shadow: 0 1px 2px rgba(79,70,229,.10)` so they pop against the periwinkle bg. On card hover they flip to the brand gradient (`linear-gradient(135deg,#818CF8,#4F46E5)`) with white icon.

### Typography

- **Body + display:** Inter (400/500/600/700/800) — Google Fonts.
- **Display voice:** tighter tracking (`letter-spacing: -.02em`) at large sizes; no serif.
- **CSS import:**
  ```css
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
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

**Left-stack + height-synced map**, chosen after explicit user comparison:

```css
.grid { display: flex; flex-direction: column; gap: 14px; }
.stack { display: flex; flex-direction: column; gap: 14px; min-width: 0; }
@media (min-width: 900px) {
  .grid  { flex-direction: row; align-items: stretch; }
  .stack { flex: 1.15 1 0; min-width: 0; }
  .map-cell { flex: .85 1 0; min-width: 0; }
}
```

- Left column: address → assigned-school(s) → kita metric → nearest-international, stacked vertically.
- Right column: single map cell. Its height must equal the exact sum of the left stack (flex `align-items: stretch` at the parent, `#map { flex: 1; height: 100%; min-height: 0 }` inside).
- **After the map is drawn**, call `requestAnimationFrame(() => mapRef.invalidateSize())` so Leaflet remeasures the stretched container.
- Mobile (<900px): single column, map gets explicit `min-height: 340px`.

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

Set defined inline in `index.html` under `const ico = {...}`. Currently: `home`, `school`, `baby`, `globe`.

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

The final HTML is `phase1/index.html` — treat it as the reference implementation. Copy patterns from there rather than re-deriving. Component classes: `.hero`, `.cell`, `.map-cell`, `.icon-badge`, `.badges` / `.badge`, `.b-public` / `.b-dist` / `.b-sesb`, `.metric-big` / `.metric-big .n`, `.chip`, `.btn`, `.loading` / `.spinner`, `.error`, `.empty`.

---

## Pre-delivery checklist

- [ ] Hero card `--hero-bg`, no hover state.
- [ ] Every result card uses `--result-bg`, hovers to `--result-bg-hover`.
- [ ] Map cell obeys the same colour rules as other result cards.
- [ ] Icon badge sits on white at rest, flips to brand gradient on card hover.
- [ ] `mapRef.invalidateSize()` called in a `requestAnimationFrame` after `drawMap`.
- [ ] All icons inline SVG (no emoji).
- [ ] Focus visible on every interactive element.
- [ ] `prefers-reduced-motion` respected.
- [ ] Contrast ≥ 4.5:1 for body text.
- [ ] Responsive at 375, 768, 1024, 1440.
