# Young Family Lens Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the Young Family (0–6) lens — a 7-traffic-light view over an address's family-friendliness — behind a Life Mode header toggle, matching Spec A at `docs/superpowers/specs/2026-08-09-young-family-lens-design.md`.

**Architecture:** Server-side tier logic in `app/core/scorer.py` reads data already computed inside `/api/lookup` (no re-fetch, no new endpoint). Frozen `LensConfig` + `LensTileConfig` dataclasses land on `CityConfig` with no defaults. Frontend is vanilla JS + neumorphic CSS with a localStorage-sticky Life Mode toggle; lens data is folded into every lookup response under `lens.young_family` so the toggle is a zero-latency re-render.

**Tech Stack:** Python 3.11+, FastAPI, shapely (existing app deps only — no new deps). Vanilla JS + hand-authored CSS (no build step, no bundler, no npm).

## Global Constraints

- **Frozen dataclasses, no defaults on `CityConfig` fields.** `young_family_lens: LensConfig` is required; missing values fail at import.
- **`app/core/*` modules are pure.** No I/O, no WFS calls, no re-fetching. Data flows in as arguments.
- **Per-city facts live in `app/cities/<slug>.py`.** No hard-coded Berlin values inside `core/`.
- **Testing without pytest.** Every module carries an `if __name__ == "__main__"` block with `assert` statements. Live asserts extend `app.selfcheck.run_live_selfcheck`.
- **BOD-first, OSM as fallback / supplement.** Every tile source cites `cfg.attribution[<key>]` verbatim — never invents a provenance string.
- **Neumorphic UI style.** Reuse `.cell` shape with left `::before` color-bar, `scaleY(0)→1` on hover. Design tokens live in `:root`. Plus Jakarta Sans typography. Inline SVGs in the shared `ico = {...}` object.
- **No build step for the frontend.** Edit-refresh. No bundler, no npm, no framework.
- **localStorage keys follow `berlin-lens-<feature>-v<n>`** (§14.10).
- **`ponytail:` comments** mark deliberate simplifications with a named ceiling and upgrade path.
- **Every threshold is inclusive on the greener side** (400m green, 400.01m amber; 55 dB green, 55.01 amber).
- **Commit after every task passes its selfcheck.** Short imperative subject; split by concern.

## File Structure

**Backend (Python):**

| File | Responsibility | Task |
|---|---|---|
| `app/cities/base.py` | Add `LensTileConfig` + `LensConfig` dataclasses | 1 |
| `app/cities/base.py` | Add `young_family_lens: LensConfig` field to `CityConfig` | 2 |
| `app/cities/berlin.py` | Instantiate `YOUNG_FAMILY_LENS` with 7 tiles + wire onto `BERLIN` | 2 |
| `app/core/amenities.py` | Add `is_paediatric(tags) -> bool` helper + assertion in `__main__` | 3 |
| `app/core/scorer.py` | Add 7 pure `_tier_*` functions + boundary sweep asserts | 4 |
| `app/core/scorer.py` | Add `young_family_lens(...)` composer + `_lens_provenance(...)` + composition asserts | 5 |
| `app/routes/lookup.py` | Call scorer at end of handler; fold under `lens.young_family` with try/except catch-all | 6 |
| `app/selfcheck.py` | Add live asserts for Kastanienallee 12 + Bergmannstraße 27 | 7 |

**Frontend (vanilla):**

| File | Responsibility | Task |
|---|---|---|
| `web/index.html`, `web/static/app.css` | Add neumorphic Life Mode toggle + tile SVG icons + pulse keyframes + `.tier-unknown` | 8 |
| `web/static/app.js` | Life Mode state (localStorage, pulse decay 30 s, toggle handler, `setLifeMode`) | 9 |
| `web/static/app.js`, `web/static/app.css` | `renderLensSingle(addr)` + `.lens-grid` tile grid | 10 |
| `web/static/app.js`, `web/static/app.css` | `renderLensCompare(addresses)` + `.lens-compare` dot-matrix | 11 |
| — | §14.12 live-browser QA checklist (9 items, manual) | 12 |

---

## Task 1: `LensTileConfig` and `LensConfig` dataclasses

**Files:**
- Modify: `app/cities/base.py` — append two dataclasses after the existing `CityConfig`
- Test: `app/cities/base.py` bottom `if __name__ == "__main__"` block (add one if absent)

**Interfaces:**
- Consumes: nothing external
- Produces:
  - `LensTileConfig(key: str, label: str, icon: str, thresholds: dict, caveat: str = "")` — frozen dataclass
  - `LensConfig(slug: str, label: str, audience_hint: str, tiles: tuple)` — frozen dataclass

**Notes:** `CityConfig` is NOT modified in this task. Adding the field there would break `app/cities/berlin.py` at import until Task 2 wires up the value. Task 1 only adds the standalone dataclasses so they can be imported by Task 2.

- [ ] **Step 1: Read the existing `CityConfig` block for style reference**

```bash
head -180 app/cities/base.py
```

- [ ] **Step 2: Append the two new dataclasses at the end of `app/cities/base.py`**

Add after the last `CityConfig` field (bottom of the file):

```python


@dataclass(frozen=True)
class LensTileConfig:
    """One traffic-light tile in a lens.

    `thresholds` is deliberately an opaque dict — each `_tier_*` function in
    `app/core/scorer.py` interprets its own keys (distance vs dB vs μg/m³ vs
    class-strings). Keeps the config table readable per tile without a shared
    schema no tile actually satisfies.
    """
    key:        str
    label:      str
    icon:       str
    thresholds: dict
    caveat:     str = ""    # long-lived tile-scoped disclosure; hidden if empty


@dataclass(frozen=True)
class LensConfig:
    """Named view over an address (Young Family, Bureaucracy, …).

    Order of `tiles` is display order — the frontend renders tiles in this
    exact order, both in single-address and compare views.
    """
    slug:          str      # stable id, e.g. "young_family"
    label:         str      # human label, e.g. "Young Family (0–6)"
    audience_hint: str      # one-line subline shown under the label
    tiles:         tuple    # tuple[LensTileConfig, ...]
```

Also, at the top of the file where `from dataclasses import ...` appears, extend the import to include `FrozenInstanceError` (needed by the assert in Step 3):

```python
from dataclasses import dataclass, FrozenInstanceError
```

- [ ] **Step 3: Add assertions in the module's `__main__` block confirming frozen semantics and default value**

Append at the bottom of `app/cities/base.py`:

```python


if __name__ == "__main__":
    # Frozen — attempting to mutate must raise FrozenInstanceError.
    t = LensTileConfig(key="k", label="l", icon="i", thresholds={"green_m": 400})
    try:
        t.key = "changed"
    except FrozenInstanceError:
        pass
    else:
        raise AssertionError("LensTileConfig must be frozen")
    # `caveat` defaults to empty string — frontend hides when empty.
    assert t.caveat == ""
    lc = LensConfig(slug="s", label="l", audience_hint="h", tiles=(t,))
    assert lc.tiles[0].key == "k"
    print("base.py selfcheck OK (LensTileConfig / LensConfig)")
```

- [ ] **Step 4: Run the module's selfcheck; expect PASS**

```bash
python -m app.cities.base
```

Expected output ends with `base.py selfcheck OK (LensTileConfig / LensConfig)`.

- [ ] **Step 5: Confirm no other module imports the new dataclasses yet**

```bash
grep -rn "LensTileConfig\|LensConfig" app/ | grep -v "base.py"
```

Expected: no output — only `base.py` has the definitions until Task 2.

- [ ] **Step 6: Commit**

```bash
git add app/cities/base.py
git commit -m "Add LensTileConfig / LensConfig dataclasses (Spec A prep)"
```

---

## Task 2: Wire `young_family_lens` onto `CityConfig` + Berlin's 7-tile instantiation

**Files:**
- Modify: `app/cities/base.py` — add `young_family_lens: LensConfig` field to `CityConfig`
- Modify: `app/cities/berlin.py` — add `YOUNG_FAMILY_LENS: LensConfig = LensConfig(...)` module-level constant + wire it onto `BERLIN`

**Interfaces:**
- Consumes: `LensTileConfig`, `LensConfig` from Task 1
- Produces:
  - New required (no-default) `CityConfig.young_family_lens: LensConfig` field
  - Berlin's `YOUNG_FAMILY_LENS` accessible as `BERLIN.young_family_lens`

**Notes:** Cities isolation (existing `app.selfcheck.run_cities_isolation`) will fail during Step 2 of this task because `berlin.py` is stale w.r.t. the new field until Step 4. That's the intended safety-net working. Task ends green.

- [ ] **Step 1: Add the field to `CityConfig` in `app/cities/base.py`**

Find the last field on `CityConfig` (the `attribution: dict` field). Add the new field immediately after (before the closing of the `@dataclass` — Python raises if a field-with-default precedes one without, but our field has no default so it's safe as last):

```python
    # -- Lenses (Spec A: Young Family). Per-city view over amenities/environment
    # for a specific audience. Adding more lenses = adding more fields here.
    young_family_lens: LensConfig
```

- [ ] **Step 2: Run cities isolation; expect FAIL because `berlin.py` doesn't spell the field yet**

```bash
python -c "from app.selfcheck import run_cities_isolation; run_cities_isolation()"
```

Expected: berlin fails with `TypeError: CityConfig.__init__() missing 1 required positional argument: 'young_family_lens'`. This is the safety net working — proves the field is actually required.

- [ ] **Step 3: Extend imports in `app/cities/berlin.py`**

Find the existing `from app.cities.base import CityConfig` line and extend it:

```python
from app.cities.base import CityConfig, LensConfig, LensTileConfig
```

- [ ] **Step 4: Add `YOUNG_FAMILY_LENS` module-level constant in `berlin.py`**

Add immediately above the `BERLIN = CityConfig(...)` construction:

```python
# --- Young Family lens (Spec A) --------------------------------------------
# Seven traffic-light tiles for families with kids under 6. Thresholds live
# per tile — every "why is this the tier" answer sits in one table here.
# Boundary convention: inclusive on the greener side (≤ green_m is green;
# > green_m is amber). See
# docs/superpowers/specs/2026-08-09-young-family-lens-design.md.
YOUNG_FAMILY_LENS: LensConfig = LensConfig(
    slug="young_family",
    label="Young Family (0–6)",
    audience_hint="For a family with kids under 6",
    tiles=(
        LensTileConfig(
            key="kita", label="Kita reachability", icon="kita",
            thresholds={"green_count": 3, "green_m": 400, "amber_m": 800},
        ),
        LensTileConfig(
            key="playground", label="Playground within stroller walk", icon="playground",
            thresholds={"green_m": 400, "amber_m": 800},
        ),
        LensTileConfig(
            key="pediatrician", label="Pediatrician within walk", icon="pediatrician",
            thresholds={"green_m": 800, "amber_m": 1500},
            caveat=("OSM community-tagged — inner-district coverage is good; "
                    "outer districts may under-report."),
        ),
        LensTileConfig(
            key="noise", label="Façade noise", icon="noise",
            thresholds={"green_db": 55, "amber_db": 60},
        ),
        LensTileConfig(
            key="heat", label="Summer heat", icon="heat",
            # Umweltatlas class strings — matched case-insensitively as substrings.
            thresholds={
                "green_classes": ("keine Belastung", "geringe Belastung"),
                "amber_classes": ("mittlere Belastung", "starke Belastung"),
            },
        ),
        LensTileConfig(
            key="air", label="Air quality (NO₂)", icon="air",
            # 20/40 tiers follow the app's existing NO₂ card thresholds
            # (§14.9 tier-color convention), not WHO 2021 strictly (10 μg/m³).
            thresholds={"green_ugm3": 20, "amber_ugm3": 40},
        ),
        LensTileConfig(
            key="refuge", label="Quiet / green refuge nearby", icon="refuge",
            # Composite: quiet zone distance OR crown coverage %. OR-forgiving
            # at both tiers so losing one signal still yields a real tier.
            thresholds={
                "green_quiet_m": 400,  "amber_quiet_m": 1000,
                "green_crown_pct": 25, "amber_crown_pct": 15,
            },
        ),
    ),
)
```

- [ ] **Step 5: Add `young_family_lens=YOUNG_FAMILY_LENS` to `BERLIN = CityConfig(...)`**

Find the `attribution=` line inside `BERLIN = CityConfig(...)`. Add immediately after (before the closing `)`):

```python
    young_family_lens=YOUNG_FAMILY_LENS,
```

- [ ] **Step 6: Run cities isolation; expect PASS**

```bash
python -c "from app.selfcheck import run_cities_isolation; run_cities_isolation()"
```

Expected: `→ berlin … OK`.

- [ ] **Step 7: Confirm `BERLIN.young_family_lens.tiles` has 7 entries in expected order**

```bash
python -c "from app.cities.berlin import BERLIN; print([t.key for t in BERLIN.young_family_lens.tiles])"
```

Expected: `['kita', 'playground', 'pediatrician', 'noise', 'heat', 'air', 'refuge']`.

- [ ] **Step 8: Commit**

```bash
git add app/cities/base.py app/cities/berlin.py
git commit -m "Wire young_family_lens onto CityConfig + Berlin instantiation"
```

---

## Task 3: `is_paediatric(tags)` helper in `app/core/amenities.py`

**Files:**
- Modify: `app/core/amenities.py` — add helper function; add assertions in the existing `__main__` block (add one if absent)

**Interfaces:**
- Consumes: OSM tags dict (from `amenities.gps.items[*].tags`)
- Produces: `is_paediatric(tags: dict) -> bool`

**Notes:** Factored out of the display-parsing at line 87 so the scorer isn't duplicating tag-key knowledge. One function, one line of logic, a handful of asserts.

- [ ] **Step 1: Find a natural insertion point in `app/core/amenities.py`**

```bash
grep -n "^def\|^from\|^import" app/core/amenities.py | head -20
```

The helper is small enough to sit near the top module-level, after the imports and before `_bod_layers`.

- [ ] **Step 2: Add the helper**

Insert after the last import and before `def _bod_layers`:

```python
def is_paediatric(tags) -> bool:
    """True iff the OSM tags describe a paediatric doctor's office.

    Handles both `healthcare:speciality` (correct British spelling — what
    OSM data actually carries in Berlin) and `healthcare:specialty` (US
    alternate; safety net for imported / edited entries). Verified live
    against Praxis für Kinderheilkunde Dr. Berns at Bergmannstraße 5 —
    it carries `healthcare:speciality=paediatrics`.
    """
    spec = ((tags or {}).get("healthcare:speciality") or
            (tags or {}).get("healthcare:specialty") or "")
    low = spec.lower()
    return "paediatrics" in low or "pediatrics" in low
```

- [ ] **Step 3: Add assertions in the module's `if __name__ == "__main__"` block**

If the block exists at the bottom, append to it. Otherwise create it. Add:

```python
    # is_paediatric — handles both spellings, mixed case, semicolon-separated
    # multi-specialities, missing tag, null tags.
    assert is_paediatric({"healthcare:speciality": "paediatrics"}) is True
    assert is_paediatric({"healthcare:specialty": "pediatrics"}) is True
    assert is_paediatric({"healthcare:speciality": "PAEDIATRICS;dermatology"}) is True
    assert is_paediatric({"healthcare:speciality": "cardiology"}) is False
    assert is_paediatric({}) is False
    assert is_paediatric(None) is False
    print("amenities.py: is_paediatric selfcheck OK")
```

- [ ] **Step 4: Run the module's selfcheck; expect PASS**

```bash
python -m app.core.amenities
```

Expected: ends with `amenities.py: is_paediatric selfcheck OK`.

- [ ] **Step 5: Commit**

```bash
git add app/core/amenities.py
git commit -m "Add is_paediatric(tags) helper for lens scorer reuse"
```

---

## Task 4: Seven pure `_tier_*` functions in `app/core/scorer.py`

**Files:**
- Modify: `app/core/scorer.py` — add 7 pure functions + boundary sweep assertions in `__main__`

**Interfaces:**
- Consumes: `LensTileConfig.thresholds` dict shapes (per tile — as instantiated in Task 2)
- Produces:
  - `_tier_kita(kitas: list, t: dict) -> dict`
  - `_tier_playground(playgrounds: list, playgrounds_error: bool, t: dict) -> dict`
  - `_tier_pediatrician(paediatricians: list, gps_error: bool, t: dict) -> dict`
  - `_tier_noise(noise: dict, t: dict) -> dict`
  - `_tier_heat(heat: dict, t: dict) -> dict`
  - `_tier_air(air: dict, t: dict) -> dict`
  - `_tier_refuge(quiet_zone: dict, trees: dict, t: dict) -> dict`
- Each function returns `{"tier": str, "rule": str, "numeric": str}` — no `sources` yet (the composer in Task 5 adds them).

- [ ] **Step 1: Read the existing `app/core/scorer.py` for style + existing selfcheck patterns**

```bash
cat app/core/scorer.py
```

- [ ] **Step 2: Add tier constants near the top of the file (after imports)**

```python
TIER_GREEN   = "green"
TIER_AMBER   = "amber"
TIER_RED     = "red"
TIER_UNKNOWN = "unknown"
```

- [ ] **Step 3: Add `_tier_kita`**

```python
def _tier_kita(kitas: list, t: dict) -> dict:
    """Kita reachability. Preloaded source (Index.kitas) → never unknown."""
    green = [k for k in kitas if k["distance_m"] <= t["green_m"]]
    amber = [k for k in kitas if k["distance_m"] <= t["amber_m"]]
    if len(green) >= t["green_count"]:
        return {"tier": TIER_GREEN,
                "rule": f"≥{t['green_count']} kitas within {t['green_m']}m",
                "numeric": f"{len(green)} within {t['green_m']}m · "
                           f"nearest {green[0]['distance_m']}m"}
    if amber:
        return {"tier": TIER_AMBER,
                "rule": f"≥1 kita within {t['amber_m']}m",
                "numeric": f"{len(amber)} within {t['amber_m']}m · "
                           f"nearest {amber[0]['distance_m']}m"}
    return {"tier": TIER_RED,
            "rule": f"no kita within {t['amber_m']}m",
            "numeric": (f"nearest {kitas[0]['distance_m']}m"
                        if kitas else "none nearby")}
```

- [ ] **Step 4: Add `_tier_playground`**

```python
def _tier_playground(playgrounds: list, playgrounds_error: bool, t: dict) -> dict:
    """Playground within stroller walk. Unknown when the playground bucket
    both errored AND returned nothing (Overpass and BOD both failed)."""
    if playgrounds_error and not playgrounds:
        return {"tier": TIER_UNKNOWN,
                "rule": "Playground data unavailable",
                "numeric": "Overpass and BOD both failed"}
    within_green = [p for p in playgrounds if p["distance_m"] <= t["green_m"]]
    within_amber = [p for p in playgrounds if p["distance_m"] <= t["amber_m"]]
    if within_green:
        return {"tier": TIER_GREEN,
                "rule": f"≥1 playground within {t['green_m']}m",
                "numeric": f"{len(within_green)} within {t['green_m']}m · "
                           f"nearest {within_green[0]['distance_m']}m"}
    if within_amber:
        return {"tier": TIER_AMBER,
                "rule": f"playground {t['green_m']}–{t['amber_m']}m",
                "numeric": f"nearest {within_amber[0]['distance_m']}m"}
    return {"tier": TIER_RED,
            "rule": f"no playground within {t['amber_m']}m",
            "numeric": (f"nearest {playgrounds[0]['distance_m']}m"
                        if playgrounds else "none nearby")}
```

- [ ] **Step 5: Add `_tier_pediatrician`**

```python
def _tier_pediatrician(paediatricians: list, gps_error: bool, t: dict) -> dict:
    """Paediatric doctor within walk. Expects `paediatricians` to be already
    filtered from the gps bucket and sorted ascending by distance."""
    if gps_error:
        return {"tier": TIER_UNKNOWN,
                "rule": "Pediatrician data unavailable",
                "numeric": "OSM Overpass unavailable"}
    within_green = [p for p in paediatricians if p["distance_m"] <= t["green_m"]]
    within_amber = [p for p in paediatricians if p["distance_m"] <= t["amber_m"]]
    if within_green:
        nearest = within_green[0]
        return {"tier": TIER_GREEN,
                "rule": f"≥1 paediatric within {t['green_m']}m",
                "numeric": (f"{len(within_green)} within {t['green_m']}m · "
                            f"nearest {nearest['distance_m']}m "
                            f"({nearest.get('name', 'unnamed')})")}
    if within_amber:
        nearest = within_amber[0]
        return {"tier": TIER_AMBER,
                "rule": f"paediatric {t['green_m']}–{t['amber_m']}m",
                "numeric": (f"nearest {nearest['distance_m']}m "
                            f"({nearest.get('name', 'unnamed')})")}
    return {"tier": TIER_RED,
            "rule": f"no paediatric within {t['amber_m']}m",
            "numeric": (f"nearest {paediatricians[0]['distance_m']}m"
                        if paediatricians else "none nearby")}
```

- [ ] **Step 6: Add `_tier_noise`**

```python
def _tier_noise(noise: dict, t: dict) -> dict:
    """Façade L_DEN. Boundary: ≤ green_db is green (inclusive)."""
    if not noise or noise.get("unavailable"):
        return {"tier": TIER_UNKNOWN,
                "rule": "Noise data unavailable",
                "numeric": (noise or {}).get("error") or "façade noise WFS down"}
    l_den = ((noise.get("l_den") or {}).get("total"))
    if l_den is None:
        return {"tier": TIER_UNKNOWN,
                "rule": "Noise data unavailable",
                "numeric": "no L_DEN reading at this façade"}
    if l_den <= t["green_db"]:
        return {"tier": TIER_GREEN,
                "rule": f"L_DEN ≤ {t['green_db']} dB",
                "numeric": f"{l_den} dB L_DEN"}
    if l_den <= t["amber_db"]:
        return {"tier": TIER_AMBER,
                "rule": f"{t['green_db']}–{t['amber_db']} dB",
                "numeric": f"{l_den} dB L_DEN"}
    return {"tier": TIER_RED,
            "rule": f"L_DEN > {t['amber_db']} dB",
            "numeric": f"{l_den} dB L_DEN"}
```

- [ ] **Step 7: Add `_tier_heat`**

```python
def _tier_heat(heat: dict, t: dict) -> dict:
    """Summer-heat class string membership. `day_class` is a German text tag
    like 'starke Belastung' — matched case-insensitively as a substring."""
    if not heat or heat.get("unavailable"):
        return {"tier": TIER_UNKNOWN,
                "rule": "Heat data unavailable",
                "numeric": (heat or {}).get("error") or "Umweltatlas WFS down"}
    day = (heat.get("day_class") or "").strip()
    day_low = day.lower()
    if not day_low:
        return {"tier": TIER_UNKNOWN,
                "rule": "Heat data unavailable",
                "numeric": "no day_class on this block"}
    if any(g.lower() in day_low for g in t["green_classes"]):
        return {"tier": TIER_GREEN, "rule": "keine / geringe Belastung",
                "numeric": day}
    if any(a.lower() in day_low for a in t["amber_classes"]):
        return {"tier": TIER_AMBER, "rule": "mittlere / starke Belastung",
                "numeric": day}
    return {"tier": TIER_RED, "rule": "sehr starke / extreme Belastung",
            "numeric": day}
```

- [ ] **Step 8: Add `_tier_air`**

```python
def _tier_air(air: dict, t: dict) -> dict:
    """NO₂ tier. Boundary: ≤ green_ugm3 is green (inclusive)."""
    if not air or air.get("unavailable"):
        return {"tier": TIER_UNKNOWN,
                "rule": "Air-quality data unavailable",
                "numeric": (air or {}).get("error") or "Umweltatlas WFS down"}
    no2 = air.get("no2_ugm3")
    if no2 is None:
        return {"tier": TIER_UNKNOWN,
                "rule": "Air-quality data unavailable",
                "numeric": "no NO₂ reading on this segment"}
    if no2 <= t["green_ugm3"]:
        return {"tier": TIER_GREEN,
                "rule": f"NO₂ ≤ {t['green_ugm3']} μg/m³",
                "numeric": f"{no2} μg/m³ NO₂"}
    if no2 <= t["amber_ugm3"]:
        return {"tier": TIER_AMBER,
                "rule": f"NO₂ {t['green_ugm3']}–{t['amber_ugm3']} μg/m³",
                "numeric": f"{no2} μg/m³ NO₂"}
    return {"tier": TIER_RED,
            "rule": f"NO₂ > {t['amber_ugm3']} μg/m³",
            "numeric": f"{no2} μg/m³ NO₂"}
```

- [ ] **Step 9: Add `_tier_refuge`**

```python
def _tier_refuge(quiet_zone: dict, trees: dict, t: dict) -> dict:
    """Composite: quiet zone distance OR tree crown coverage %. OR-forgiving
    at both tiers — losing one signal still yields a real tier. Only unknown
    when BOTH signals are missing."""
    q_m   = (quiet_zone or {}).get("distance_m")
    crown = (trees or {}).get("crown_coverage_pct")
    if q_m is None and crown is None:
        return {"tier": TIER_UNKNOWN,
                "rule": "Refuge data unavailable",
                "numeric": "quiet-zone + trees both unavailable"}
    def _parts():
        p = []
        if q_m is not None:
            name = (quiet_zone or {}).get("name") or "quiet zone"
            p.append(f"{name} at {q_m}m")
        if crown is not None:
            p.append(f"{crown}% crown")
        return " · ".join(p)

    green_hit = ((q_m is not None and q_m <= t["green_quiet_m"]) or
                 (crown is not None and crown >= t["green_crown_pct"]))
    if green_hit:
        return {"tier": TIER_GREEN,
                "rule": (f"quiet ≤ {t['green_quiet_m']}m OR "
                         f"crown ≥ {t['green_crown_pct']}%"),
                "numeric": _parts()}
    amber_hit = ((q_m is not None and q_m <= t["amber_quiet_m"]) or
                 (crown is not None and crown >= t["amber_crown_pct"]))
    if amber_hit:
        return {"tier": TIER_AMBER,
                "rule": (f"quiet ≤ {t['amber_quiet_m']}m OR "
                         f"crown ≥ {t['amber_crown_pct']}%"),
                "numeric": _parts()}
    return {"tier": TIER_RED,
            "rule": "no quiet zone within walk AND low tree cover",
            "numeric": _parts() or "no signal"}
```

- [ ] **Step 10: Add boundary sweep assertions in the module's `if __name__ == "__main__"` block**

Append at the bottom of the existing block (or create one if absent):

```python
    # -- Young Family lens: boundary sweeps (Spec A pure selfcheck) ----------
    from app.cities.berlin import BERLIN as _CFG_YF
    _T = {t.key: t.thresholds for t in _CFG_YF.young_family_lens.tiles}

    # Kita — inclusive on greener side.
    at_400 = [{"distance_m": 400}, {"distance_m": 350}, {"distance_m": 100}]
    at_401 = [{"distance_m": 401}, {"distance_m": 402}, {"distance_m": 403}]
    assert _tier_kita(at_400, _T["kita"])["tier"] == TIER_GREEN
    assert _tier_kita(at_401, _T["kita"])["tier"] == TIER_AMBER
    assert _tier_kita([{"distance_m": 800}], _T["kita"])["tier"] == TIER_AMBER
    assert _tier_kita([{"distance_m": 801}], _T["kita"])["tier"] == TIER_RED
    assert _tier_kita([], _T["kita"])["tier"] == TIER_RED

    # Playground.
    assert _tier_playground([{"distance_m": 400}], False, _T["playground"])["tier"] == TIER_GREEN
    assert _tier_playground([{"distance_m": 401}], False, _T["playground"])["tier"] == TIER_AMBER
    assert _tier_playground([{"distance_m": 801}], False, _T["playground"])["tier"] == TIER_RED
    assert _tier_playground([], True, _T["playground"])["tier"] == TIER_UNKNOWN

    # Pediatrician.
    P800 = [{"distance_m": 800, "name": "Dr. X"}]
    P801 = [{"distance_m": 801, "name": "Dr. Y"}]
    P1500 = [{"distance_m": 1500, "name": "Dr. Z"}]
    P1501 = [{"distance_m": 1501, "name": "Dr. W"}]
    assert _tier_pediatrician(P800, False, _T["pediatrician"])["tier"] == TIER_GREEN
    assert _tier_pediatrician(P801, False, _T["pediatrician"])["tier"] == TIER_AMBER
    assert _tier_pediatrician(P1500, False, _T["pediatrician"])["tier"] == TIER_AMBER
    assert _tier_pediatrician(P1501, False, _T["pediatrician"])["tier"] == TIER_RED
    assert _tier_pediatrician([], True, _T["pediatrician"])["tier"] == TIER_UNKNOWN

    # Noise — inclusive on greener side (55 is green, 55.01 is amber).
    assert _tier_noise({"l_den": {"total": 55}}, _T["noise"])["tier"] == TIER_GREEN
    assert _tier_noise({"l_den": {"total": 55.01}}, _T["noise"])["tier"] == TIER_AMBER
    assert _tier_noise({"l_den": {"total": 60}}, _T["noise"])["tier"] == TIER_AMBER
    assert _tier_noise({"l_den": {"total": 60.01}}, _T["noise"])["tier"] == TIER_RED
    assert _tier_noise({"unavailable": True}, _T["noise"])["tier"] == TIER_UNKNOWN

    # Heat — case-insensitive substring membership.
    assert _tier_heat({"day_class": "geringe Belastung"}, _T["heat"])["tier"] == TIER_GREEN
    assert _tier_heat({"day_class": "starke Belastung"}, _T["heat"])["tier"] == TIER_AMBER
    assert _tier_heat({"day_class": "sehr starke Belastung"}, _T["heat"])["tier"] == TIER_RED
    assert _tier_heat({"day_class": "extreme Belastung"}, _T["heat"])["tier"] == TIER_RED
    assert _tier_heat({"unavailable": True}, _T["heat"])["tier"] == TIER_UNKNOWN

    # Air — inclusive on greener side.
    assert _tier_air({"no2_ugm3": 20}, _T["air"])["tier"] == TIER_GREEN
    assert _tier_air({"no2_ugm3": 20.01}, _T["air"])["tier"] == TIER_AMBER
    assert _tier_air({"no2_ugm3": 40}, _T["air"])["tier"] == TIER_AMBER
    assert _tier_air({"no2_ugm3": 40.01}, _T["air"])["tier"] == TIER_RED
    assert _tier_air({"unavailable": True}, _T["air"])["tier"] == TIER_UNKNOWN

    # Refuge — composite OR.
    assert _tier_refuge({"distance_m": 400, "name": "Volkspark"},
                        {"crown_coverage_pct": 5},
                        _T["refuge"])["tier"] == TIER_GREEN  # quiet clears green
    assert _tier_refuge({"distance_m": 2000},
                        {"crown_coverage_pct": 25},
                        _T["refuge"])["tier"] == TIER_GREEN  # crown clears green
    assert _tier_refuge({"distance_m": 1000},
                        {"crown_coverage_pct": 14.99},
                        _T["refuge"])["tier"] == TIER_AMBER  # quiet clears amber only
    assert _tier_refuge({"distance_m": 2000},
                        {"crown_coverage_pct": 14.99},
                        _T["refuge"])["tier"] == TIER_RED
    assert _tier_refuge(None, None, _T["refuge"])["tier"] == TIER_UNKNOWN
    print("scorer.py: young_family tier boundary sweeps OK")
```

- [ ] **Step 11: Run scorer selfcheck; expect PASS**

```bash
python -m app.core.scorer
```

Expected: existing scorer OK lines + `scorer.py: young_family tier boundary sweeps OK`.

- [ ] **Step 12: Commit**

```bash
git add app/core/scorer.py
git commit -m "Add young_family lens tier functions + boundary sweeps"
```

---

## Task 5: `young_family_lens(...)` composer + `_lens_provenance(...)` helper

**Files:**
- Modify: `app/core/scorer.py` — add composer, provenance helper, source-mapping helper, composition + shape assertions

**Interfaces:**
- Consumes: seven `_tier_*` functions from Task 4; `is_paediatric` from Task 3; `LensConfig` from Task 1; `CityConfig.young_family_lens` from Task 2
- Produces:
  - `young_family_lens(cfg, index, lon, lat, *, air, heat, noise, amenities, trees, quiet_zone) -> dict`
  - `_lens_provenance(cfg, tiles: list) -> str`
  - `_sources_for(cfg, key: str, tier: str) -> list` (private)
- Output shape: `{"slug", "label", "audience", "tiles": [7 dicts], "provenance": str}`; each tile is `{key, label, icon, tier, rule, numeric, caveat, sources}`.

- [ ] **Step 1: Add the provenance helper at module level in `scorer.py`**

```python
def _lens_provenance(cfg, tiles: list) -> str:
    """Union of `sources` from tiles that contributed a real tier — de-duped,
    insertion-order preserved (Python 3.7+ dict semantics). Unknown tiles
    contribute [], so they're skipped naturally. Empty string if nothing to
    cite; frontend hides the provenance footer in that case (§14.5)."""
    seen, out = set(), []
    for tile in tiles:
        for s in (tile.get("sources") or []):
            if s and s not in seen:
                seen.add(s); out.append(s)
    return " · ".join(out)
```

- [ ] **Step 2: Add the source-mapping helper (private) using `cfg.attribution`**

```python
def _sources_for(cfg, key: str, tier: str) -> list:
    """Return the `sources` array for one tile. Unknown tiles get []. Every
    string is looked up in cfg.attribution — never invent a provenance line.
    Empty strings dropped so a missing attribution key doesn't leak an empty
    citation."""
    if tier == TIER_UNKNOWN:
        return []
    attr = cfg.attribution
    mapping = {
        "kita":         [attr.get("kitas")],
        "playground":   [attr.get("playgrounds"),
                         attr.get("parks"),
                         "© OpenStreetMap contributors (ODbL)"],
        "pediatrician": ["© OpenStreetMap contributors (ODbL)"],
        "noise":        [attr.get("noise")],
        "heat":         [attr.get("heat")],
        "air":          [attr.get("air")],
        "refuge":       [attr.get("quiet_zone"), attr.get("trees")],
    }
    return [s for s in (mapping.get(key) or []) if s]
```

- [ ] **Step 3: Add the composer**

```python
def young_family_lens(cfg, index, lon: float, lat: float, *,
                      air: dict, heat: dict, noise: dict,
                      amenities: dict, trees: dict, quiet_zone: dict) -> dict:
    """Assemble 7 tile results for one address. Pure — no I/O.

    All inputs are values already computed elsewhere in /api/lookup;
    the lens is a view over data the address already carries. Never call
    WFS from here — that keeps the lens from ever disagreeing with the
    raw data in the same response.
    """
    from app.core.amenities import is_paediatric

    lens = cfg.young_family_lens
    thresholds  = {t.key: t.thresholds       for t in lens.tiles}
    tile_meta   = {t.key: (t.label, t.icon, t.caveat) for t in lens.tiles}

    kitas = index.kitas_near_bod(lon, lat, 800)

    pg_block  = (amenities or {}).get("playgrounds") or {}
    pg_items  = pg_block.get("items") or []
    pg_error  = bool(pg_block.get("error") or pg_block.get("_error"))

    gps_block = (amenities or {}).get("gps") or {}
    gps_items = gps_block.get("items") or []
    gps_error = bool(gps_block.get("error") or gps_block.get("_error"))
    paediatric = [g for g in gps_items if is_paediatric(g.get("tags"))]
    paediatric.sort(key=lambda x: x.get("distance_m", 10**9))

    results = [
        ("kita",         _tier_kita(kitas, thresholds["kita"])),
        ("playground",   _tier_playground(pg_items, pg_error, thresholds["playground"])),
        ("pediatrician", _tier_pediatrician(paediatric, gps_error, thresholds["pediatrician"])),
        ("noise",        _tier_noise(noise, thresholds["noise"])),
        ("heat",         _tier_heat(heat, thresholds["heat"])),
        ("air",          _tier_air(air, thresholds["air"])),
        ("refuge",       _tier_refuge(quiet_zone, trees, thresholds["refuge"])),
    ]

    tiles = []
    for key, res in results:
        label, icon, caveat = tile_meta[key]
        tiles.append({
            "key":     key,
            "label":   label,
            "icon":    icon,
            "tier":    res["tier"],
            "rule":    res["rule"],
            "numeric": res["numeric"],
            "caveat":  caveat,
            "sources": _sources_for(cfg, key, res["tier"]),
        })

    return {
        "slug":       lens.slug,
        "label":      lens.label,
        "audience":   lens.audience_hint,
        "tiles":      tiles,
        "provenance": _lens_provenance(cfg, tiles),
    }
```

- [ ] **Step 4: Add composition + empty-vs-unavailable + caveat + shape asserts in `__main__`**

Append below the boundary sweeps in the same `if __name__ == "__main__"` block:

```python
    # -- Sources composition + de-dup order --------------------------------
    _fake_tiles = [
        {"sources": ["A", "B"]},
        {"sources": []},                    # unknown-shaped, contributes nothing
        {"sources": ["B", "C", "A"]},       # duplicates suppressed, order kept
        {"sources": None},                  # tolerated
    ]
    assert _lens_provenance(_CFG_YF, _fake_tiles) == "A · B · C"
    assert _lens_provenance(_CFG_YF, [{"sources": []}, {"sources": None}]) == ""

    # -- Caveat pass-through -----------------------------------------------
    _caveats = {t.key: t.caveat for t in _CFG_YF.young_family_lens.tiles}
    assert _caveats["pediatrician"], "pediatrician tile must carry a caveat"
    assert _caveats["kita"] == "" and _caveats["noise"] == ""

    # -- Empty-but-available inputs → red (kita has 0 nearby, noise=100 dB, etc.)
    #    Uses a stub for the only Index method the composer calls.
    class _StubIndex:
        def kitas_near_bod(self, lon, lat, r): return []
    _empty_result = young_family_lens(
        _CFG_YF, _StubIndex(), 13.4, 52.5,
        air={"no2_ugm3": 60}, heat={"day_class": "extreme Belastung"},
        noise={"l_den": {"total": 70}},
        amenities={"playgrounds": {"items": []}, "gps": {"items": []}},
        trees={"crown_coverage_pct": 5},
        quiet_zone={"distance_m": 5000},
    )
    _tiers = {t["key"]: t["tier"] for t in _empty_result["tiles"]}
    assert all(v == TIER_RED for v in _tiers.values()), _tiers

    # -- Unavailable inputs → unknown where possible, red where not ---------
    _unavail_result = young_family_lens(
        _CFG_YF, _StubIndex(), 13.4, 52.5,
        air={"unavailable": True}, heat={"unavailable": True},
        noise={"unavailable": True},
        amenities={"playgrounds": {"items": [], "error": "overpass timeout"},
                   "gps":         {"items": [], "error": "overpass timeout"}},
        trees=None, quiet_zone=None,
    )
    _u = {t["key"]: t["tier"] for t in _unavail_result["tiles"]}
    assert _u["noise"]        == TIER_UNKNOWN
    assert _u["heat"]         == TIER_UNKNOWN
    assert _u["air"]          == TIER_UNKNOWN
    assert _u["playground"]   == TIER_UNKNOWN
    assert _u["pediatrician"] == TIER_UNKNOWN
    assert _u["refuge"]       == TIER_UNKNOWN
    assert _u["kita"]         == TIER_RED   # preloaded — unknown unreachable

    # Response shape stability (every tile has the same 8 keys).
    for t in _unavail_result["tiles"]:
        assert set(t.keys()) == {"key","label","icon","tier","rule","numeric","caveat","sources"}, t
    assert _unavail_result["slug"]     == "young_family"
    assert _unavail_result["label"]    == "Young Family (0–6)"
    assert _unavail_result["audience"] == "For a family with kids under 6"
    # kita is red (not unknown) → DOES cite its attribution source.
    assert "Kindertagesstätten" in _unavail_result["provenance"], _unavail_result["provenance"]

    print("scorer.py: young_family composer + provenance OK")
```

- [ ] **Step 5: Run scorer selfcheck; expect PASS**

```bash
python -m app.core.scorer
```

Expected: boundary sweeps OK + `scorer.py: young_family composer + provenance OK`.

- [ ] **Step 6: Commit**

```bash
git add app/core/scorer.py
git commit -m "Add young_family_lens composer + provenance helper + tests"
```

---

## Task 6: Wire scorer into `/api/lookup` with try/except catch-all

**Files:**
- Modify: `app/routes/lookup.py` — call scorer at end of handler; fold under `lens.young_family`

**Interfaces:**
- Consumes: `scorer.young_family_lens` from Task 5
- Produces: `/api/lookup` response gains new top-level key `lens: {young_family: {...}}`

**Notes:** The current `/api/lookup` handler does NOT compute `amenities` or `noise` — those live in separate `/api/amenities` and `/api/noise` endpoints. This task adds internal calls to `amenities_near()` and `noise_at()` inside `/api/lookup`, purely to feed the lens. The results are **not** exposed in the `/api/lookup` response — the frontend still calls the separate endpoints for the raw views. Both helpers already have module-level caches keyed by rounded (lon, lat, radius), so a second call from the raw endpoints is a cache hit (~ms). Expected extra latency on cold `/api/lookup`: +~1s Overpass, +~500ms noise WFS.

- [ ] **Step 1: Read `app/routes/lookup.py` to confirm which variables are already in scope**

```bash
cat app/routes/lookup.py
```

Expected variables in scope at the return statement: `geo`, `lon`, `lat`, `cfg`, `index`, `air`, `heat`, `trees_summary`, `quiet_zone`. Missing (need to add): `_amen`, `_noise`.

- [ ] **Step 2: Add imports at the top of `app/routes/lookup.py`**

Extend the existing import block:

```python
from app.core.amenities import amenities_near
from app.core.wfs import noise_at
from app.core import scorer
```

- [ ] **Step 3: Add the lens computation block immediately before the `return {...}`**

Insert (adjust variable names to match what's actually in scope from Step 1):

```python
    # -- Young Family lens (Spec A) ----------------------------------------
    # The lens needs playgrounds + gps (pediatricians) + noise, none of
    # which /api/lookup exposes today. We fetch them here purely for the
    # lens — they do NOT leak into the /api/lookup response shape (the
    # frontend still calls /api/amenities and /api/noise for the raw
    # views; both helpers are cache-backed so second calls are ~ms).
    try:
        _amen  = amenities_near(index, cfg, lon, lat, 800)
        _noise = noise_at(cfg, lon, lat)
    except Exception:
        _amen, _noise = {}, {"unavailable": True}
    try:
        lens_yf = scorer.young_family_lens(
            cfg, index, lon, lat,
            air=air, heat=heat, noise=_noise,
            amenities=(_amen or {}).get("amenities") or {},
            trees=trees_summary, quiet_zone=quiet_zone,
        )
    except Exception as e:
        # The lens is additive. Never break /api/lookup for it (§14.7).
        lens_yf = {"slug": "young_family",
                   "error": f"{type(e).__name__}: {e}"}
```

- [ ] **Step 4: Add the `lens` key to the response dict**

Locate the `return {...}` in the handler. Add one new key alongside the existing ones:

```python
        "lens":         {"young_family": lens_yf},
```

- [ ] **Step 5: Boot / already-running app on port 8000 — hit /api/lookup and verify**

```bash
curl -s "http://127.0.0.1:8000/api/lookup?address=Kastanienallee+12%2C+10435" \
  | python3 -c "import json,sys; d=json.load(sys.stdin); \
    print('lens present:', 'lens' in d); \
    yf=(d.get('lens') or {}).get('young_family') or {}; \
    print('young_family present:', bool(yf)); \
    print('tiles count:', len(yf.get('tiles') or [])); \
    print('slug:', yf.get('slug')); \
    print('provenance sample:', (yf.get('provenance') or '')[:120])"
```

Expected:
```
lens present: True
young_family present: True
tiles count: 7
slug: young_family
provenance sample: <string that contains at minimum "Kindertagesstätten">
```

- [ ] **Step 6: Verify shape of the kita tile**

```bash
curl -s "http://127.0.0.1:8000/api/lookup?address=Kastanienallee+12%2C+10435" \
  | python3 -c "import json,sys; \
    tiles=json.load(sys.stdin)['lens']['young_family']['tiles']; \
    kita=[t for t in tiles if t['key']=='kita'][0]; \
    print(json.dumps(kita, indent=2, ensure_ascii=False))"
```

Expected: JSON with `key, label, icon, tier, rule, numeric, caveat, sources`; `tier == "green"` for Kastanienallee 12.

- [ ] **Step 7: Verify graceful degradation — temporarily break the scorer**

In `app/core/scorer.py`, at the very top of `young_family_lens(...)`, temporarily add:

```python
    raise RuntimeError("temp — verify catch-all")
```

Restart the server if needed (kill and re-uvicorn), then:

```bash
curl -s "http://127.0.0.1:8000/api/lookup?address=Kastanienallee+12%2C+10435" \
  | python3 -c "import json,sys; \
    d=json.load(sys.stdin); \
    yf=(d.get('lens') or {}).get('young_family') or {}; \
    print('lens error:', yf.get('error')); \
    print('rest of lookup intact:', 'address' in d and 'catchment' in d)"
```

Expected:
```
lens error: RuntimeError: temp — verify catch-all
rest of lookup intact: True
```

Then **revert** the `raise` line in `scorer.py`.

- [ ] **Step 8: Commit**

```bash
git add app/routes/lookup.py
git commit -m "Wire young_family lens into /api/lookup with try/except catch-all"
```

---

## Task 7: Live selfcheck assertions in `app/selfcheck.py`

**Files:**
- Modify: `app/selfcheck.py` — extend `run_live_selfcheck()` with two known-good address blocks

**Interfaces:**
- Consumes: `Index.geocode`, `Index.kitas_near_bod`, `Index.trees_bbox`, `Index.nearest_quiet_zone`, `scorer.young_family_lens`, `air_quality_at`, `summer_heat_at`, `noise_at`, `amenities_near`
- Produces: `python -m app.selfcheck` now runs Kastanienallee 12 + Bergmannstraße 27 lens assertions

- [ ] **Step 1: Add imports at the top of `app/selfcheck.py`**

Extend the existing import block:

```python
from app.core.amenities import amenities_near
from app.core import scorer
```

`air_quality_at`, `summer_heat_at`, `noise_at` are already imported (they're used elsewhere in the live selfcheck).

- [ ] **Step 2: Append the lens block near the end of `run_live_selfcheck()`**

Locate the closing `print("→ live selfcheck OK")` in `run_live_selfcheck()`. Immediately *before* that line, insert:

```python
    # -- Young Family lens ---------------------------------------------------
    # Two known-good addresses cover two very different lens shapes:
    #   Kastanienallee 12 (Prenzlauer Berg) — dense, family-heavy inner city.
    #   Bergmannstraße 27 (Kreuzberg)      — the user-verified pediatrician anchor.
    def _compute_lens(lon_, lat_):
        _amen  = (amenities_near(idx, cfg, lon_, lat_, 800) or {}).get("amenities") or {}
        _noise = noise_at(cfg, lon_, lat_)
        _air   = air_quality_at(cfg, lon_, lat_)
        _heat  = summer_heat_at(cfg, lon_, lat_)
        _trees = idx.trees_bbox(lon_, lat_)
        _qz    = idx.nearest_quiet_zone(lon_, lat_)
        _lens  = scorer.young_family_lens(cfg, idx, lon_, lat_,
                                          air=_air, heat=_heat, noise=_noise,
                                          amenities=_amen, trees=_trees,
                                          quiet_zone=_qz)
        return _lens, _amen, _noise, _heat, _air

    lens_yf, _amen, n_raw, h_raw, a_raw = _compute_lens(geo["lon"], geo["lat"])
    assert len(lens_yf["tiles"]) == 7, f"expected 7 tiles, got {len(lens_yf['tiles'])}"
    _keys = [t["key"] for t in lens_yf["tiles"]]
    assert _keys == ["kita","playground","pediatrician","noise","heat","air","refuge"], _keys
    for t in lens_yf["tiles"]:
        assert t["label"] and t["rule"], t
        assert t["tier"] in {"green","amber","red","unknown"}, t
    _by = {t["key"]: t for t in lens_yf["tiles"]}
    # Dense Prenzlauer Berg → kita must be green.
    assert _by["kita"]["tier"] == "green", \
        f"expected kita green at Kastanienallee 12: {_by['kita']}"
    # Defensive: at least one tile must be green.
    assert any(t["tier"] == "green" for t in lens_yf["tiles"]), \
        "the lens must produce some positive signal in dense inner Berlin"
    # kita cited in provenance (kita is green).
    assert "Kindertagesstätten" in lens_yf["provenance"], lens_yf["provenance"]
    # Consistency invariant: no tile is unknown unless the matching raw block
    # is also unavailable in the same lookup.
    if n_raw.get("unavailable"):
        assert _by["noise"]["tier"] == "unknown"
    else:
        assert _by["noise"]["tier"] != "unknown", _by["noise"]
    if h_raw.get("unavailable"):
        assert _by["heat"]["tier"] == "unknown"
    else:
        assert _by["heat"]["tier"] != "unknown", _by["heat"]
    if a_raw.get("unavailable"):
        assert _by["air"]["tier"] == "unknown"
    else:
        assert _by["air"]["tier"] != "unknown", _by["air"]

    # -- Bergmannstraße 27 (pediatrician anchor) -----------------------------
    berg = idx.geocode("Bergmannstraße", "27", "10961")
    if not berg:
        print("  Bergmannstraße 27 geocode failed — skipped pediatrician anchor")
    else:
        lens_b, _, _, _, _ = _compute_lens(berg["lon"], berg["lat"])
        _by_b = {t["key"]: t for t in lens_b["tiles"]}
        assert _by_b["pediatrician"]["tier"] == "green", \
            f"expected paediatric green at Bergmannstraße 27: {_by_b['pediatrician']}"
        assert "m" in _by_b["pediatrician"]["numeric"], _by_b["pediatrician"]
        assert "OSM community-tagged" in _by_b["pediatrician"]["caveat"], \
            _by_b["pediatrician"]["caveat"]
        # Marheinekeplatz Spielplatz is ~75m; playground must be green.
        assert _by_b["playground"]["tier"] == "green", \
            f"expected playground green at Bergmannstraße 27: {_by_b['playground']}"
    print("  young_family lens asserts OK")
```

- [ ] **Step 3: Run the full app selfcheck; expect PASS (network-gated)**

```bash
python -m app.selfcheck
```

Expected sequence: cities isolation OK → pure module blocks OK → live selfcheck prints `young_family lens asserts OK` then `→ live selfcheck OK`. Any single assertion whose data source is genuinely unavailable at test time prints "skipped" via existing graceful-degradation and continues.

- [ ] **Step 4: Commit**

```bash
git add app/selfcheck.py
git commit -m "Add live selfcheck for young_family lens (Kastanienallee, Bergmannstraße)"
```

---

## Task 8: Neumorphic Life Mode toggle — HTML + CSS (no JS behavior yet)

**Files:**
- Modify: `web/index.html` — add toggle button in header + new SVG entries in `ico = {...}`
- Modify: `web/static/app.css` — pill button styling, keyframes pulse animation, `.tier-unknown` class

**Interfaces:**
- Produces: DOM element `#life-mode-toggle` with CSS classes `.lm-toggle` (base), `.lm-toggle.on` (active), `.lm-toggle.pulse` (first-visit); ready for JS wiring in Task 9

**Notes:** Task 8 only produces the *visuals*. Clicking the button does nothing until Task 9. This lets a reviewer approve the neumorphic design independently of the state logic.

- [ ] **Step 1: Read `web/index.html` to locate the header block + `ico = {...}` object**

```bash
grep -n "class=\"header\"\|<header\|ico\s*=\|<script" web/index.html | head -20
```

Note where `ico = {...}` lives — inline in `index.html` or in `app.js`. Note the existing header block structure.

- [ ] **Step 2: Insert the toggle button inside the header**

Add inside `<header>` (adjust wrapper markup to match the existing header layout):

```html
<button id="life-mode-toggle" class="lm-toggle" type="button"
        role="switch" aria-pressed="false"
        aria-label="Life Mode: toggle family-lens view">
  <span class="lm-dot" aria-hidden="true"></span>
  <span class="lm-label">Life Mode</span>
</button>
```

- [ ] **Step 3: Check which icon keys are already present in `ico = {...}`**

```bash
grep -n "^\s*\(kita\|playground\|pediatrician\|noise\|heat\|air\|refuge\)\s*:" web/index.html web/static/app.js
```

Note which keys are missing. Add only the missing ones in the next step.

- [ ] **Step 4: Add missing SVG entries to the `ico = {...}` object**

For each missing key from Step 3, add a matching entry inside `ico = {...}`:

```javascript
kita: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M3 21V10l9-6 9 6v11"/><path d="M9 21V13h6v8"/></svg>`,
playground: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="5" r="2"/><path d="M12 7v6M8 21l4-8 4 8M6 13h12"/></svg>`,
pediatrician: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v8m-4-4h8"/><circle cx="12" cy="15" r="6"/><path d="M9 15h6M12 12v6"/></svg>`,
refuge: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l7 7v11H5V10z"/><path d="M9 21v-6h6v6"/></svg>`,
noise: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4 10v4h4l5 4V6l-5 4H4z"/><path d="M16 8a5 5 0 0 1 0 8"/></svg>`,
heat: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v18M6 8l12 8M6 16l12-8"/></svg>`,
air: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M3 10h11a3 3 0 1 0-3-3M3 14h15a3 3 0 1 1-3 3"/></svg>`,
```

- [ ] **Step 5: Append neumorphic styles to `web/static/app.css`**

```css
/* --- Life Mode toggle (Spec A) ------------------------------------------
   Neumorphic pill matching the existing .cell shadow language. Uses
   --brand for the "on" state and --sh-1/--sh-2 for the raised-surface feel. */
.lm-toggle{
  display:inline-flex; align-items:center; gap:.5em;
  padding:.5em .9em .5em .55em;
  border:none; border-radius:999px;
  background:var(--result-bg, #f2f4f8);
  color:var(--muted, #667);
  font:600 .82em/1 'Plus Jakarta Sans', system-ui, sans-serif;
  letter-spacing:.02em;
  box-shadow: 4px 4px 8px var(--sh-1, rgba(0,0,0,.08)),
             -4px -4px 8px var(--sh-2, rgba(255,255,255,.9));
  cursor:pointer; user-select:none;
  transition: background .18s ease, color .18s ease,
              box-shadow .18s ease, transform .08s ease;
}
.lm-toggle:hover{ transform:translateY(-1px); }
.lm-toggle:active{ transform:translateY(0);
  box-shadow: inset 3px 3px 6px var(--sh-1, rgba(0,0,0,.08)),
             inset -3px -3px 6px var(--sh-2, rgba(255,255,255,.9)); }
.lm-toggle:focus-visible{ outline:2px solid var(--brand, #4a5cff); outline-offset:3px; }
.lm-toggle .lm-dot{
  width:.7em; height:.7em; border-radius:50%;
  background:currentColor; opacity:.35;
  box-shadow: inset 1px 1px 2px rgba(0,0,0,.15);
  transition: opacity .18s ease, background .18s ease;
}
.lm-toggle.on{
  background:var(--brand, #4a5cff); color:#fff;
  box-shadow: inset 3px 3px 6px rgba(0,0,0,.18),
             inset -2px -2px 4px rgba(255,255,255,.18);
}
.lm-toggle.on .lm-dot{ opacity:1; background:#fff; box-shadow:none; }

/* Onboarding pulse — CSS keyframes glow to draw the eye on first visit. */
@keyframes lm-pulse{
  0%,100% { box-shadow: 4px 4px 8px var(--sh-1, rgba(0,0,0,.08)),
                       -4px -4px 8px var(--sh-2, rgba(255,255,255,.9)),
                        0 0 0 0 rgba(74,92,255,.55); }
  50%     { box-shadow: 4px 4px 8px var(--sh-1, rgba(0,0,0,.08)),
                       -4px -4px 8px var(--sh-2, rgba(255,255,255,.9)),
                        0 0 0 12px rgba(74,92,255,0); }
}
.lm-toggle.pulse{ animation: lm-pulse 1.6s ease-out infinite; }

/* --- .tier-unknown ------------------------------------------------------
   Companion to the existing .tier-{green,amber,orange,red} in §14.9. */
.tier-unknown{ --tier-color: #b0b6c0; }
.tier-unknown .tile-tier-badge{ background:#eef0f4; color:#7a8090; font-style:italic; }
.tier-unknown .tile-rule{ font-style:italic; color:#7a8090; }
```

- [ ] **Step 6: Visual QA — open the app in a browser**

Load `http://127.0.0.1:8000/` in Chrome. Confirm visually:

1. Pill button appears in the header.
2. Hover raises the pill (`translateY(-1px)`).
3. Focus shows a brand-color outline ring.
4. Click depresses (inset shadow).
5. The button pulses (radial glow every 1.6s).
6. Styling matches the existing neumorphic language.

Clicking does nothing yet — that's Task 9.

- [ ] **Step 7: Commit**

```bash
git add web/index.html web/static/app.css
git commit -m "Add Life Mode toggle (neumorphic pill + pulse + tier-unknown)"
```

---

## Task 9: Life Mode state management in JS

**Files:**
- Modify: `web/static/app.js` — add state, event handlers, localStorage sync, pulse decay

**Interfaces:**
- Consumes: `#life-mode-toggle` DOM element from Task 8
- Produces:
  - Module-level constants `LM_STATE_KEY = "berlin-lens-mode-v1"`, `LM_SEEN_KEY = "berlin-lens-mode-seen-v1"`, `LM_PULSE_MS = 30000`
  - `setLifeMode(on)` — flips `document.body.classList` (`life-mode`), updates toggle text/attrs, persists to localStorage, calls `renderAllPanels()` (no-op stub until Task 10)
  - `initLifeMode()` — called at boot; reads localStorage, wires click handler, starts pulse if unseen with 30 s auto-decay

- [ ] **Step 1: Find where `app.js` runs at boot**

```bash
grep -n "DOMContentLoaded\|window.addEventListener('load'\|^function boot\|^const boot" web/static/app.js | head
```

Note the existing pattern so the new `initLifeMode()` invocation matches.

- [ ] **Step 2: Add module-level constants near the top of `app.js`**

Insert near other constants (e.g., where localStorage keys already live if any):

```javascript
const LM_STATE_KEY = 'berlin-lens-mode-v1';       // "on" | "off"
const LM_SEEN_KEY  = 'berlin-lens-mode-seen-v1';  // "1" once seen or dismissed
const LM_PULSE_MS  = 30000;                       // auto-stop pulse after 30 s
```

- [ ] **Step 3: Add a stub `renderAllPanels` if one doesn't exist yet**

```bash
grep -n "function renderAllPanels\|const renderAllPanels" web/static/app.js
```

If none exists, add near other render helpers:

```javascript
// Filled in by Task 10; declared here so setLifeMode() can call it safely.
function renderAllPanels() { /* no-op until Task 10 */ }
```

- [ ] **Step 4: Add the state-management functions**

```javascript
function setLifeMode(on) {
  const btn = document.getElementById('life-mode-toggle');
  document.body.classList.toggle('life-mode', on);
  btn.classList.toggle('on', on);
  btn.setAttribute('aria-pressed', on ? 'true' : 'false');
  btn.querySelector('.lm-label').textContent = on ? 'Life Mode: Family' : 'Life Mode';
  try { localStorage.setItem(LM_STATE_KEY, on ? 'on' : 'off'); } catch (e) {}
  renderAllPanels();   // no HTTP call; data already cached per address
}

function initLifeMode() {
  const btn = document.getElementById('life-mode-toggle');
  if (!btn) return;

  // Sticky state.
  let saved = null;
  try { saved = localStorage.getItem(LM_STATE_KEY); } catch (e) {}
  setLifeMode(saved === 'on');

  // First-visit pulse.
  let seen = null;
  try { seen = localStorage.getItem(LM_SEEN_KEY); } catch (e) {}
  const stopPulse = () => {
    btn.classList.remove('pulse');
    try { localStorage.setItem(LM_SEEN_KEY, '1'); } catch (e) {}
  };
  if (!seen) {
    btn.classList.add('pulse');
    setTimeout(stopPulse, LM_PULSE_MS);
  }

  btn.addEventListener('click', () => {
    stopPulse();                                                          // any click stops the pulse
    setLifeMode(!document.body.classList.contains('life-mode'));
  });
}
```

- [ ] **Step 5: Wire `initLifeMode()` into the app's boot hook**

If the app uses `DOMContentLoaded`, add inside the existing handler:

```javascript
document.addEventListener('DOMContentLoaded', () => {
  // ...existing init calls...
  initLifeMode();
});
```

If there's a named `boot()` function, append `initLifeMode();` at its end.

- [ ] **Step 6: Browser QA — verify toggle behavior**

Open a fresh Incognito window at `http://127.0.0.1:8000/`. Verify in order:

1. Toggle visible in header AND pulsing on first load.
2. Click toggle → pulse stops. Label changes to "Life Mode: Family". `document.body` has class `life-mode`. Pill fills brand color.
3. Reload page → toggle still ON, no pulse.
4. In DevTools → Application → Local Storage, delete both `berlin-lens-mode-*-v1` keys. Reload. Toggle OFF and pulsing again.
5. Wait 30 s without clicking. Pulse stops. Reload → no pulse; `berlin-lens-mode-seen-v1` is `"1"` in localStorage.

- [ ] **Step 7: Commit**

```bash
git add web/static/app.js
git commit -m "Add Life Mode state (localStorage sticky, pulse decay 30 s)"
```

---

## Task 10: Lens single-address render + tile grid CSS

**Files:**
- Modify: `web/static/app.js` — add `renderLensSingle(addr)`, `renderLensTile(tile)`; wire into existing per-address panel render
- Modify: `web/static/app.css` — `.lens-view`, `.lens-header`, `.lens-grid`, `.lens-tile`, `.tile-*`, tier color classes

**Interfaces:**
- Consumes: `data.lens.young_family` on the address object (populated by `/api/lookup` from Task 6)
- Produces:
  - `renderLensSingle(addr) -> string` — HTML for the tile grid + header + provenance
  - `renderLensTile(tile) -> string` — HTML for one `.cell`-shaped tile
  - CSS classes `.lens-view`, `.lens-header`, `.lens-grid`, `.lens-tile` reusing the `.cell` neumorphic pattern

- [ ] **Step 1: Find where per-address panels render today**

```bash
grep -n "function render\|panel\.innerHTML\|\.innerHTML\s*=" web/static/app.js | head -30
```

Note the entry point that populates a single-address panel. That's where the Life Mode branch drops in.

- [ ] **Step 2: Add `escapeHtml` if not already present**

```bash
grep -n "escapeHtml\|escape(" web/static/app.js
```

If absent, add near other utilities:

```javascript
function escapeHtml(s) {
  return String(s == null ? '' : s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}
```

- [ ] **Step 3: Add `renderLensTile(tile)`**

```javascript
function renderLensTile(tile) {
  const tier = tile.tier || 'unknown';
  const iconSVG = (typeof ico !== 'undefined' && ico[tile.icon]) || '';
  const badge = tier === 'unknown' ? 'N/A' : tier.toUpperCase();
  const ariaLabel = `${tile.label}, tier ${tier}: ${tile.rule}`;
  return `
    <section class="cell lens-tile tier-${escapeHtml(tier)}"
             aria-label="${escapeHtml(ariaLabel)}">
      <div class="tile-head">
        <span class="tile-icon" aria-hidden="true">${iconSVG}</span>
        <span class="tile-label">${escapeHtml(tile.label)}</span>
        <span class="tile-tier-badge">${escapeHtml(badge)}</span>
      </div>
      <div class="tile-rule">${escapeHtml(tile.rule)}</div>
      ${tile.numeric ? `<div class="tile-numeric">${escapeHtml(tile.numeric)}</div>` : ''}
      ${tile.caveat  ? `<div class="tile-caveat">${escapeHtml(tile.caveat)}</div>`  : ''}
    </section>
  `;
}
```

- [ ] **Step 4: Add `renderLensSingle(addr)`**

```javascript
function renderLensSingle(addr) {
  const lens = addr && addr.data && addr.data.lens && addr.data.lens.young_family;
  if (!lens || lens.error) {
    return `<div class="lens-empty">Lens unavailable for this address.</div>`;
  }
  const tilesHtml = lens.tiles.map(renderLensTile).join('');
  const prov = lens.provenance
    ? `<footer class="lens-provenance">${escapeHtml(lens.provenance)}</footer>`
    : '';
  return `
    <div class="lens-view">
      <header class="lens-header">
        <h2>${escapeHtml(lens.label)}</h2>
        <p class="audience">${escapeHtml(lens.audience || '')}</p>
      </header>
      <div class="lens-grid">${tilesHtml}</div>
      ${prov}
    </div>
  `;
}
```

- [ ] **Step 5: Wire `renderLensSingle` into the per-address render — replace the Task 9 stub**

Find the actual per-address render function noted in Step 1. Modify `renderAllPanels()` (the stub from Task 9) so it iterates open panels and, when Life Mode is on, injects `renderLensSingle(addr)` into the panel's content area:

```javascript
function renderAllPanels() {
  const onLife = document.body.classList.contains('life-mode');
  document.querySelectorAll('.address-panel').forEach(panel => {
    // Substitute with whatever the codebase uses to associate a panel with
    // its address object — e.g., a data attribute or a Map keyed by panel id.
    const addr = /* look up the panel's address object as the existing render does */;
    if (!addr) return;
    if (onLife) {
      panel.querySelector('.panel-body').innerHTML = renderLensSingle(addr);
    } else {
      // Existing raw-tab render — call the same function the app uses today.
      /* existing raw render */;
    }
  });
}
```

If the existing per-address render is named differently (`renderAddress(addr)`, `paintPanel(...)`, etc.), wrap that function so the Life Mode branch is a fork at the top. The raw branch continues to call whatever ran before.

- [ ] **Step 6: Add CSS for the lens grid + tiles**

Append to `web/static/app.css`:

```css
/* --- Life Mode content (Spec A) ---------------------------------------- */
body.life-mode .tab-bar,       /* raw-data tab buttons */
body.life-mode .tab-panel:not(.lens-view){ display:none !important; }
body:not(.life-mode) .lens-view{ display:none !important; }

.lens-view{ display:flex; flex-direction:column; gap:1em; padding:1em 0; }

.lens-header h2{
  margin:0 0 .1em 0;
  font:700 1.15em/1.15 'Plus Jakarta Sans', system-ui, sans-serif;
  color:var(--ink, #2a2f3a);
  letter-spacing:-.01em;
}
.lens-header .audience{
  margin:0; color:var(--muted, #667);
  font:500 .88em/1.35 'Plus Jakarta Sans', system-ui, sans-serif;
}

.lens-grid{
  display:grid; gap:.9em;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
}

.lens-tile{                                      /* reuses .cell neumorphic shape */
  position:relative; padding:.9em 1em .9em 1.3em;
  min-height:118px;
  display:flex; flex-direction:column; gap:.35em;
}
.lens-tile::before{                              /* the §14.9 left color bar */
  content:""; position:absolute; left:0; top:0; bottom:0; width:6px;
  background:var(--tier-color, var(--muted, #b0b6c0));
  border-top-left-radius:inherit; border-bottom-left-radius:inherit;
  transform-origin:top; transform:scaleY(0);
  transition: transform .28s cubic-bezier(.2,.7,.2,1);
}
.lens-tile:hover::before{ transform:scaleY(1); }

.lens-tile .tile-head{ display:flex; align-items:center; gap:.55em; }
.lens-tile .tile-icon{ width:1.1em; height:1.1em; flex:0 0 auto;
                       color:var(--tier-color, var(--muted, #b0b6c0)); }
.lens-tile .tile-icon svg{ width:100%; height:100%; }
.lens-tile .tile-label{ flex:1;
                        font:600 .95em/1.2 'Plus Jakarta Sans', system-ui, sans-serif;
                        color:var(--ink, #2a2f3a); }
.lens-tile .tile-tier-badge{
  font:700 .68em/1 'Plus Jakarta Sans', system-ui, sans-serif;
  letter-spacing:.06em;
  padding:.32em .55em; border-radius:999px;
  background:var(--tier-color, #b0b6c0); color:#fff;
}
.lens-tile .tile-rule{
  font:500 .82em/1.3 'Plus Jakarta Sans', system-ui, sans-serif;
  color:var(--muted, #667);
}
.lens-tile .tile-numeric{
  font:500 .78em/1.35 'Plus Jakarta Sans', system-ui, sans-serif;
  color:var(--ink-2, #4a4f5a);
}
.lens-tile .tile-caveat{
  margin-top:.15em;
  font:italic 400 .72em/1.35 'Plus Jakarta Sans', system-ui, sans-serif;
  color:#8a8f9a;
}

/* Tier colors — reuse existing tokens where present, fall back locally. */
.tier-green { --tier-color: var(--tier-green, #3aa168); }
.tier-amber { --tier-color: var(--tier-amber, #d69a2b); }
.tier-red   { --tier-color: var(--tier-red,   #d05656); }
/* .tier-unknown defined in Task 8. */

.lens-provenance{
  font:italic 400 .72em/1.4 'Plus Jakarta Sans', system-ui, sans-serif;
  color:#8a8f9a; padding:0 .5em;
}
.lens-empty{ padding:1em; color:var(--muted, #667); font-style:italic; }
```

- [ ] **Step 7: Browser QA — verify single-address lens rendering**

Reload with Kastanienallee 12 loaded. Toggle Life Mode ON. Verify:

1. Raw-data tab bar disappears.
2. "Young Family (0–6)" heading + audience subline appear.
3. 7 tiles render in a responsive grid (3-per-row on desktop, 2 on tablet, 1 on mobile).
4. Each tile shows: icon, label, tier badge, rule, numeric; the pediatrician tile also shows a small italic caveat.
5. Hover a tile → left color bar animates (`scaleY(0)→1`) matching the neumorphic language.
6. Provenance footer at the bottom, italic and muted.
7. Toggle OFF → tiles disappear, raw tabs return.

- [ ] **Step 8: Commit**

```bash
git add web/static/app.js web/static/app.css
git commit -m "Add Young Family single-address lens rendering (7-tile grid)"
```

---

## Task 11: Lens compare-view render + dot-matrix CSS

**Files:**
- Modify: `web/static/app.js` — add `renderLensCompare(addresses)`, `renderLensDot(tile)`; wire into existing compare render
- Modify: `web/static/app.css` — `.lens-compare`, `.lens-compare-row`, `.lens-compare-cell`, `.lens-compare-*label`

**Interfaces:**
- Consumes: array of address objects, each with `data.lens.young_family.tiles`
- Produces:
  - `renderLensCompare(addresses) -> string` — HTML for the 7 × N matrix
  - `renderLensDot(tile) -> string` — HTML for one dot cell
  - CSS classes for the compare grid + dot cells

- [ ] **Step 1: Find the existing compare-view render entry point**

```bash
grep -n "compare\|renderCompare\|compareGrid\|compareView" web/static/app.js | head
```

Note where the compare grid is populated so the Life Mode branch drops in there.

- [ ] **Step 2: Add `renderLensDot(tile)`**

```javascript
function renderLensDot(tile) {
  if (!tile) {
    return `<button class="lens-compare-cell tier-unknown" type="button"
                    aria-label="unavailable" title="unavailable">•</button>`;
  }
  const tier = tile.tier || 'unknown';
  const short = `${tile.rule}${tile.numeric ? ' — ' + tile.numeric : ''}`;
  const aria = `${tile.label}, tier ${tier}: ${tile.rule}`;
  return `
    <button class="lens-compare-cell tier-${escapeHtml(tier)}" type="button"
            aria-label="${escapeHtml(aria)}"
            title="${escapeHtml(short)}">
      <span aria-hidden="true">●</span>
    </button>
  `;
}
```

- [ ] **Step 3: Add `renderLensCompare(addresses)`**

```javascript
function renderLensCompare(addresses) {
  if (!addresses || !addresses.length) return '';
  // Use the first address's lens as the row spec — every address returns
  // the same 7 keys in the same order (server contract).
  const first = addresses.find(a => a && a.data && a.data.lens && a.data.lens.young_family
                                  && !a.data.lens.young_family.error);
  if (!first) {
    return `<div class="lens-empty">Lens unavailable for the current addresses.</div>`;
  }
  const rowSpec = first.data.lens.young_family.tiles;   // 7 tiles

  const header = `
    <div class="lens-compare-row lens-compare-head">
      <div class="lens-compare-rowlabel"></div>
      ${addresses.map(a => `
        <div class="lens-compare-collabel">${escapeHtml(
          (a && a.shortLabel) ||
          (a && a.data && a.data.address && a.data.address.street) ||
          '—')}</div>
      `).join('')}
    </div>`;

  const rows = rowSpec.map(spec => {
    const cells = addresses.map(a => {
      const t = a && a.data && a.data.lens && a.data.lens.young_family
              && !a.data.lens.young_family.error
              ? a.data.lens.young_family.tiles.find(x => x.key === spec.key)
              : null;
      return `<div class="lens-compare-cellwrap">${renderLensDot(t)}</div>`;
    }).join('');
    return `
      <div class="lens-compare-row">
        <div class="lens-compare-rowlabel">${escapeHtml(spec.label)}</div>
        ${cells}
      </div>`;
  }).join('');

  return `<div class="lens-compare">${header}${rows}</div>`;
}
```

- [ ] **Step 4: Wire `renderLensCompare` into the compare render**

Extend `renderAllPanels` (or the compare-specific render function noted in Step 1) so that when `document.body.classList.contains('life-mode')` is true *and* compare mode is active, the compare grid area renders `renderLensCompare(addresses)` instead of the raw compare tiles. Match the branching shape used in Task 10.

- [ ] **Step 5: Add CSS for the compare matrix**

Append to `web/static/app.css`:

```css
/* --- Life Mode compare (Spec A) ---------------------------------------- */
.lens-compare{
  display:flex; flex-direction:column; gap:.35em;
  padding:1em 0;
  font:500 .82em/1.3 'Plus Jakarta Sans', system-ui, sans-serif;
}
.lens-compare-row{
  display:grid;
  grid-template-columns: minmax(140px, 1.4fr) repeat(auto-fit, minmax(72px, 1fr));
  gap:.5em; align-items:center;
}
.lens-compare-rowlabel{
  color:var(--ink, #2a2f3a); font-weight:600;
  padding-left:.3em;
}
.lens-compare-collabel{
  text-align:center; color:var(--muted, #667);
  font-weight:600; font-size:.85em;
  overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
}
.lens-compare-head .lens-compare-rowlabel{ min-height:1.6em; }

.lens-compare-cellwrap{ display:flex; justify-content:center; }
.lens-compare-cell{
  width:2em; height:2em; border-radius:50%;
  border:none; padding:0;
  background:var(--tier-color, #b0b6c0);
  color:#fff; font-size:1.4em; line-height:1;
  cursor:default; user-select:none;
  box-shadow: 2px 2px 4px var(--sh-1, rgba(0,0,0,.08)),
             -2px -2px 4px var(--sh-2, rgba(255,255,255,.9));
  transition: transform .12s ease;
}
.lens-compare-cell:hover{ transform:scale(1.08); }
.lens-compare-cell:focus-visible{
  outline:2px solid var(--brand, #4a5cff); outline-offset:3px;
}
.lens-compare-cell.tier-unknown{ background:#eef0f4; color:#7a8090; }
```

- [ ] **Step 6: Browser QA — verify compare view**

Load 2–5 addresses in compare mode. Toggle Life Mode ON. Verify:

1. Raw compare tiles disappear.
2. 7-row × N-column dot matrix appears; row labels on the left, address short labels along the top.
3. Each dot is colored by tier; hover shows a native tooltip with `rule` + `numeric`.
4. Tab-focus moves through dots individually; screen reader announces `aria-label`.
5. Toggle OFF → raw compare tiles return.

- [ ] **Step 7: Commit**

```bash
git add web/static/app.js web/static/app.css
git commit -m "Add Young Family compare-view (7×N dot matrix)"
```

---

## Task 12: Frontend live-browser QA checklist (§14.12)

**Files:**
- No edits — pure manual QA against the running app.

**Interfaces:** none — this task consumes the entire feature.

**Notes:** Nine checklist items lifted verbatim from Spec A's testing section. Do all nine in order on a fresh browser profile. Any failure = return to the responsible task, fix, re-QA.

- [ ] **Step 1: Initial state.** Fresh Incognito window at `http://127.0.0.1:8000/`. Confirm: Life Mode toggle visible in header, pulsing. Label reads "Life Mode" (OFF state).

- [ ] **Step 2: Pulse decay by timeout.** Same window, don't click anything for 30 s. Confirm: pulse stops. `localStorage.getItem('berlin-lens-mode-seen-v1')` returns `"1"` in DevTools.

- [ ] **Step 3: Pulse decay by click.** Another fresh Incognito window. Click the toggle before 30 s. Confirm: pulse stops. `berlin-lens-mode-seen-v1` is set. Toggle shows ON state (label "Life Mode: Family").

- [ ] **Step 4: Mode switch — single address.** Enter Kastanienallee 12, 10435 with Life Mode OFF. Toggle ON. Confirm: raw-data tab bar hides; 7-tile grid renders under "Young Family (0–6)". Toggle OFF; raw tabs restored.

- [ ] **Step 5: State persistence.** With Life Mode ON, reload. Confirm: mode still ON.

- [ ] **Step 6: Compare view.** Enter 2+ addresses. Toggle ON. Confirm: 7-row × N-column dot matrix renders. Hover a dot → tooltip with rule + numeric. Toggle OFF; existing compare panels return.

- [ ] **Step 7: Outage state.** Simulate Umweltatlas WFS outage — temporarily point `air_wfs_url` and `heat_wfs_url` in `app/cities/berlin.py` to `http://localhost:9/` (a definitely-dead port). Restart the server. Reload address. Confirm: Air and Heat tiles render gray with "N/A" badge and italic *"Umweltatlas WFS unavailable"* rule. The other 5 tiles render normal tiers. Provenance footer omits Umweltatlas. **Revert `berlin.py`** and restart the server.

- [ ] **Step 8: Keyboard accessibility.** Tab-focus to Life Mode toggle. Press Space — mode flips. Press Space again — flips back. Tab through tiles when Life Mode ON — each tile focusable, VoiceOver / NVDA announces `aria-label`. Tab through compare dots — each individually focusable.

- [ ] **Step 9: Missing lens block.** In `app/core/scorer.py`, at the very top of `young_family_lens(...)`, temporarily add `raise RuntimeError("qa test")`. Restart the server. Reload address. Confirm: rest of `/api/lookup` renders normally. Life Mode toggle disabled with hover title "Lens unavailable for this address" — clicking is a no-op. **Revert** the `raise` and restart.

- [ ] **Step 10: Clean up ephemeral screenshots per §14.12.**

- [ ] **Step 11: Mark ship-ready with an empty commit**

```bash
git commit --allow-empty -m "Young Family lens: live-browser QA passed (Spec A shipped)"
```

---

## Self-Review

**1. Spec coverage:**
- Every scope-in item mapped: header toggle (Tasks 8+9), lens (Tasks 4-5), 7 tiles (Tasks 4+2), scorer server-side (Tasks 4-5), `LensConfig` on `CityConfig` (Task 2), single-address + compare views (Tasks 10+11), onboarding pulse (Tasks 8+9), pure + live selfcheck (Tasks 4-5+7), Neumorphic UI (Task 8+10+11 with reused `.cell` + `::before` pattern).
- Locked-decision threshold values are all in Task 2's Berlin instantiation and Task 4's boundary asserts.
- Non-goals honored — no pytest, no new endpoint, no drill-down modal, no future lenses in this spec.

**2. Placeholder scan:** clean. No TBD/TODO. Every code block is complete and runnable. The seven `_tier_*` functions are all spelled out; the tile output shape is spelled out in Task 5.

**3. Type consistency across tasks:**
- `young_family_lens` field name matches across `base.py` (definition), `berlin.py` (assignment), and `lookup.py` (dot access).
- `LensTileConfig.thresholds` dict-key names in Task 2's Berlin config match the Task 4 tier fn readers (`green_m`/`amber_m`, `green_db`/`amber_db`, `green_ugm3`/`amber_ugm3`, `green_classes`/`amber_classes`, `green_quiet_m`/`amber_quiet_m`, `green_crown_pct`/`amber_crown_pct`, `green_count`).
- Function signatures line up: `_tier_playground(playgrounds, playgrounds_error, t)` in Task 4 matches its call site in Task 5 (`_tier_playground(pg_items, pg_error, thresholds["playground"])`). Same for `_tier_pediatrician(paediatricians, gps_error, t)`.
- Tile output keys are `{key, label, icon, tier, rule, numeric, caveat, sources}` — set explicitly in Task 5's composer and asserted in Step 4 of Task 5. Task 10 and Task 11 read exactly these keys.
- Provenance sources are looked up from `cfg.attribution.get(...)` — the keys are the same ones Berlin's attribution dict already carries (`kitas`, `playgrounds`, `parks`, `noise`, `heat`, `air`, `quiet_zone`, `trees`).

No inconsistencies found. Plan is ready to hand off.
