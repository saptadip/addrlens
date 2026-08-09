# Bureaucracy Lens — Design (Spec B)

**Date:** 2026-08-09
**Status:** Approved for implementation planning
**Predecessor:** Spec A (Young Family lens) — landed the lens abstraction this spec reuses.
**Successor:** Spec C (LLM re-narration through lenses) — consumes the two lenses this spec + Spec A ship.

## Context

Spec A landed a working `LensConfig` + `LensTileConfig` abstraction on `CityConfig`, a pure `young_family_lens` composer in `app/core/scorer.py`, a Life Mode header toggle with localStorage-sticky state, and neumorphic tile rendering (single-address grid + compare-view dot matrix). Every Spec A choice about tile shape, tier boundaries, provenance handling, and error semantics carries forward.

Spec B adds a **second lens** aimed at Berlin's bureaucratic infrastructure — the offices English-speaking expats need to find in their first months. It also introduces a **lens picker** (previously deferred because there was only one lens).

Primary audience: same as Spec A — English-speaking expats new to Germany, per `microservice-refactor-plan.md` §0.

## Scope

**In scope:**
- One new lens: **Bureaucracy** (5 tiles).
- Tiles: `buergeramt` (Anmeldung), `finanzamt` (tax office), `standesamt` (marriage / birth), `lea` (residence permit), `arbeitsagentur` (employment agency).
- Distance metric: haversine → estimated walk-minutes; tier ≤ 15 min green, 15–30 min amber, > 30 min red.
- Jurisdiction handling:
  - `buergeramt`, `arbeitsagentur` → **nearest** (both are free-choice in practice).
  - `finanzamt` → nearest, with a caveat that real assignment is by Steuernummer.
  - `standesamt` → **Bezirk-assigned** via point-in-polygon on Bezirksgrenzen.
  - `lea` → single central office (Friedrich-Krause-Ufer 24).
- Data-source strategy (BOD-first, curated hardcoded lists as fallback, per §14.4):
  - Bezirksgrenzen: BOD.
  - Bürgerämter: BOD.
  - Finanzämter, Standesämter, Arbeitsagentur: probe BOD first; if not cleanly published, use curated hardcoded tuples in `berlin.py`.
  - LEA: hardcoded single point.
- **Lens picker** — segmented pill control above the tile grid, `berlin-lens-active-v1` localStorage-sticky, default `young_family`.
- Tile schema **unchanged** from Spec A (`{key, label, icon, tier, rule, numeric, caveat, sources}`).
- Caveats on `buergeramt`, `finanzamt`, `lea`.
- Pure + live selfcheck coverage.

**Out of scope (deliberate):**
- Health insurance offices (TK or others) — category mismatch; may earn its own Health lens later.
- Amtsgericht (courts) — category drift; not admin infrastructure.
- Insurance / Krankenkasse offices — same reason.
- Transit-time via BVG/VBB routing API — walk-minutes proxy is enough for v1; adds external API dependency.
- URL fields on tile schema (users google office names).
- Bezirk-based Finanzamt lookup with a hardcoded PLZ-to-Finanzamt map — deferred in favor of nearest + caveat.
- LEA specialty branches (BIS, ISA, refugee services) as separate tiles — main office only, caveat covers the branch case.
- LLM narration of tiles — Spec C.
- Additional lenses (Student, Couple, Senior) — future.

## Locked decisions

- **Five tiles**, in this display order: `buergeramt`, `finanzamt`, `standesamt`, `lea`, `arbeitsagentur`.
- **Uniform threshold**: walk-minutes ≤ 15 = green, 15–30 = amber, > 30 = red. Boundary inclusive on the greener side.
- **Walk-minutes proxy**: `dist_m / 62` (i.e., 4.8 km/h walking × 1.3 route factor ≈ 62 m/min effective).
- **Lens picker**: segmented pill above the tile grid, two `.pill-btn` buttons, active gets `pill-btn-brand`. `role="tablist"` + `aria-selected`. Sticky via `berlin-lens-active-v1`. Default `young_family` for first-time visitors.
- **Caveats** on Bürgeramt (free choice quirk), Finanzamt (Steuernummer assignment), LEA (specialty branches). Standesamt and Arbeitsagentur have no caveat.
- **LEA**: single central office, hardcoded coordinate in `berlin.py`.
- **Determinism**: bureaucracy composer is fully deterministic (no live per-request fetches on the hot path). All data is boot-preloaded or config-embedded.
- **Response shape**: `/api/lookup` gains a sibling under the existing `lens` key:
  ```
  "lens": { "young_family": {...}, "bureaucracy": {...} }
  ```

## Architecture (delta vs Spec A)

*Where the code lives:*

- `app/cities/base.py` — add new required fields to `CityConfig`: `bezirksgrenzen_wfs_url` / `_layer` / `_field_map`, `buergeramt_wfs_url` / `_layer` / `_field_map`, `finanzamts: tuple`, `standesamts_by_bezirk: dict`, `arbeitsagenturs: tuple`, `lea_office: dict`, `bureaucracy_lens: LensConfig`. No defaults, per the Ship-B rule.
- `app/cities/berlin.py` — instantiate `BUREAUCRACY_LENS` (five tiles with thresholds + caveats). Add curated tuples/dicts for Finanzamt / Standesamt / Arbeitsagentur / LEA. Add new attribution keys.
- `app/core/index.py` — extend `Index.__init__` to preload Bezirksgrenzen (12 polygons) + Bürgerämter (~40 points). Add lookup methods: `bezirk_for(lon, lat)`, `buergeramt_near(lon, lat, radius_m)`, `finanzamt_nearest(lon, lat)`, `standesamt_for(lon, lat)`, `arbeitsagentur_near(lon, lat, radius_m)`.
- `app/core/scorer.py` — add module-level `_walk_minutes(dist_m)` helper. Add five pure `_tier_bureau_*` functions. Add `bureaucracy_lens(cfg, index, lon, lat)` composer. Extend `_sources_for` mapping with bureaucracy tile keys.
- `app/routes/lookup.py` — add a second try/except catch-all block computing `bureaucracy_lens(...)` alongside the existing `young_family_lens(...)`. Response gains `lens.bureaucracy`.
- `web/index.html` — five new SVG entries in the shared `ico = {...}` object: `buergeramt`, `finanzamt`, `standesamt`, `lea`, `arbeitsagentur`.
- `web/static/app.js` — add `LM_ACTIVE_KEY` constant + `getActiveLens()` / `setActiveLens(slug)` / `renderLensPicker(activeSlug)` functions. Update `renderLensSingle(addr)` and `renderLensCompare(addresses)` to read the active lens (was hard-coded to `young_family`). Add delegated click handler for `.lens-picker [data-lens]`. Add `isAnyLensAvailable(addr)` for the toggle-disabled state.
- `web/static/app.css` — 4-line `.lens-picker` block (flex row, gap, margin). Everything else reuses Spec A's neumorphic tile styles, tier colors, and dot-matrix layout.

*Data flow (single-address):*

```
User enters address
   │
   ▼
GET /api/lookup?address=…
   │
   ├─ existing (Spec A): amenities + noise fetch, young_family_lens computed
   │
   └─ new (Spec B): scorer.bureaucracy_lens(...) reads preloaded
                    Bezirksgrenzen + Bürgeramt list + curated federal
                    directories; identifies the address's Bezirk
                    (point-in-polygon) for Standesamt lookup.
        ↓
   response now includes  lens.young_family + lens.bureaucracy
   both as siblings under the top-level `lens` key.

Frontend caches response. Life Mode toggle + lens picker
together decide which grid renders. Both are re-renders,
no HTTP call.
```

*Data flow (compare view):* Each address's `/api/lookup` already populates both lenses on the address object. The picker chooses which grid renders — 7-row young_family or 5-row bureaucracy matrix.

*Response-size cost:* +~1 KB per lookup (5 tiles × ~200 bytes each). Total lookup response was ~30 KB pre-Spec-A, ~31.5 KB after A, ~32.5 KB after B. Negligible.

## `BUREAUCRACY_LENS` shape and scorer contract

*Berlin's instantiation (in `app/cities/berlin.py`):*

```python
BUREAUCRACY_LENS: LensConfig = LensConfig(
    slug="bureaucracy",
    label="Bureaucracy",
    audience_hint="Public admin offices you'll visit as a new arrival",
    tiles=(
        LensTileConfig(
            key="buergeramt", label="Bürgeramt (Anmeldung)", icon="buergeramt",
            thresholds={"green_min": 15, "amber_min": 30},
            caveat="Berlin lets you book any Bürgeramt for Anmeldung — not restricted by PLZ.",
        ),
        LensTileConfig(
            key="finanzamt", label="Finanzamt (tax office)", icon="finanzamt",
            thresholds={"green_min": 15, "amber_min": 30},
            caveat=("Your assigned Finanzamt is set by Steuernummer, not address alone. "
                    "Nearest office shown as a starting point."),
        ),
        LensTileConfig(
            key="standesamt", label="Standesamt (marriage / birth)", icon="standesamt",
            thresholds={"green_min": 15, "amber_min": 30},
        ),
        LensTileConfig(
            key="lea", label="LEA (residence permit)", icon="lea",
            thresholds={"green_min": 15, "amber_min": 30},
            caveat=("Specialty branches exist for skilled workers, students, and refugees — "
                    "check LEA Berlin's website for the right one."),
        ),
        LensTileConfig(
            key="arbeitsagentur", label="Arbeitsagentur", icon="arbeitsagentur",
            thresholds={"green_min": 15, "amber_min": 30},
        ),
    ),
)
```

*Threshold table (uniform across all five tiles):*

| Tile | Green | Amber | Red | Unknown |
|---|---|---|---|---|
| **buergeramt** | ≥ 1 within 15 min walk | ≥ 1 within 30 min | none within 30 min | preloaded list empty (bug) |
| **finanzamt** | nearest within 15 min | 15–30 min | > 30 min | curated list empty (bug) |
| **standesamt** | assigned office within 15 min | 15–30 min | > 30 min | address outside Berlin (bezirk lookup returned None) |
| **lea** | 15 min | 15–30 min | > 30 min | `cfg.lea_office` malformed (bug) |
| **arbeitsagentur** | ≥ 1 within 15 min | ≥ 1 within 30 min | none within 30 min | curated list empty (bug) |

*Walk-minutes proxy (module-level helper in `scorer.py`):*

```python
def _walk_minutes(dist_m: float) -> float:
    """Haversine → estimated walking minutes.
    4.8 km/h walking speed × 1.3 route factor ≈ 62 m/min effective.
    Uniform across bureaucracy tiles."""
    return dist_m / 62
```

*Data preloads in `Index.__init__` (boot-time, one shot):*

- **Bezirksgrenzen** — 12 polygons via WFS, small (§14.6 preload rule). Stored as `self.bezirksgrenzen = [(props, shape(geom)), ...]`.
- **Bürgerämter** — BOD point layer (~40 city-wide). Stored as `self.buergeramts = [{name, address, website, lat, lon}, ...]`.
- **Finanzämter / Standesämter / Arbeitsagentur / LEA** — read directly from `cfg.finanzamts` / `cfg.standesamts_by_bezirk` / `cfg.arbeitsagenturs` / `cfg.lea_office`. No fetch — they're config.

*New `Index` methods (all pure, in-memory lookups):*

```python
def bezirk_for(self, lon, lat) -> Optional[str]:
    """Point-in-polygon over 12 Bezirksgrenzen. Returns Bezirk name or None."""

def buergeramt_near(self, lon, lat, radius_m=3000) -> list:
    """All Bürgerämter within radius, sorted by distance asc. Adds distance_m."""

def arbeitsagentur_near(self, lon, lat, radius_m=5000) -> list:
    """All curated Arbeitsagentur offices within radius, sorted asc."""

def finanzamt_nearest(self, lon, lat) -> Optional[dict]:
    """Nearest Finanzamt from the curated list. Adds distance_m."""

def standesamt_for(self, lon, lat) -> Optional[dict]:
    """Point-in-polygon → Bezirk name → the address's assigned Standesamt.
    Returns None if the address is outside Berlin's Bezirksgrenzen."""
```

*Scorer contract in `app/core/scorer.py`:*

```python
def bureaucracy_lens(cfg, index, lon: float, lat: float) -> dict:
    """Assemble 5 tile results for one address. Pure — no I/O.

    Reads preloaded data from Index (Bezirksgrenzen, Bürgerämter) and
    curated data from CityConfig (Finanzamt / Standesamt / Arbeitsagentur
    / LEA directories). No external fetches on the hot path.
    """
```

Signature is simpler than Young Family's composer: no `amenities` / `noise` / `air` / `heat` inputs because all data is Index-preloaded or config-embedded.

*Output shape (folded into `/api/lookup` alongside `young_family`):*

```json
{
  "lens": {
    "young_family": { "slug": "young_family", "tiles": [7 tiles], "provenance": "..." },
    "bureaucracy": {
      "slug": "bureaucracy",
      "label": "Bureaucracy",
      "audience": "Public admin offices you'll visit as a new arrival",
      "tiles": [
        {
          "key": "buergeramt",
          "label": "Bürgeramt (Anmeldung)",
          "icon": "buergeramt",
          "tier": "green",
          "rule": "≥1 Bürgeramt within 15 min walk",
          "numeric": "3 within 15 min · nearest 8 min (Bürgeramt Prenzlauer Berg)",
          "caveat": "Berlin lets you book any Bürgeramt for Anmeldung — not restricted by PLZ.",
          "sources": ["Geoportal Berlin / Bürgerämter (dl-de/by-2.0)"]
        },
        "… 4 more tiles in this order: finanzamt, standesamt, lea, arbeitsagentur"
      ],
      "provenance": "Geoportal Berlin / Bürgerämter · … · Curated from Bundesagentur für Arbeit …"
    }
  }
}
```

Per-tile field semantics unchanged from Spec A — `{key, label, icon, tier, rule, numeric, caveat, sources}`. Office name lives in `numeric` alongside distance/walk-time.

## Frontend

### Lens picker (segmented pill control above the tile grid)

```html
<div class="lens-picker" role="tablist" aria-label="Choose a lens">
  <button class="pill-btn pill-btn-brand" data-lens="young_family"
          role="tab" aria-selected="true">Young Family (0–6)</button>
  <button class="pill-btn" data-lens="bureaucracy"
          role="tab" aria-selected="false">Bureaucracy</button>
</div>
```

Reuses the existing `.pill-btn` primitive — no new visual grammar. Active pill has `pill-btn-brand` + `aria-selected="true"`. Clicking a pill swaps active state, writes to localStorage, re-renders the lens content.

### localStorage — one new key alongside Spec A's two

```javascript
const LM_STATE_KEY  = 'berlin-lens-mode-v1';       // existing: "on"|"off"
const LM_SEEN_KEY   = 'berlin-lens-mode-seen-v1';  // existing: "1" once seen
const LM_ACTIVE_KEY = 'berlin-lens-active-v1';     // new: "young_family"|"bureaucracy"
const LM_DEFAULT_LENS = 'young_family';            // default for first-time users
```

Follows §14.10 `berlin-lens-<feature>-v<n>` convention.

### JS additions

```javascript
function getActiveLens() {
  try {
    const saved = localStorage.getItem(LM_ACTIVE_KEY);
    if (saved === 'young_family' || saved === 'bureaucracy') return saved;
  } catch (e) {}
  return LM_DEFAULT_LENS;
}

function setActiveLens(slug) {
  if (slug !== 'young_family' && slug !== 'bureaucracy') return;
  try { localStorage.setItem(LM_ACTIVE_KEY, slug); } catch (e) {}
  document.querySelectorAll('.lens-picker [data-lens]').forEach(btn => {
    const on = btn.dataset.lens === slug;
    btn.classList.toggle('pill-btn-brand', on);
    btn.setAttribute('aria-selected', on ? 'true' : 'false');
  });
  renderAllPanels();
}

function renderLensPicker(activeSlug) { /* returns the picker HTML */ }
function isAnyLensAvailable(addr)      { /* checks both lenses for .error */ }
```

Delegated click handler wired once at boot:

```javascript
document.addEventListener('click', (e) => {
  const btn = e.target.closest('.lens-picker [data-lens]');
  if (btn) setActiveLens(btn.dataset.lens);
});
```

### Render updates

`renderLensSingle(addr)` reads `addr.lens[getActiveLens()]` instead of `addr.lens.young_family`. Picker rendered above the header. Everything else unchanged.

`renderLensCompare(addresses)` same delta: reads the active lens's `tiles` for row spec; 7 rows if `young_family`, 5 if `bureaucracy`.

`renderLensTile(tile)` and `renderLensDot(tile)` — **unchanged** from Spec A. Same schema, same rendering.

### New SVG icons in `ico = {...}`

Five entries with `stroke="currentColor"` per Spec A convention (~24×24 viewBox, ~1.6px stroke):

- `buergeramt` — building outline with ID-card overlay.
- `finanzamt` — receipt/document with a currency glyph.
- `standesamt` — book with rings / heart on cover.
- `lea` — passport with stamp or arrow crossing a border.
- `arbeitsagentur` — briefcase or handshake glyph.

### CSS additions (`web/static/app.css`)

```css
/* --- Lens picker (Spec B) --------------------------------------------- */
.lens-picker{
  display:flex; flex-wrap:wrap; gap:.6em;
  margin-bottom:1em;
}
.lens-picker .pill-btn{ font-size:.85em; }
```

That is the entire CSS delta. Everything else reuses Spec A's `.lens-grid`, `.lens-tile`, `.lens-compare`, tier classes, and neumorphic tokens.

### Accessibility

- Picker uses `role="tablist"` with `role="tab"` on the pills. `aria-selected` reflects state. Screen readers read the tablist naturally.
- Keyboard: pills are `<button>`s — Space/Enter activates. Arrow-key navigation between pills is a v2 follow-up.
- Tiles and compare dots — unchanged from Spec A.

## Error handling & provenance

### Failure modes (much smaller than Spec A — deterministic feature)

| Source | Failure mode | Detection |
|---|---|---|
| Bezirksgrenzen (12 polygons) | Preloaded at boot; failure → `/ready` = 503 | Can't fail per-request |
| Bürgerämter (BOD, ~40 points) | Preloaded at boot | Can't fail per-request |
| Finanzämter, Standesämter, Arbeitsagentur | Hardcoded curated tuples/dicts in `berlin.py` | Cannot fail unless config bug |
| LEA | Static hardcoded point in `cfg.lea_office` | Cannot fail unless config malformed |
| Bezirk lookup for the address | Point-in-polygon | Returns `None` for addresses outside Berlin |

Bureaucracy is deliberately a lower-risk lens than Young Family — no per-request WFS fetches on the hot path.

### Per-tile "unknown" semantics

Three invariants from Spec A carry over unchanged:

1. Unknown tiles never default to red.
2. Unknown tiles contribute no sources (`sources: []`).
3. The frontend never silently hides unknown tiles — they render with `.tier-unknown` (gray left-bar, N/A badge, italic rule text).

Realistic "unknown" case in production is the Standesamt tile for an address at the very edge of Berlin whose lookup ambiguously lands outside a Bezirksgrenzen polygon. Rule text: *"Address is outside Berlin's Bezirksgrenzen — Standesamt not determined."*

### Scorer catch-all — both lenses guarded independently

```python
# --- Young Family lens (unchanged from Spec A) ---
try:
    lens_yf = scorer.young_family_lens(cfg, index, lon, lat, air=air, heat=heat,
                                       noise=_noise, amenities=(_amen or {}),
                                       trees=trees_summary, quiet_zone=quiet_zone)
except Exception as e:
    lens_yf = {"slug": "young_family", "error": f"{type(e).__name__}: {e}"}

# --- Bureaucracy lens (Spec B) ---
try:
    lens_bur = scorer.bureaucracy_lens(cfg, index, lon, lat)
except Exception as e:
    lens_bur = {"slug": "bureaucracy", "error": f"{type(e).__name__}: {e}"}
```

Response gets both under the single `lens` key. Independence invariant: a bug in one lens cannot break the other's response.

### Frontend on lens absence / error

1. **Picker is always shown when Life Mode is ON**, even if one lens has an error — users must be able to switch.
2. **Per-lens error** — the tile grid area shows `.lens-empty` when the active lens has `.error`. The other pill still works.
3. **Both-lens error** — the Life Mode toggle in the header is disabled with hover title *"Lens unavailable for this address."* Matches Spec A's fallback shape, extended to check both lenses via `isAnyLensAvailable(addr)`.

### Provenance composition

`_lens_provenance(cfg, tiles)` is unchanged from Spec A. It just receives bureaucracy tiles alongside young_family tiles when called from each composer.

`_sources_for(cfg, key, tier)` extended with new tile keys:

```python
mapping = {
    # ... existing young_family keys ...
    "buergeramt":     [attr.get("buergeramt")],
    "finanzamt":      [attr.get("finanzamt")],
    "standesamt":     [attr.get("standesamt")],
    "lea":            [attr.get("lea")],
    "arbeitsagentur": [attr.get("arbeitsagentur")],
}
```

### New attribution keys in Berlin's `cfg.attribution`

```python
"buergeramt":     "Geoportal Berlin / Bürgerämter (dl-de/by-2.0)",
"bezirksgrenzen": "Geoportal Berlin / Bezirksgrenzen (dl-de/by-2.0)",
"finanzamt":      "Curated from berlin.de Finanzamt-Verzeichnis (public reference)",
"standesamt":     "Curated from berlin.de Standesamt-Verzeichnis (public reference)",
"lea":            "Curated from Landesamt für Einwanderung Berlin (public reference)",
"arbeitsagentur": "Curated from Bundesagentur für Arbeit Berlin-Brandenburg (public reference)",
```

Two attribution rules held from Spec A / §14.5:

1. BOD-first citation for Bürgerämter and Bezirksgrenzen — the real WFS layers get their "Geoportal Berlin / X (dl-de/by-2.0)" line.
2. "Curated from" honesty for the hardcoded federal directories — transparent that these are curated references rather than live open-data feeds.

## Testing

### Pure selfcheck — `app/core/scorer.py` `if __name__ == "__main__"`

1. **`_walk_minutes` sanity.** `_walk_minutes(0) == 0`, `_walk_minutes(62) == 1.0`, `_walk_minutes(930)` within float tolerance of `15.0`.

2. **Boundary sweep per tier fn** — synthetic offices at exact boundaries. Every tier fn (`_tier_buergeramt`, `_tier_finanzamt`, `_tier_standesamt`, `_tier_lea`, `_tier_arbeitsagentur`) tested at 930 m (green boundary), 931 m (amber), 1860 m (amber boundary), 1861 m (red), and the missing-input case (`[]` or `None`) yielding `unknown`.

3. **Composer determinism.** Two identical calls to `bureaucracy_lens(...)` return deep-equal dicts. Locks in the "no live fetch" contract.

4. **Composer — empty vs unavailable inputs (distinguish, per Spec A rule).** Stub `Index` with all-empty results → tiles produce `red` where the source is present but empty (list case); Bezirk lookup returning `None` → Standesamt goes `unknown`. Non-Standesamt tiles do NOT go unknown from a valid empty list — they go red.

5. **Caveat pass-through.** `_caveats["buergeramt"]` truthy, `_caveats["finanzamt"]` contains "Steuernummer", `_caveats["lea"]` contains "Specialty branches". `_caveats["standesamt"] == "" and _caveats["arbeitsagentur"] == ""`.

6. **Provenance composition.** Covered by Spec A's existing `_lens_provenance` tests — no new tests needed (helper is shared).

### Cities isolation

`run_cities_isolation()` auto-covers the extended contract: adding required (no-default) fields to `CityConfig` (`bezirksgrenzen_*`, `buergeramt_*`, `finanzamts`, `standesamts_by_bezirk`, `arbeitsagenturs`, `lea_office`, `bureaucracy_lens`) means any city module missing them fails at import. Berlin's config must spell all of them.

### Live selfcheck — `app/selfcheck.py` extension (Berlin-guarded)

Two known-good addresses cover Bezirk-based Standesamt assignment and distance-based tier variation:

**Kastanienallee 12, 10435** (Prenzlauer Berg → Pankow Bezirk):
- `index.bezirk_for(lon, lat) == "Pankow"`.
- `lens.tiles` length 5, keys in exact order `[buergeramt, finanzamt, standesamt, lea, arbeitsagentur]`.
- `standesamt.numeric` contains "Pankow" (the assigned Bezirk office).
- `lea.numeric` contains "LEA" and a walk-minutes reading.
- No tile is `unknown` in dense inner Berlin.
- At least one tile is `green` — defensive.
- Caveats on `buergeramt`, `finanzamt`, `lea` match config verbatim.
- `provenance` non-empty; contains at least the Bürgerämter BOD attribution.

**Bergmannstraße 27, 10961** (Kreuzberg → Friedrichshain-Kreuzberg Bezirk):
- `index.bezirk_for(lon, lat) == "Friedrichshain-Kreuzberg"`.
- `standesamt.numeric` contains "Friedrichshain-Kreuzberg" (or its official short form).
- LEA tile's walk-minutes > Pankow's (Kreuzberg is farther from Wedding).

**Determinism guard**: compute the lens twice on Kastanienallee → deep-equal results.

Graceful-skip pattern preserved: any assertion whose data source is genuinely unavailable prints "skipped" and continues.

Prints `bureaucracy lens asserts OK` just before `→ live selfcheck OK`.

### Frontend live-browser QA (per §14.12) — pre-ship checklist

1. **Initial state (fresh profile).** Life Mode toggle visible + pulsing. Toggle OFF. When toggled ON, picker appears with Young Family selected (default) and 7 tiles.
2. **Picker click — switch to Bureaucracy.** Click "Bureaucracy" pill. It becomes `pill-btn-brand`; the other loses brand styling. 5 tiles render. `localStorage.getItem('berlin-lens-active-v1') === 'bureaucracy'`.
3. **State persistence for active lens.** Reload. Life Mode still ON, active lens still Bureaucracy, 5 tiles still visible.
4. **Switch back to Young Family.** Click the pill; 7 tiles return. localStorage flips back.
5. **Compare view — Bureaucracy.** Load 2 addresses. Toggle Life Mode ON with active=bureaucracy. Verify 5-row × 2-col dot matrix. Hover a dot → tooltip contains rule + numeric.
6. **Compare view — switch lens live.** Click Young Family pill in compare view. Matrix re-renders as 7×2. Click Bureaucracy back — 5×2.
7. **Standesamt correctness at address.** Enter Kastanienallee 12, 10435 → Bureaucracy Standesamt tile numeric contains "Pankow". Enter Bergmannstraße 27, 10961 → tile numeric contains "Friedrichshain-Kreuzberg".
8. **Bürgeramt caveat visible.** Bürgeramt tile shows the small italic caveat text at the bottom of the tile.
9. **Outage state — one lens errors.** Simulate a `raise RuntimeError` in `bureaucracy_lens` at the composer top. Reload. Young Family pill still works. Bureaucracy pill greys / shows `.lens-empty` when active. Life Mode toggle itself still enabled (Young Family works). Revert.
10. **Both lenses error.** Simulate raise in both composers. Reload. Life Mode toggle is greyed with hover title *"Lens unavailable for this address."* Clicking is a no-op. Revert.

Screenshots captured during QA are ephemeral (cleaned up after the session), per §14.12.

## Non-goals

- **pytest / JS unit tests / mocks / CI wiring** (same as Spec A).
- **Prometheus counters per lens** — `prometheus-client` is already a dep; separate ops task.
- **Structured error codes on the response** — free-text `error` strings suffice.
- **Retries inside the scorer** — nothing to retry (no live fetches for bureaucracy).
- **Arrow-key navigation between picker pills** — v2 accessibility polish.
- **Animated transition when lens switches** — a plain re-render + `pill-btn-brand` swap is sufficient visual feedback.
- **Deep-link URLs for a specific lens** (`#lens=bureaucracy`) — future.
- **Per-address "last lens" memory** — single global sticky state; matches Life Mode.
- **Testing every Bezirk's Standesamt assignment individually** — two representative Bezirke (Pankow, Friedrichshain-Kreuzberg) + config coverage assertion (`len(cfg.standesamts_by_bezirk) == 12`).
- **URL / hours / phone fields on tile schema** — users google office names.

## References

- `CLAUDE.md` — Berlin ADI micro-service architecture.
- `docs/superpowers/specs/2026-08-09-young-family-lens-design.md` — Spec A (predecessor).
- `docs/superpowers/follow-ups/2026-08-09-young-family-lens.md` — Spec A deferred minors.
- `../../../berlin-family-address-intelligence-product-doc.md` §14 — engineering conventions.
- `../../../microservice-refactor-plan.md` §0 — locked defaults (audience, GDPR, no-scraping).
- `app/cities/base.py` — existing `CityConfig` + `LensConfig` + `LensTileConfig` dataclasses.
- `app/core/scorer.py` — existing pure `young_family_lens` composer + tier fns + provenance helpers.
- `app/routes/lookup.py` — existing aggregating endpoint with Young Family lens folded in.
- `web/static/app.js` — existing `renderLensSingle`, `renderLensCompare`, `renderLensTile`, `renderLensDot`, Life Mode state.
