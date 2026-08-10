# Young Family Lens — Design (Spec A)

**Date:** 2026-08-09
**Status:** Approved for implementation planning
**Sequel specs:** Spec B (Bureaucracy lens) and Spec C (LLM re-narration) build on this one and reuse its lens abstraction.
**See also:** [Spec D — Clickable Lens Tiles](2026-08-10-clickable-lens-tiles-design.md) extends every tile in this spec with a `features` array + interactive modal / map integration. The tile schema described below (`{key, label, icon, tier, rule, numeric, caveat, sources}`) gains one required field (`features`) and one optional field (`metadata`, refuge tile only) once Spec D lands.

## Context

The app today surfaces objective open-data about a Berlin address — schools, kitas, hospitals, transit, noise, air, heat, protection zones, etc. It is data-first by design (§14 engineering conventions).

Primary audience is English-speaking expats new to Germany (`microservice-refactor-plan.md` §0). Expats face a specific problem: they do not know what to prioritise in a new city. The current dashboard shows everything — cognitive overload — and doesn't answer *"is this address good for someone like me?"*

This spec introduces the **Young Family lens** — an opinionated view over the existing data that answers that question for families with kids under 6. It also establishes the **lens abstraction** that Spec B and Spec C will consume. Getting the abstraction right on one profile is the whole point of shipping just this one.

## Scope

**In scope:**
- One header toggle: **Life Mode**.
- One lens: **Young Family (0–6)**.
- Seven traffic-light tiles: kita reachability, playground, pediatrician, façade noise, summer heat, air quality (NO₂), quiet/green refuge.
- Server-computed tier logic in `app/core/scorer.py`.
- `LensConfig` + `LensTileConfig` dataclasses on `CityConfig`.
- Single-address view and compare-up-to-5 view.
- Onboarding pulse on the toggle for first-time visitors.
- Pure + live selfcheck coverage.

**Out of scope (deliberate):**
- Additional lenses (Student, Couple, Senior) — future.
- Kiez / vibe lens — Spec B.
- LLM narration over tiles — Spec C.
- User-configurable thresholds — v1 is monolithic.
- User-input parameters like "youngest child age" — v1 is monolithic.
- Tile drill-down modal — natural v2 addition.
- Non-Berlin cities — deferred with Ship C.

## Locked decisions

- **Age band:** 0–6 pre-primary only. Primary-school signals already exist elsewhere in the dashboard and are not re-weighted here.
- **Scoring shape:** 7 independent green/amber/red tiles. No aggregate score. A single scalar hides its assumptions; per-need traffic lights let the user evaluate the tradeoffs directly.
- **Tile set:** kita reachability, playground, pediatrician, noise, heat, air, refuge.
- **Pediatrician tile is IN** with a permanent honest-coverage caveat ("OSM community-tagged — inner-district coverage good, outer may under-report"). Verified against the running app that the required data is available: `healthcare:speciality=paediatrics` is parsed at `app/core/amenities.py:87` and rendered at `web/static/app.js:670`. Sample check on Bergmannstraße 27 confirmed one paediatric-tagged practice within 800m.
- **UI shape:** header toggle switches the entire app between "raw data mode" (current tabs) and "Life Mode" (lens tabs). Global — couples single-address and compare views.
- **Default state:** OFF, with a pulsing highlight on the toggle for first-time visitors. Sticky via localStorage.
- **Tile content:** tier badge + rule + numeric evidence. No drill-down modal in v1.
- **Compute location:** server-side, always included in `/api/lookup` under `lens.young_family`. Zero-latency toggle. No new endpoint.
- **Boundary convention:** every threshold is **inclusive on the greener side** (400m is green; 400.01m is amber; 55 dB is green; 55.01 is amber).

## Architecture

*Where the code lives:*

- `app/cities/base.py` — two new frozen dataclasses (`LensTileConfig`, `LensConfig`); one new required field on `CityConfig` (`young_family_lens: LensConfig`). No default: matches the Ship-B rule that every city must spell every field.
- `app/cities/berlin.py` — `YOUNG_FAMILY_LENS: LensConfig` instantiation with all 7 tiles and their threshold values.
- `app/core/scorer.py` — pure tier functions per tile (`_tier_kita`, `_tier_playground`, `_tier_pediatrician`, `_tier_noise`, `_tier_heat`, `_tier_air`, `_tier_refuge`) plus one composer `young_family_lens(...)`.
- `app/core/amenities.py` — small helper `is_paediatric(tags) -> bool` factored out of the tag parsing that already exists at line 87 of that file.
- `app/routes/lookup.py` — call the scorer at the end of the handler; fold result under `lens.young_family` in the response.
- `web/index.html` — Life Mode toggle in header; new icon entries in the shared `ico = {...}` object.
- `web/static/app.js` — Life Mode toggle init, state management, render functions for tiles and compare matrix.
- `web/static/app.css` — toggle pill styling, keyframes pulse animation, tile grid, dot matrix, `.tier-unknown` class if not already covered.

*Data flow (single-address):*

```
User enters address
   │
   ▼
GET /api/lookup?address=…                                (unchanged endpoint contract)
   │
   ├─ existing: geocode → catchment → schools → kitas → amenities → noise → heat → air → …
   │
   └─ new: scorer.young_family_lens(...) computes 7 tiles from data already present
         ↓
   response now includes  lens.young_family.tiles: [...]  +  lens.young_family.provenance

Frontend caches response per address.

User flips Life Mode toggle → no HTTP → pure re-render from cache.
```

*Data flow (compare view):* each address's `/api/lookup` fetch already populates `lens.young_family` on the address object; Life Mode ON re-renders the compare grid as 7 rows × N columns of tier dots.

## `LensConfig` shape and scorer contract

```python
# app/cities/base.py
@dataclass(frozen=True)
class LensTileConfig:
    key:        str    # "kita" | "playground" | "pediatrician" |
                       # "noise" | "heat" | "air" | "refuge"
    label:      str
    icon:       str
    thresholds: dict   # tile-specific; each _tier_* fn interprets its own shape
    caveat:     str = ""   # long-lived tile-specific disclosure, always displayed

@dataclass(frozen=True)
class LensConfig:
    slug:           str    # "young_family"
    label:          str    # "Young Family (0–6)"
    audience_hint:  str    # "For a family with kids under 6"
    tiles:          tuple  # tuple[LensTileConfig, ...] — order = display order
```

`CityConfig` gains one required field (no default): `young_family_lens: LensConfig`.

*Berlin's threshold table — the whole editorial layer in one place:*

| Tile | Green | Amber | Red | Unknown |
|---|---|---|---|---|
| **kita** | ≥3 kitas within 400m | ≥1 within 800m | none within 800m | — (preloaded at boot) |
| **playground** | ≥1 within 400m | 400–800m | none within 800m | Overpass/BOD both failed |
| **pediatrician** | ≥1 paediatric-tagged GP within 800m | 800–1500m | none within 1500m | Overpass unavailable |
| **noise** | L_DEN ≤ 55 dB | 55–60 dB | > 60 dB | noise WFS unavailable |
| **heat** | day_class ∈ {keine, geringe} | {mittlere, starke} | {sehr starke, extreme} | Umweltatlas WFS unavailable |
| **air** | NO₂ ≤ 20 μg/m³ (WHO 2021) | 20–40 | > 40 | Umweltatlas WFS unavailable |
| **refuge** (composite) | quiet ≤ 400m **OR** crown ≥ 25% | quiet ≤ 1000m **OR** crown ≥ 15% | neither | both signals unavailable |

Composite refuge is `OR` at both tiers so the tile is forgiving of one missing signal — matches §14.7 partial-success convention.

*Scorer contract in `app/core/scorer.py`:*

```python
def young_family_lens(cfg, index, lon, lat, *,
                      air, heat, noise, amenities,
                      trees, quiet_zone) -> dict:
    """Assemble 7 tile results. Pure — no I/O, no re-fetching.

    All inputs are values already computed elsewhere in /api/lookup;
    the lens is a view over data the address already carries. Never call
    WFS from here — that keeps the lens from ever disagreeing with the
    raw data in the same response.
    """
```

*Output shape (folded into `/api/lookup` response under `lens.young_family`):*

```json
{
  "slug": "young_family",
  "label": "Young Family (0–6)",
  "audience": "For a family with kids under 6",
  "tiles": [
    {
      "key": "kita",
      "label": "Kita reachability",
      "icon": "kita",
      "tier": "green",
      "rule": "≥3 kitas within 400m",
      "numeric": "5 within 400m · nearest 180m",
      "caveat": "",
      "sources": ["Geoportal Berlin / Kindertagesstätten"]
    },
    "… 6 more tiles in this order: playground, pediatrician, noise, heat, air, refuge"
  ],
  "provenance": "Geoportal Berlin / Kindertagesstätten · Grünanlagenbestand · Strategische Lärmkarten · Umweltatlas · © OpenStreetMap contributors (ODbL)"
}
```

Per-tile field semantics:

- **`tier`** — `"green" | "amber" | "red" | "unknown"`. Single source of truth for tile colour.
- **`rule`** — human-readable threshold that produced this tier ("≥3 kitas within 400m"). Displayed under the tier badge.
- **`numeric`** — the underlying fact ("5 within 400m · nearest 180m"). Displayed as fine print.
- **`caveat`** — permanent tile-specific disclosure (currently only the pediatrician tile has one). Empty string default; frontend hides if empty. Distinct from `rule`/`numeric` — the caveat is about the data source's structural limits, not about this address's tier.
- **`sources`** — array of attribution strings, one per data source this tile touched. Unknown tiles contribute `[]`.

## Frontend

### Header toggle

Pill button in the header, right-aligned. Two visual states:

```
[  ○  Life Mode        ]      ← OFF (subtle border, muted text)
[  ●  Life Mode: Family ]     ← ON (brand-color fill, active state)
```

Keyboard-activatable (Space / Enter). `role="switch"` + `aria-pressed` reflects state.

On first visit (no `berlin-lens-mode-seen-v1` in localStorage), the button gets a `.pulse` class — a CSS-keyframes glow that draws the eye. Pulse stops on **first click** or after **30 seconds elapsed**, whichever first. Either path writes `berlin-lens-mode-seen-v1=1` so the pulse never fires again.

### Single-address view (Life Mode ON)

The raw-data tab bar (Environment / Amenities / Medical / Connectivity / Education) hides. In its place: the "Young Family (0–6)" heading with the audience-hint subline, the 7-tile grid, and the provenance footer.

Grid layout: CSS `grid-template-columns: repeat(auto-fit, minmax(240px, 1fr))` — 3-per-row desktop, 2-per-row tablet, 1-per-row mobile. Each tile reuses the existing `.cell` shape and left color-bar convention (§14.9) so it visually rhymes with every other card in the app. Only the tier-colour class changes (`.tier-green | .tier-amber | .tier-red | .tier-unknown`).

Unknown tiles render with `.tier-unknown`: gray left-bar, gray tier badge reading "N/A", italic rule text (e.g., *"Umweltatlas WFS unavailable"*). No numeric line. Nothing is silently hidden — matches your `[hidden]{display:none!important}` rule from §14.9.

### Compare view (Life Mode ON)

```
                Addr A   Addr B   Addr C   Addr D
Kita              ●        ●        ●        ●
Playground        ●        ●        ●        ●
Pediatrician      ●        ●        ●        ●
Noise             ●        ●        ●        ●
Heat              ●        ●        ●        ●
Air               ●        ●        ●        ●
Refuge            ●        ●        ●        ●
```

7 rows × up-to-5 columns. Each cell is a colored dot (the tile's tier color). Hover / tap → floating tooltip with `rule` + `numeric` anchored to the cell. Row headers = tile labels; column headers = address short labels (already computed by the compare view today). This is where the lens earns its keep — the "which of these 5 is best for us" question collapses into scanning 35 dots.

### localStorage keys

Both follow the §14.10 `berlin-lens-<feature>-v<n>` convention:

- `berlin-lens-mode-v1` — `"on" | "off"`, current mode state. Read at app boot.
- `berlin-lens-mode-seen-v1` — `"1"` once the user has seen (or dismissed) the pulse. Read at boot.

### Accessibility

- Toggle: `role="switch"`, `aria-pressed`, keyboard-flips on Space / Enter.
- Tiles: `<section>` with `aria-label` composed from `label` + `tier` + `rule` (e.g., *"Kita reachability, tier green: ≥3 kitas within 400m"*).
- Compare dots: `<button>` with the same aria-label shape so screen-readers can navigate the matrix cell-by-cell.
- Focus after toggle stays on the toggle (does not jump into the newly-rendered content, which would be disorienting).

## Error handling & provenance

### Failure modes

| Source | Failure mode | Detection |
|---|---|---|
| Kita, Fountains, Quiet zones, Fire, Pools, Protection | Preloaded at boot — can't fail per-request | `/ready` gates the service until Index is built |
| Playgrounds | Overpass + BOD polygon (per-request) | `amenities.playgrounds` empty or carries `_error` |
| Pediatricians (paediatric filter over `gps`) | Overpass query per-request | `amenities.gps.items` empty or missing |
| Noise (façade L_DEN) | `noise_at()` — per-request WFS | `{"unavailable": true, "error": …}` |
| Heat (Umweltatlas day_class) | `summer_heat_at()` — per-request WFS | `{"unavailable": true}` |
| Air (NO₂) | `air_quality_at()` — per-request WFS | `{"unavailable": true}` |
| Refuge (composite) | Trees WFS per-request; quiet zone preloaded | Trees may error; quiet zone always present |

### Per-tile "unknown" semantics

Any tile whose upstream data is missing or explicitly unavailable produces:

```json
{
  "key": "air",
  "label": "Air quality (NO₂)",
  "tier": "unknown",
  "rule": "Air-quality data unavailable",
  "numeric": "Umweltatlas WFS down",
  "caveat": "",
  "sources": []
}
```

Three invariants:

1. **Unknown tiles never default to red.** A silent WFS outage would otherwise flip a healthy address's tile red overnight.
2. **Unknown tiles contribute no sources** (`sources: []`) so the lens-level `provenance` string doesn't cite datasets that didn't actually contribute.
3. **Refuge is forgiving.** Composite `OR` means losing one signal still produces a real tier — only reports unknown if both fail.

### Scorer catch-all

```python
# app/routes/lookup.py, at the end of the handler
try:
    lens_yf = scorer.young_family_lens(cfg, index, lon, lat,
                                       air=air, heat=heat, noise=n,
                                       amenities=amenities_block,
                                       trees=trees_summary,
                                       quiet_zone=quiet_zone)
except Exception as e:
    # The lens is additive. Never break /api/lookup for it (§14.7).
    lens_yf = {"slug": "young_family", "error": f"{type(e).__name__}: {e}"}
```

### Frontend on lens absence / error

- `data.lens?.young_family` missing OR has `error` → Life Mode toggle stays visible but disabled, with hover title *"Lens unavailable for this address."*
- Any tile with `tier: "unknown"` renders with `.tier-unknown` styling; nothing is silently hidden.

### Provenance composition

```python
def _lens_provenance(cfg, tiles):
    """Union of sources cited by tiles that contributed a real tier.
    Insertion-order preserved (Python 3.7+ dict semantics) → deterministic."""
    seen, out = set(), []
    for tile in tiles:
        for s in tile.get("sources") or []:
            if s and s not in seen:
                seen.add(s); out.append(s)
    return " · ".join(out)
```

Only non-unknown tiles contribute sources — matches §14.5 "provenance reflects what actually contributed to *this* result, not a static footer." De-duplicated. Insertion order preserved so equivalent tile sets produce identical strings — testable in the pure selfcheck. Empty string if every tile is unknown; frontend hides the footer entirely in that case.

## Testing

### Pure selfcheck — `app/core/scorer.py` `if __name__ == "__main__"`

1. **Boundary sweep per tile** — synthetic inputs straddling every threshold; asserts the correct tier per the inclusive-on-greener-side rule. Example: kita with 3 features at 400m exactly → `green`; 3 features at 400.01m → `amber`. Noise 55 dB → `green`; 55.01 → `amber`. Air 20 μg/m³ → `green`; 20.01 → `amber`.
2. **Sources composition** — synthetic mixed tiles → correct de-duplicated ordered provenance string.
3. **Caveat pass-through** — pediatrician's `caveat` string present verbatim in the returned tile dict; every other tile's `caveat` is `""`.
4. **Empty-but-available inputs → red, not unknown.** Kita list empty, playground list empty, pediatrician filter empty (Overpass succeeded but 0 matches), noise/heat/air present with valid values that fail every green/amber threshold. Assert every tile is `red`, none is `unknown`. This is the ordinary "sparse suburb" case — empty is a factual answer, not an outage.
5. **Unavailable inputs → unknown where possible, red where not.** Every WFS-backed source (`noise`, `heat`, `air`, `trees`) marked `{"unavailable": true}`; Overpass buckets flagged with `_error`. Assert: `noise`, `heat`, `air`, `pediatrician`, `playground`, `refuge` tiles are `unknown`; `kita` is `red` (its data is preloaded at boot and cannot report unavailable, so its unknown state is unreachable by design — the `—` in the tile table). Provenance string contains only sources cited by the surviving `red` tile(s); no exception raised; response shape still valid.

Bails on first failure with a readable diff (existing `assert x == y` style in `app/core/*`).

### Cities isolation

`app.selfcheck.run_cities_isolation()` already boots each city module in a fresh subprocess. Making `young_family_lens` a required (no-default) field means any city missing the field fails at import time — protection is automatic. No new test needed; the existing runner starts covering this contract.

### Live selfcheck — `app.selfcheck.run_live_selfcheck` (Berlin-guarded)

Two known-good addresses cover two very different lens shapes.

**Kastanienallee 12** (Prenzlauer Berg — dense, family-heavy):

- `lens.tiles` is a list of length 7, keys in expected order (kita, playground, pediatrician, noise, heat, air, refuge).
- Every tile has non-empty `label`, `rule`; `tier` in `{green, amber, red, unknown}`.
- `kita` tile is `green` (dense area — always ≥3 kitas within 400m; existing selfcheck already loads ≥3 nearby).
- At least one tile is `green` — defensive; the lens must produce *some* positive signal in dense inner Berlin.
- `provenance` non-empty and contains "Kindertagesstätten" (kita source must be cited since kita is green).
- **Consistency invariant:** no tile is `unknown` unless the matching raw block in the same `/api/lookup` response is also `unavailable`. The lens cannot disagree with the raw data about whether a signal exists.

**Bergmannstraße 27** (Kreuzberg — the pediatrician anchor):

- `pediatrician` tile is `green` (Dr. Berns ~430m — verified live earlier, stable open data).
- `pediatrician` tile's `numeric` mentions distance.
- `pediatrician` tile's `caveat` equals the configured caveat string verbatim.
- `playground` tile is `green` (Marheinekeplatz Spielplatz ~75m).

**Graceful degradation of the live block.** Any assertion whose data source is `unavailable` at test time prints "skipped: <reason>" and continues — mirrors existing `n.get("unavailable")` handling for the Kurfürstendamm 195 noise assertion. Live asserts must never fail the whole selfcheck for a transient upstream outage.

### Frontend live-browser QA (per §14.12) — pre-ship manual checklist

1. **Initial state.** Fresh browser profile (`localStorage.clear()`): Life Mode toggle visible in header, pulsing. Toggle text reads "Life Mode" (OFF state).
2. **Pulse decay by timeout.** Wait 30s without interacting. Pulse stops. `localStorage.getItem('berlin-lens-mode-seen-v1')` returns `"1"`.
3. **Pulse decay by click.** Fresh profile. Click the toggle before 30s. Pulse stops. `berlin-lens-mode-seen-v1` set. Toggle shows ON state.
4. **Mode switch — single address.** With an address loaded and Life Mode OFF, toggle ON. Raw-data tab bar hides. 7-tile grid renders under "Young Family (0–6)" heading. Toggle OFF. Raw tabs restored.
5. **State persistence.** With Life Mode ON, reload. Mode still ON.
6. **Compare view.** Load 2+ addresses. Toggle ON. 7-row × N-column dot matrix renders. Hover a dot → tooltip with rule + numeric. Toggle OFF. Existing per-address panels return.
7. **Outage state.** Point the app at a Berlin instance with Umweltatlas WFS blocked (mock via `/etc/hosts` or a proxy). Load Kastanienallee 12. Air and Heat tiles render gray with italic *"Umweltatlas WFS unavailable"* rule text. Five other tiles render normal tiers. Provenance footer omits Umweltatlas.
8. **Keyboard accessibility.** Tab to Life Mode toggle. Space → mode flips. Space → flips back. Tab through tiles when Life Mode is ON — each tile focusable, screen-reader announces `aria-label`. Tab through compare dots — each individually focusable and announced.
9. **Missing lens block.** With a temporarily-throwing scorer, reload. Rest of `/api/lookup` renders normally. Life Mode toggle greyed with hover title "Lens unavailable for this address."

Screenshots captured during QA are ephemeral (cleaned up after the session), per §14.12.

## Non-goals

- **pytest / JS unit tests / mocks / CI wiring.** Everything runs via `python -m app.core.scorer` and `python -m app.selfcheck`; frontend correctness lives in the browser QA checklist.
- **Prometheus metrics for lens computation failures.** `prometheus-client` is already a dep — add later.
- **Structured error codes in the response.** Free-text `rule`/`numeric` is enough for v1; schema evolution if a UI ever needs to react programmatically to specific failures.
- **Retries inside the scorer.** Retries live where the fetch lives (`app/core/wfs.py`), not in the pure scorer.
- **Multiple lenses in a sub-tab bar inside Life Mode.** There's only one lens in Spec A; the "Young Family (0–6)" header sits above the grid. When Spec B lands, a lens picker appears here.
- **"Sort compare view by tile" affordance** — click row header to sort columns by that tile's tier. Nice but not needed for v1.
- **Onboarding tooltip prose.** The pulse itself is the onboarding.
- **Tile drill-down modal** — deferred; natural v2 addition on top of the current tile shape.

## References

- `CLAUDE.md` — Berlin ADI micro-service architecture (per-city boot, Index preload, /health vs /ready).
- `../../../berlin-family-address-intelligence-product-doc.md` §14 — engineering conventions.
- `../../../microservice-refactor-plan.md` §0 — locked defaults (audience, GDPR, no-scraping).
- `app/cities/base.py` — existing `CityConfig` frozen dataclass shape.
- `app/core/scorer.py` — existing pure-function tier-logic module.
- `app/routes/lookup.py` — existing aggregating endpoint.
- `app/core/amenities.py:87` — existing paediatric tag parsing (server-side, will be reused).
- `web/static/app.js:670` — existing paediatric tag parsing (client-side, reference only).
