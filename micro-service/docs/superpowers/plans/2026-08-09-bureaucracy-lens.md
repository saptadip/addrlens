# Bureaucracy Lens Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the Bureaucracy lens — 5-tile Life-Mode view of Berlin public-admin offices (Bürgeramt, Finanzamt, Standesamt, LEA, Arbeitsagentur) — as a second lens alongside the shipped Young Family lens, matching Spec B at `docs/superpowers/specs/2026-08-09-bureaucracy-lens-design.md`.

**Architecture:** Reuses Spec A's lens abstraction (`LensConfig`/`LensTileConfig` on `CityConfig`, pure composer in `app/core/scorer.py`, folded into `/api/lookup` under `lens.*`). Bureaucracy is deterministic — no live per-request WFS on the hot path; all data is boot-preloaded (Bezirksgrenzen + Bürgerämter) or config-embedded (Finanzämter, Standesämter, Arbeitsagentur, LEA). Frontend gains a segmented `.pill-btn` lens picker above the tile grid.

**Tech Stack:** Python 3.11+, FastAPI, shapely (existing app deps only — no new deps). Vanilla JS + hand-authored CSS (no build step, no bundler, no npm).

## Global Constraints

- **Spec A is already merged on `main`.** Do not modify `young_family_lens`, `YOUNG_FAMILY_LENS`, or any Spec A code paths except where Section-4 error-handling explicitly extends shared helpers (`_sources_for`, `renderLensSingle`, `renderLensCompare`, `renderAllPanels`).
- **Frozen dataclasses, no defaults on `CityConfig` fields.** Every new field must be spelled by Berlin at import time; missing fields fail cities-isolation immediately.
- **`app/core/*` modules are pure.** No I/O, no WFS calls at request time. `Index.__init__` preloads happen once at boot.
- **Bureaucracy composer is deterministic.** No live fetches on the hot path — data is boot-preloaded or config-embedded. Same inputs must produce byte-for-byte identical output.
- **Per-city facts live in `app/cities/berlin.py`.** No hard-coded Berlin values inside `core/`.
- **BOD-first with curated hardcoded fallback** (§14.4). Finanzämter, Standesämter, Arbeitsagentur, LEA are hardcoded curated directories; Bezirksgrenzen and Bürgerämter come from Berlin BOD WFS.
- **Testing without pytest.** Every module carries a `if __name__ == "__main__"` block with `assert` statements. Live asserts extend `app.selfcheck.run_live_selfcheck`.
- **`.pill-btn` primitive is the base for the lens picker.** Do NOT invent a new pill/toggle stack. Reuse the Spec A + existing convention.
- **Neumorphic tokens** — shadow colors are `var(--neumo-sh-light)` / `var(--neumo-sh-dark)`; tier colors are `var(--success)` / `var(--amber)` / `var(--danger)`. Do NOT invent `--sh-1`/`--sh-2` as color arguments or `--tier-*` tokens.
- **Plus Jakarta Sans** typography, inline SVGs in the shared `ico = {...}` object, no build step / bundler / npm.
- **localStorage keys follow `berlin-lens-<feature>-v<n>`** (§14.10). One new key added: `berlin-lens-active-v1`.
- **Every threshold inclusive on greener side** — 15 min walk = green, 15.01 min = amber. Same rule as Spec A.
- **Walk-minutes proxy**: `_walk_minutes(dist_m) = dist_m / 62`. Uniform across all bureaucracy tiles.
- **`ponytail:` comments** mark deliberate simplifications with a named ceiling and upgrade path.
- **Commit after every task passes its selfcheck.** Short imperative subject; split by concern.

## File Structure

**Backend (Python):**

| File | Responsibility | Task |
|---|---|---|
| `app/cities/base.py` | Add new required fields to `CityConfig` (bezirksgrenzen_*, buergeramt_*, finanzamts, standesamts_by_bezirk, arbeitsagenturs, lea_office, bureaucracy_lens) | 1 |
| `app/cities/berlin.py` | Instantiate `BUREAUCRACY_LENS` + curated federal directories + new attribution keys | 2 |
| `app/core/index.py` | Preload Bezirksgrenzen + Bürgerämter at boot; add 5 lookup methods | 3 |
| `app/core/scorer.py` | Add `_walk_minutes` helper + 5 pure `_tier_bureau_*` fns + boundary sweeps | 4 |
| `app/core/scorer.py` | Add `bureaucracy_lens` composer + extend `_sources_for` mapping + composition asserts | 5 |
| `app/routes/lookup.py` | Add second try/except catch-all; response gains `lens.bureaucracy` | 6 |
| `app/selfcheck.py` | Add live selfcheck for Kastanienallee + Bergmannstraße (Bezirk-assigned Standesamt) | 7 |

**Frontend (vanilla):**

| File | Responsibility | Task |
|---|---|---|
| `web/index.html`, `web/static/app.css` | Add 5 tile SVGs + `.lens-picker` CSS block | 8 |
| `web/static/app.js` | Add picker state (`LM_ACTIVE_KEY`, `getActiveLens`, `setActiveLens`, `renderLensPicker`, `isAnyLensAvailable`); extend `renderLensSingle` / `renderLensCompare` / `renderAllPanels` to read active lens | 9 |
| — | §14.12 live-browser QA checklist (10 items, manual) | 10 |

---

## Task 1: `CityConfig` field extensions for bureaucracy

**Files:**
- Modify: `app/cities/base.py` — add fields to `CityConfig` dataclass; no changes to `LensConfig` / `LensTileConfig` (they already exist from Spec A)

**Interfaces:**
- Consumes: `LensConfig` and `Optional` from existing imports in `base.py`
- Produces (new required fields on `CityConfig`):
  - `bezirksgrenzen_wfs_url: Optional[str]`
  - `bezirksgrenzen_layer: Optional[str]`
  - `bezirksgrenzen_field_map: dict`     — `{"name": <field>}` — property key holding the Bezirk name
  - `buergeramt_wfs_url: Optional[str]`
  - `buergeramt_layer: Optional[str]`
  - `buergeramt_field_map: dict`         — `{"name","address","website"}`
  - `finanzamts: tuple`                  — tuple of dicts `{"name","address","lat","lon"}`
  - `standesamts_by_bezirk: dict`        — Bezirk name → office dict `{"name","address","lat","lon"}`; MUST have exactly 12 entries at Berlin's instantiation
  - `arbeitsagenturs: tuple`             — tuple of dicts `{"name","address","lat","lon"}`
  - `lea_office: dict`                   — `{"name","address","lat","lon"}`
  - `bureaucracy_lens: LensConfig`

**Notes:** Cities-isolation will fail during Steps 2–3 of this task because `berlin.py` doesn't yet spell any of these fields. Intended: that's the safety net working. Task 2 fixes it.

- [ ] **Step 1: Read `app/cities/base.py` to locate the last field on `CityConfig`**

```bash
grep -n "young_family_lens\|attribution" app/cities/base.py | head
```

The new fields land AFTER the existing `young_family_lens: LensConfig` field.

- [ ] **Step 2: Add the ten new fields to `CityConfig`**

Insert immediately after the `young_family_lens: LensConfig` line:

```python
    # -- Spec B: Bureaucracy lens ---------------------------------------
    # Bezirksgrenzen — 12 polygons for point-in-polygon Bezirk assignment
    bezirksgrenzen_wfs_url:      Optional[str]
    bezirksgrenzen_layer:        Optional[str]
    bezirksgrenzen_field_map:    dict            # {"name": "namgem"} or similar
    # Bürgeramt (BOD WFS layer — points)
    buergeramt_wfs_url:          Optional[str]
    buergeramt_layer:            Optional[str]
    buergeramt_field_map:        dict            # {"name","address","website"}
    # Curated federal-office directories (small, stable — like regional_rail_stations)
    finanzamts:                  tuple           # ({"name","address","lat","lon"}, ...)
    standesamts_by_bezirk:       dict            # bezirk_name -> {"name","address","lat","lon"}
    arbeitsagenturs:             tuple           # ({"name","address","lat","lon"}, ...)
    lea_office:                  dict            # {"name","address","lat","lon"}
    # Bureaucracy lens
    bureaucracy_lens:            LensConfig
```

- [ ] **Step 3: Confirm the file still parses**

```bash
python -c "from app.cities.base import CityConfig; print(CityConfig.__dataclass_fields__.keys())" 2>&1 | head -3
```

Expected: prints a `dict_keys([...])` view including the ten new field names. If it errors, re-check the insertion point.

- [ ] **Step 4: Run cities isolation; expect FAIL because Berlin doesn't spell the new fields yet**

```bash
python -c "from app.selfcheck import run_cities_isolation; run_cities_isolation()"
```

Expected: berlin fails with `TypeError: CityConfig.__init__() missing 10 required positional arguments: 'bezirksgrenzen_wfs_url', 'bezirksgrenzen_layer', …`. This proves the fields are truly required (no defaults leaked in). Task 2 wires the values.

- [ ] **Step 5: Commit**

```bash
git add app/cities/base.py
git commit -m "Add Bureaucracy lens fields to CityConfig (Spec B prep)"
```

---

## Task 2: Berlin config — BUREAUCRACY_LENS + curated federal directories + attribution keys

**Files:**
- Modify: `app/cities/berlin.py` — add module-level constants + wire them into `BERLIN = CityConfig(...)`
- Test: no new test file; cities-isolation catches structural bugs at import

**Interfaces:**
- Consumes: `CityConfig`, `LensConfig`, `LensTileConfig` (already imported from `app.cities.base`)
- Produces:
  - `BUREAUCRACY_LENS: LensConfig` module-level constant
  - `_STANDESAMTS_BY_BEZIRK: dict` module-level constant — 12 entries
  - `_FINANZAMTS: tuple` module-level constant
  - `_ARBEITSAGENTURS: tuple` module-level constant
  - `_LEA_OFFICE: dict` module-level constant
  - `_WFS_BEZIRKE`, `_WFS_BUERGERAEMTER` — URL string constants (verify against Berlin Geoportal at implementation time)
  - `BERLIN.bureaucracy_lens = BUREAUCRACY_LENS` + all the new field values wired in
  - Six new keys in `attribution` dict

**Notes:** The curated directories below are STARTER data — implementer verifies against public sources during implementation. Standesämter is exactly 12 entries (one per Bezirk); the other lists are approximations from public references.

- [ ] **Step 1: Extend the `_WFS_*` block at the top of `berlin.py`**

Under the existing `_WFS_*` constants (near line 45-53), add:

```python
# Spec B — Bureaucracy lens
_WFS_BEZIRKE       = "https://gdi.berlin.de/services/wfs/alkis_bezirke"        # ponytail: verify layer name at implementation time; probe with GetCapabilities if unsure
_WFS_BUERGERAEMTER = "https://gdi.berlin.de/services/wfs/buergeraemter"        # ponytail: same — Berlin Geoportal catalog is the source of truth
```

Verify the exact WFS URLs at implementation time by running `curl -s "<url>?service=WFS&request=GetCapabilities" | head -100` and confirming the endpoint exists. If a probe returns 404, search the Berlin Geoportal catalog (https://daten.berlin.de/) for the correct layer.

- [ ] **Step 2: Add curated federal-office directories as module-level constants**

Add above the existing `YOUNG_FAMILY_LENS` block:

```python
# --- Bureaucracy lens curated directories (Spec B) -------------------------
# Small, stable federal-adjacent directories. Hardcoded here per §14.4
# "BOD first, curated fallback" — the Berlin Geoportal doesn't cleanly
# publish these; curated is the honest choice for stable directories.
# ponytail: refresh annually or when a Bezirk merger/rename happens.

# One Standesamt per Bezirk (12 total). Names + addresses from berlin.de.
# Coordinates rounded to 4 decimals (~11 m precision). Verify at
# implementation time via Nominatim or Berlin's own address lookup.
_STANDESAMTS_BY_BEZIRK = {
    "Mitte":                          {"name": "Standesamt Mitte",
                                        "address": "Karl-Marx-Allee 31, 10178 Berlin",
                                        "lat": 52.5197, "lon": 13.4180},
    "Friedrichshain-Kreuzberg":       {"name": "Standesamt Friedrichshain-Kreuzberg",
                                        "address": "Schlesische Str. 27a, 10997 Berlin",
                                        "lat": 52.5008, "lon": 13.4460},
    "Pankow":                         {"name": "Standesamt Pankow",
                                        "address": "Fröbelstr. 17, 10405 Berlin",
                                        "lat": 52.5348, "lon": 13.4249},
    "Charlottenburg-Wilmersdorf":     {"name": "Standesamt Charlottenburg-Wilmersdorf",
                                        "address": "Otto-Suhr-Allee 100, 10585 Berlin",
                                        "lat": 52.5163, "lon": 13.3020},
    "Spandau":                        {"name": "Standesamt Spandau",
                                        "address": "Carl-Schurz-Str. 2/6, 13597 Berlin",
                                        "lat": 52.5350, "lon": 13.2010},
    "Steglitz-Zehlendorf":            {"name": "Standesamt Steglitz-Zehlendorf",
                                        "address": "Kirchstr. 1/3, 14163 Berlin",
                                        "lat": 52.4319, "lon": 13.2596},
    "Tempelhof-Schöneberg":           {"name": "Standesamt Tempelhof-Schöneberg",
                                        "address": "Rathausstr. 27, 12105 Berlin",
                                        "lat": 52.4685, "lon": 13.3888},
    "Neukölln":                       {"name": "Standesamt Neukölln",
                                        "address": "Karl-Marx-Str. 83, 12040 Berlin",
                                        "lat": 52.4813, "lon": 13.4400},
    "Treptow-Köpenick":               {"name": "Standesamt Treptow-Köpenick",
                                        "address": "Alt-Köpenick 21, 12555 Berlin",
                                        "lat": 52.4459, "lon": 13.5765},
    "Marzahn-Hellersdorf":            {"name": "Standesamt Marzahn-Hellersdorf",
                                        "address": "Riesaer Str. 94, 12627 Berlin",
                                        "lat": 52.5390, "lon": 13.6055},
    "Lichtenberg":                    {"name": "Standesamt Lichtenberg",
                                        "address": "Egon-Erwin-Kisch-Str. 106, 13059 Berlin",
                                        "lat": 52.5670, "lon": 13.5030},
    "Reinickendorf":                  {"name": "Standesamt Reinickendorf",
                                        "address": "Eichborndamm 215-239, 13437 Berlin",
                                        "lat": 52.5825, "lon": 13.3130},
}

# Finanzämter — ~17 offices across Berlin. Individual-income tax
# jurisdictions carve Berlin by street ranges, so this directory is a
# "starting point" (caveat on the lens tile carries this disclosure).
# ponytail: verify addresses at berlin.de/finanzaemter; annual refresh.
_FINANZAMTS = (
    {"name": "Finanzamt Charlottenburg",       "address": "Bismarckstr. 48, 10627 Berlin",
     "lat": 52.5075, "lon": 13.3060},
    {"name": "Finanzamt Friedrichshain-Kreuzberg", "address": "Möllendorffstr. 34, 10367 Berlin",
     "lat": 52.5225, "lon": 13.4550},
    {"name": "Finanzamt Lichtenberg",          "address": "Josef-Orlopp-Str. 62, 10365 Berlin",
     "lat": 52.5225, "lon": 13.4790},
    {"name": "Finanzamt Marzahn-Hellersdorf",  "address": "Allee der Kosmonauten 29, 10315 Berlin",
     "lat": 52.5305, "lon": 13.5265},
    {"name": "Finanzamt Mitte/Tiergarten",     "address": "Neue Jakobstr. 6-7, 10179 Berlin",
     "lat": 52.5140, "lon": 13.4160},
    {"name": "Finanzamt Neukölln",             "address": "Thiemannstr. 1, 12059 Berlin",
     "lat": 52.4680, "lon": 13.4530},
    {"name": "Finanzamt Pankow/Weißensee",     "address": "Storkower Str. 134, 10407 Berlin",
     "lat": 52.5290, "lon": 13.4560},
    {"name": "Finanzamt Prenzlauer Berg",      "address": "Storkower Str. 134, 10407 Berlin",
     "lat": 52.5290, "lon": 13.4560},
    {"name": "Finanzamt Reinickendorf",        "address": "Eichborndamm 208, 13437 Berlin",
     "lat": 52.5820, "lon": 13.3140},
    {"name": "Finanzamt Schöneberg",           "address": "Bundesallee 171, 10715 Berlin",
     "lat": 52.4820, "lon": 13.3335},
    {"name": "Finanzamt Spandau",              "address": "Nonnendammallee 15-21, 13599 Berlin",
     "lat": 52.5395, "lon": 13.2170},
    {"name": "Finanzamt Steglitz",             "address": "Schloßstr. 58-59, 12165 Berlin",
     "lat": 52.4570, "lon": 13.3260},
    {"name": "Finanzamt Tempelhof",            "address": "Tempelhofer Damm 234, 12099 Berlin",
     "lat": 52.4525, "lon": 13.3860},
    {"name": "Finanzamt Treptow-Köpenick",     "address": "Seelenbinderstr. 99, 12555 Berlin",
     "lat": 52.4570, "lon": 13.5770},
    {"name": "Finanzamt Wedding",              "address": "Osloer Str. 37, 13359 Berlin",
     "lat": 52.5540, "lon": 13.3800},
    {"name": "Finanzamt Wilmersdorf",          "address": "Volkslehrer- und Blissestr., 10713 Berlin",
     "lat": 52.4870, "lon": 13.3120},
    {"name": "Finanzamt Zehlendorf",           "address": "Martin-Buber-Str. 20, 14163 Berlin",
     "lat": 52.4330, "lon": 13.2540},
)

# Arbeitsagentur — Bundesagentur für Arbeit branches in Berlin.
# ~10 branches. Curated from arbeitsagentur.de.
_ARBEITSAGENTURS = (
    {"name": "Agentur für Arbeit Berlin Mitte",     "address": "Friedrichstr. 34, 10969 Berlin",
     "lat": 52.5063, "lon": 13.3900},
    {"name": "Agentur für Arbeit Berlin Nord",      "address": "Königin-Elisabeth-Str. 49, 14059 Berlin",
     "lat": 52.5290, "lon": 13.2880},
    {"name": "Agentur für Arbeit Berlin Süd",       "address": "Sonnenallee 282, 12057 Berlin",
     "lat": 52.4700, "lon": 13.4500},
    {"name": "Agentur für Arbeit Berlin Marzahn",   "address": "Allee der Kosmonauten 29, 12681 Berlin",
     "lat": 52.5410, "lon": 13.5910},
    {"name": "Agentur für Arbeit Berlin Neukölln",  "address": "Sonnenallee 282, 12057 Berlin",
     "lat": 52.4700, "lon": 13.4500},
    {"name": "Agentur für Arbeit Berlin Pankow",    "address": "Storkower Str. 118, 10407 Berlin",
     "lat": 52.5300, "lon": 13.4530},
    {"name": "Agentur für Arbeit Berlin Reinickendorf", "address": "Miraustr. 54, 13509 Berlin",
     "lat": 52.5900, "lon": 13.3320},
    {"name": "Agentur für Arbeit Berlin Spandau",   "address": "Altonaer Str. 70-72, 13581 Berlin",
     "lat": 52.5320, "lon": 13.2010},
    {"name": "Agentur für Arbeit Berlin Steglitz",  "address": "Kaiser-Wilhelm-Str. 1, 12247 Berlin",
     "lat": 52.4360, "lon": 13.3200},
    {"name": "Agentur für Arbeit Berlin Charlottenburg", "address": "Königin-Elisabeth-Str. 49, 14059 Berlin",
     "lat": 52.5290, "lon": 13.2880},
)

# LEA — Landesamt für Einwanderung, main office.
_LEA_OFFICE = {
    "name": "LEA Berlin — Landesamt für Einwanderung",
    "address": "Friedrich-Krause-Ufer 24, 13353 Berlin",
    "lat": 52.5450, "lon": 13.3616,
}
```

- [ ] **Step 3: Add `BUREAUCRACY_LENS` module-level constant**

Add immediately after the `YOUNG_FAMILY_LENS` definition:

```python
# --- Bureaucracy lens (Spec B) --------------------------------------------
# Five traffic-light tiles for Berlin public-admin infrastructure.
# Boundary convention: inclusive on greener side (≤ 15 min = green;
# > 15 min = amber). See
# docs/superpowers/specs/2026-08-09-bureaucracy-lens-design.md.
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

- [ ] **Step 4: Wire the eleven new field values into `BERLIN = CityConfig(...)`**

Find the `young_family_lens=YOUNG_FAMILY_LENS,` line inside `BERLIN = CityConfig(...)`. Immediately AFTER that line, add:

```python
    # --- Spec B: Bureaucracy lens ---------------------------------
    bezirksgrenzen_wfs_url=_WFS_BEZIRKE,
    bezirksgrenzen_layer="alkis_bezirke",                  # ponytail: verify via GetCapabilities
    bezirksgrenzen_field_map={"name": "namgem"},           # ponytail: probe layer for correct property key
    buergeramt_wfs_url=_WFS_BUERGERAEMTER,
    buergeramt_layer="buergeraemter",                      # ponytail: verify via GetCapabilities
    buergeramt_field_map={"name": "standort", "address": "adresse", "website": "internet"},
    finanzamts=_FINANZAMTS,
    standesamts_by_bezirk=_STANDESAMTS_BY_BEZIRK,
    arbeitsagenturs=_ARBEITSAGENTURS,
    lea_office=_LEA_OFFICE,
    bureaucracy_lens=BUREAUCRACY_LENS,
```

- [ ] **Step 5: Add six new keys to `BERLIN.attribution`**

Find the `attribution=` block inside `BERLIN = CityConfig(...)` and add these six keys (place near the end of the existing attribution dict, before the closing `}`):

```python
        "bezirksgrenzen": "Geoportal Berlin / Bezirksgrenzen (dl-de/by-2.0)",
        "buergeramt":     "Geoportal Berlin / Bürgerämter (dl-de/by-2.0)",
        "finanzamt":      "Curated from berlin.de Finanzamt-Verzeichnis (public reference)",
        "standesamt":     "Curated from berlin.de Standesamt-Verzeichnis (public reference)",
        "lea":            "Curated from Landesamt für Einwanderung Berlin (public reference)",
        "arbeitsagentur": "Curated from Bundesagentur für Arbeit Berlin-Brandenburg (public reference)",
```

- [ ] **Step 6: Confirm `standesamts_by_bezirk` has exactly 12 entries**

```bash
python -c "from app.cities.berlin import BERLIN; print(len(BERLIN.standesamts_by_bezirk))"
```

Expected: `12`. If not, the dict is missing a Bezirk (bug — must fix before proceeding).

- [ ] **Step 7: Confirm `bureaucracy_lens.tiles` has 5 entries in expected order**

```bash
python -c "from app.cities.berlin import BERLIN; print([t.key for t in BERLIN.bureaucracy_lens.tiles])"
```

Expected: `['buergeramt', 'finanzamt', 'standesamt', 'lea', 'arbeitsagentur']`.

- [ ] **Step 8: Run cities isolation; expect PASS**

```bash
python -c "from app.selfcheck import run_cities_isolation; run_cities_isolation()"
```

Expected: `→ berlin … OK`.

- [ ] **Step 9: Commit**

```bash
git add app/cities/berlin.py
git commit -m "Wire BUREAUCRACY_LENS + curated federal directories onto Berlin"
```

---

## Task 3: Index preloads (Bezirksgrenzen + Bürgerämter) + 5 lookup methods

**Files:**
- Modify: `app/core/index.py` — extend `Index.__init__` with boot-time preload of Bezirksgrenzen and Bürgerämter; add five new instance methods

**Interfaces:**
- Consumes: `cfg.bezirksgrenzen_*`, `cfg.buergeramt_*` (from Task 2), plus `cfg.finanzamts`, `cfg.standesamts_by_bezirk`, `cfg.arbeitsagenturs`, `cfg.lea_office`
- Produces:
  - `self.bezirksgrenzen: list[tuple[dict, shapely geom]]` — 12 polygons
  - `self.buergeramts: list[dict]` — ~40 offices with `{name, address, website, lat, lon}`
  - `Index.bezirk_for(lon, lat) -> Optional[str]` — point-in-polygon Bezirk lookup
  - `Index.buergeramt_near(lon, lat, radius_m=3000) -> list[dict]` — all offices within radius, sorted asc; each entry has `distance_m` added
  - `Index.arbeitsagentur_near(lon, lat, radius_m=5000) -> list[dict]` — same shape
  - `Index.finanzamt_nearest(lon, lat) -> Optional[dict]` — nearest office with `distance_m` added
  - `Index.standesamt_for(lon, lat) -> Optional[dict]` — via `bezirk_for` → `cfg.standesamts_by_bezirk` lookup; returns `None` for outside-Berlin addresses

**Notes:** Existing `Index.__init__` has a bunch of `if cfg.<x>_wfs_url and cfg.<x>_layer` guarded preload blocks. Match that style.

- [ ] **Step 1: Locate the last existing preload block in `Index.__init__`**

```bash
grep -n "def __init__\|sys.stdout.write\|self\.pools\|self\.natural_swim" app/core/index.py | tail -10
```

The new preload block lands AFTER the last existing preload (likely after `self.natural_swim`).

- [ ] **Step 2: Add Bezirksgrenzen preload**

Append to `Index.__init__`, after the last existing preload (likely `pools + natural_swim`):

```python
        # -- Spec B: Bureaucracy lens preloads -----------------------------
        # Bezirksgrenzen — 12 polygons, small (§14.6 preload rule).
        self.bezirksgrenzen = []
        if cfg.bezirksgrenzen_wfs_url and cfg.bezirksgrenzen_layer:
            sys.stdout.write("loading Bezirksgrenzen… "); sys.stdout.flush()
            r = wfs(cfg.bezirksgrenzen_wfs_url, typeNames=cfg.bezirksgrenzen_layer,
                    count=50, outputFormat=cfg.wfs_output_format)
            for f in r.get("features", []):
                if not f.get("geometry"): continue
                self.bezirksgrenzen.append((f["properties"], shape(f["geometry"])))
            print(f"{len(self.bezirksgrenzen)} Bezirke")

        # Bürgerämter — BOD point layer (~40 city-wide); preload once.
        self.buergeramts = []
        if cfg.buergeramt_wfs_url and cfg.buergeramt_layer:
            sys.stdout.write("loading Bürgerämter… "); sys.stdout.flush()
            r = wfs(cfg.buergeramt_wfs_url, typeNames=cfg.buergeramt_layer,
                    count=200, outputFormat=cfg.wfs_output_format)
            bfm = cfg.buergeramt_field_map
            for f in r.get("features", []):
                g = f.get("geometry")
                if not g: continue
                lo, la = g["coordinates"]
                p = f["properties"] or {}
                self.buergeramts.append({
                    "name":    (p.get(bfm["name"]) or "Bürgeramt").strip(),
                    "address": (p.get(bfm["address"]) or "").strip(),
                    "website": (p.get(bfm["website"]) or "").strip(),
                    "lat": la, "lon": lo,
                })
            print(f"{len(self.buergeramts)} Bürgerämter")
```

- [ ] **Step 3: Add the five lookup methods to the `Index` class**

Append after existing instance methods (near the end of the class body, before the module's `__main__` block):

```python
    # -- Spec B lookups ---------------------------------------------------

    def bezirk_for(self, lon, lat):
        """Point-in-polygon over 12 Bezirksgrenzen. Returns Bezirk name or None
        for addresses outside Berlin's official Bezirke."""
        fm = self.cfg.bezirksgrenzen_field_map
        pt = Point(lon, lat)
        for props, geom in self.bezirksgrenzen:
            if geom.contains(pt):
                return (props.get(fm["name"]) or "").strip() or None
        return None

    def buergeramt_near(self, lon, lat, radius_m=3000):
        """All Bürgerämter within radius, sorted ascending by distance.
        Each returned dict has `distance_m` added."""
        hits = []
        for o in self.buergeramts:
            d = haversine_m(lon, lat, o["lon"], o["lat"])
            if d <= radius_m:
                hits.append({**o, "distance_m": round(d)})
        hits.sort(key=lambda x: x["distance_m"])
        return hits

    def arbeitsagentur_near(self, lon, lat, radius_m=5000):
        """All curated Arbeitsagentur branches within radius, sorted asc."""
        hits = []
        for o in self.cfg.arbeitsagenturs:
            d = haversine_m(lon, lat, o["lon"], o["lat"])
            if d <= radius_m:
                hits.append({**o, "distance_m": round(d)})
        hits.sort(key=lambda x: x["distance_m"])
        return hits

    def finanzamt_nearest(self, lon, lat):
        """Nearest Finanzamt from the curated list. Returns None if the list
        is empty (config bug)."""
        if not self.cfg.finanzamts:
            return None
        best = min(self.cfg.finanzamts,
                   key=lambda o: haversine_m(lon, lat, o["lon"], o["lat"]))
        d = haversine_m(lon, lat, best["lon"], best["lat"])
        return {**best, "distance_m": round(d)}

    def standesamt_for(self, lon, lat):
        """Address's Bezirk → its assigned Standesamt. Point-in-polygon
        lookup + directory read. Returns None if bezirk_for() returns None
        (address outside Berlin) or if the Bezirk isn't in the dict."""
        bezirk = self.bezirk_for(lon, lat)
        if not bezirk:
            return None
        office = self.cfg.standesamts_by_bezirk.get(bezirk)
        if not office:
            return None
        d = haversine_m(lon, lat, office["lon"], office["lat"])
        return {**office, "distance_m": round(d)}
```

- [ ] **Step 4: Boot the app locally and confirm the preloads succeed**

The dev server on port 8000 needs a restart to pick up the new preloads (backend Python change):

```bash
pkill -f "uvicorn app.main"; sleep 1
nohup .venv/bin/uvicorn app.main:app --port 8000 > /tmp/uvicorn-boot.log 2>&1 &
for i in $(seq 1 15); do
  if curl -sf "http://127.0.0.1:8000/ready" > /dev/null 2>&1; then
    echo "ready after ${i}s"; break
  fi; sleep 1
done
grep -E "Bezirke|Bürgerämter" /tmp/uvicorn-boot.log
```

Expected: log contains `12 Bezirke` and `NN Bürgerämter` (whatever count Berlin publishes).

If the log shows `0 Bezirke` or the boot fails with an HTTPError, the WFS URLs in `berlin.py` need adjustment — probe with:

```bash
curl -s "https://gdi.berlin.de/services/wfs/alkis_bezirke?service=WFS&request=GetCapabilities" | head -50
curl -s "https://gdi.berlin.de/services/wfs/buergeraemter?service=WFS&request=GetCapabilities" | head -50
```

Adjust `_WFS_BEZIRKE` / `_WFS_BUERGERAEMTER` / their `_layer` / `_field_map` values in `berlin.py` until the preload succeeds.

- [ ] **Step 5: Verify the lookup methods with a known address**

```bash
python -c "
from app.cities.berlin import BERLIN
from app.core.index import Index
idx = Index(BERLIN)
print('bezirk_for Kastanienallee 12 area:', idx.bezirk_for(13.3948, 52.5388))
print('bezirk_for Bergmannstraße 27 area:', idx.bezirk_for(13.3952, 52.4888))
print('buergeramt_near Kastanienallee:', len(idx.buergeramt_near(13.3948, 52.5388)))
print('finanzamt_nearest Kastanienallee:', idx.finanzamt_nearest(13.3948, 52.5388))
print('standesamt_for Kastanienallee:', idx.standesamt_for(13.3948, 52.5388))
"
```

Expected:
```
bezirk_for Kastanienallee 12 area: Pankow
bezirk_for Bergmannstraße 27 area: Friedrichshain-Kreuzberg
buergeramt_near Kastanienallee: <N > 0 — some Bürgerämter within 3 km>
finanzamt_nearest Kastanienallee: {'name': 'Finanzamt Prenzlauer Berg', ..., 'distance_m': ...}
standesamt_for Kastanienallee: {'name': 'Standesamt Pankow', ..., 'distance_m': ...}
```

If `bezirk_for` returns None or the wrong Bezirk, the `bezirksgrenzen_field_map["name"]` key is wrong. Probe:

```bash
python -c "
from app.cities.berlin import BERLIN
from app.core.index import Index
idx = Index(BERLIN)
if idx.bezirksgrenzen:
    print('First Bezirk props keys:', list(idx.bezirksgrenzen[0][0].keys()))
    print('First Bezirk props:', idx.bezirksgrenzen[0][0])
"
```

Fix the field-map key and re-verify.

- [ ] **Step 6: Commit**

```bash
git add app/cities/berlin.py app/core/index.py
git commit -m "Preload Bezirksgrenzen + Bürgerämter; add 5 bureaucracy lookups"
```

---

## Task 4: `_walk_minutes` helper + 5 pure `_tier_bureau_*` functions + boundary sweeps

**Files:**
- Modify: `app/core/scorer.py` — add module-level `_walk_minutes` + five tier functions + boundary sweep asserts in `__main__`

**Interfaces:**
- Consumes: `LensTileConfig.thresholds` dict shape `{"green_min", "amber_min"}` from Task 2
- Produces:
  - `_walk_minutes(dist_m: float) -> float` — module-level helper
  - `_tier_buergeramt(offices: list, t: dict) -> dict` — dict with `tier, rule, numeric`
  - `_tier_finanzamt(office: Optional[dict], t: dict) -> dict`
  - `_tier_standesamt(office: Optional[dict], t: dict) -> dict`
  - `_tier_lea(office: dict, t: dict) -> dict`
  - `_tier_arbeitsagentur(offices: list, t: dict) -> dict`

**Notes:** The tier constants `TIER_GREEN`, `TIER_AMBER`, `TIER_RED`, `TIER_UNKNOWN` already exist from Spec A. Reuse them.

- [ ] **Step 1: Locate the existing tier constants in `scorer.py`**

```bash
grep -n "^TIER_\|^def _tier_" app/core/scorer.py | head -10
```

The new helper + tier fns land after the last existing `_tier_*` function.

- [ ] **Step 2: Add `_walk_minutes` helper**

Append to `scorer.py` after the existing tier functions:

```python
def _walk_minutes(dist_m: float) -> float:
    """Haversine → estimated walking minutes.
    4.8 km/h walking speed × 1.3 route factor ≈ 62 m/min effective.
    Uniform across bureaucracy tiles."""
    return dist_m / 62
```

- [ ] **Step 3: Add `_tier_buergeramt`**

```python
def _tier_buergeramt(offices: list, t: dict) -> dict:
    """Bürgeramt — nearest of many (Berlin is free choice)."""
    if not offices:
        return {"tier": TIER_UNKNOWN,
                "rule": "Bürgeramt data unavailable",
                "numeric": "no Bürgeramt loaded"}
    nearest = offices[0]
    m = _walk_minutes(nearest["distance_m"])
    within_green = sum(1 for o in offices
                       if _walk_minutes(o["distance_m"]) <= t["green_min"])
    if m <= t["green_min"]:
        return {"tier": TIER_GREEN,
                "rule": f"≥1 Bürgeramt within {t['green_min']} min walk",
                "numeric": (f"{within_green} within {t['green_min']} min · "
                            f"nearest {round(m)} min ({nearest['name']})")}
    if m <= t["amber_min"]:
        return {"tier": TIER_AMBER,
                "rule": f"Bürgeramt {t['green_min']}–{t['amber_min']} min walk",
                "numeric": f"nearest {round(m)} min ({nearest['name']})"}
    return {"tier": TIER_RED,
            "rule": f"no Bürgeramt within {t['amber_min']} min walk",
            "numeric": f"nearest {round(m)} min ({nearest['name']})"}
```

- [ ] **Step 4: Add `_tier_finanzamt`**

```python
def _tier_finanzamt(office: dict, t: dict) -> dict:
    """Finanzamt — nearest single office. `office` is the pre-selected
    nearest from Index.finanzamt_nearest()."""
    if not office:
        return {"tier": TIER_UNKNOWN,
                "rule": "Finanzamt data unavailable",
                "numeric": "no Finanzamt loaded"}
    m = _walk_minutes(office["distance_m"])
    label = office["name"]
    if m <= t["green_min"]:
        return {"tier": TIER_GREEN,
                "rule": f"Finanzamt within {t['green_min']} min walk",
                "numeric": f"{round(m)} min ({label})"}
    if m <= t["amber_min"]:
        return {"tier": TIER_AMBER,
                "rule": f"Finanzamt {t['green_min']}–{t['amber_min']} min walk",
                "numeric": f"{round(m)} min ({label})"}
    return {"tier": TIER_RED,
            "rule": f"Finanzamt > {t['amber_min']} min walk",
            "numeric": f"{round(m)} min ({label})"}
```

- [ ] **Step 5: Add `_tier_standesamt`**

```python
def _tier_standesamt(office: dict, t: dict) -> dict:
    """Standesamt — the pre-assigned office for the address's Bezirk.
    `office` is None only if bezirk_for() returned None (address outside
    Berlin's Bezirksgrenzen)."""
    if not office:
        return {"tier": TIER_UNKNOWN,
                "rule": "Standesamt not determined",
                "numeric": "Address is outside Berlin's Bezirksgrenzen"}
    m = _walk_minutes(office["distance_m"])
    label = office["name"]
    if m <= t["green_min"]:
        return {"tier": TIER_GREEN,
                "rule": f"assigned Standesamt within {t['green_min']} min walk",
                "numeric": f"{round(m)} min ({label})"}
    if m <= t["amber_min"]:
        return {"tier": TIER_AMBER,
                "rule": f"Standesamt {t['green_min']}–{t['amber_min']} min walk",
                "numeric": f"{round(m)} min ({label})"}
    return {"tier": TIER_RED,
            "rule": f"assigned Standesamt > {t['amber_min']} min walk",
            "numeric": f"{round(m)} min ({label})"}
```

- [ ] **Step 6: Add `_tier_lea`**

```python
def _tier_lea(office: dict, t: dict) -> dict:
    """LEA — single central office. `office` includes `distance_m`
    (added by the composer from cfg.lea_office)."""
    if not office or "distance_m" not in office:
        return {"tier": TIER_UNKNOWN,
                "rule": "LEA data unavailable",
                "numeric": "cfg.lea_office malformed"}
    m = _walk_minutes(office["distance_m"])
    label = office["name"]
    if m <= t["green_min"]:
        return {"tier": TIER_GREEN,
                "rule": f"LEA within {t['green_min']} min walk",
                "numeric": f"{round(m)} min ({label})"}
    if m <= t["amber_min"]:
        return {"tier": TIER_AMBER,
                "rule": f"LEA {t['green_min']}–{t['amber_min']} min walk",
                "numeric": f"{round(m)} min ({label})"}
    return {"tier": TIER_RED,
            "rule": f"LEA > {t['amber_min']} min walk",
            "numeric": f"{round(m)} min ({label})"}
```

- [ ] **Step 7: Add `_tier_arbeitsagentur`**

```python
def _tier_arbeitsagentur(offices: list, t: dict) -> dict:
    """Arbeitsagentur — nearest of many (free choice)."""
    if not offices:
        return {"tier": TIER_UNKNOWN,
                "rule": "Arbeitsagentur data unavailable",
                "numeric": "no Arbeitsagentur loaded"}
    nearest = offices[0]
    m = _walk_minutes(nearest["distance_m"])
    within_green = sum(1 for o in offices
                       if _walk_minutes(o["distance_m"]) <= t["green_min"])
    if m <= t["green_min"]:
        return {"tier": TIER_GREEN,
                "rule": f"≥1 Arbeitsagentur within {t['green_min']} min walk",
                "numeric": (f"{within_green} within {t['green_min']} min · "
                            f"nearest {round(m)} min ({nearest['name']})")}
    if m <= t["amber_min"]:
        return {"tier": TIER_AMBER,
                "rule": f"Arbeitsagentur {t['green_min']}–{t['amber_min']} min walk",
                "numeric": f"nearest {round(m)} min ({nearest['name']})"}
    return {"tier": TIER_RED,
            "rule": f"no Arbeitsagentur within {t['amber_min']} min walk",
            "numeric": f"nearest {round(m)} min ({nearest['name']})"}
```

- [ ] **Step 8: Add boundary sweep assertions in the module's `__main__` block**

Locate the existing `if __name__ == "__main__":` block in `scorer.py`. Append after the last Young Family assertion:

```python
    # -- Bureaucracy lens: boundary sweeps (Spec B pure selfcheck) ----------
    from app.cities.berlin import BERLIN as _CFG_BUR
    _TB = {t.key: t.thresholds for t in _CFG_BUR.bureaucracy_lens.tiles}

    # _walk_minutes sanity
    assert _walk_minutes(0)   == 0.0
    assert _walk_minutes(62)  == 1.0
    assert abs(_walk_minutes(930) - 15.0) < 1e-9

    # _tier_buergeramt — nearest of many
    _B930 = [{"name":"BA-A","distance_m":930}]
    _B931 = [{"name":"BA-B","distance_m":931}]
    assert _tier_buergeramt(_B930, _TB["buergeramt"])["tier"] == TIER_GREEN
    assert _tier_buergeramt(_B931, _TB["buergeramt"])["tier"] == TIER_AMBER
    assert _tier_buergeramt([{"name":"X","distance_m":1860}], _TB["buergeramt"])["tier"] == TIER_AMBER
    assert _tier_buergeramt([{"name":"X","distance_m":1861}], _TB["buergeramt"])["tier"] == TIER_RED
    assert _tier_buergeramt([], _TB["buergeramt"])["tier"] == TIER_UNKNOWN

    # _tier_finanzamt — nearest single office (dict, not list)
    assert _tier_finanzamt({"name":"FA","distance_m":930}, _TB["finanzamt"])["tier"] == TIER_GREEN
    assert _tier_finanzamt({"name":"FA","distance_m":931}, _TB["finanzamt"])["tier"] == TIER_AMBER
    assert _tier_finanzamt({"name":"FA","distance_m":1861}, _TB["finanzamt"])["tier"] == TIER_RED
    assert _tier_finanzamt(None, _TB["finanzamt"])["tier"] == TIER_UNKNOWN

    # _tier_standesamt — pre-assigned dict
    assert _tier_standesamt({"name":"SA","distance_m":930}, _TB["standesamt"])["tier"] == TIER_GREEN
    assert _tier_standesamt({"name":"SA","distance_m":931}, _TB["standesamt"])["tier"] == TIER_AMBER
    assert _tier_standesamt({"name":"SA","distance_m":1861}, _TB["standesamt"])["tier"] == TIER_RED
    assert _tier_standesamt(None, _TB["standesamt"])["tier"] == TIER_UNKNOWN

    # _tier_lea — single dict with distance_m
    assert _tier_lea({"name":"LEA","distance_m":930}, _TB["lea"])["tier"] == TIER_GREEN
    assert _tier_lea({"name":"LEA","distance_m":931}, _TB["lea"])["tier"] == TIER_AMBER
    assert _tier_lea({"name":"LEA","distance_m":1861}, _TB["lea"])["tier"] == TIER_RED
    assert _tier_lea(None, _TB["lea"])["tier"] == TIER_UNKNOWN
    assert _tier_lea({"name":"LEA"}, _TB["lea"])["tier"] == TIER_UNKNOWN  # missing distance_m

    # _tier_arbeitsagentur — same shape as buergeramt
    _A930 = [{"name":"AA-A","distance_m":930}]
    _A931 = [{"name":"AA-B","distance_m":931}]
    assert _tier_arbeitsagentur(_A930, _TB["arbeitsagentur"])["tier"] == TIER_GREEN
    assert _tier_arbeitsagentur(_A931, _TB["arbeitsagentur"])["tier"] == TIER_AMBER
    assert _tier_arbeitsagentur([{"name":"X","distance_m":1861}], _TB["arbeitsagentur"])["tier"] == TIER_RED
    assert _tier_arbeitsagentur([], _TB["arbeitsagentur"])["tier"] == TIER_UNKNOWN

    print("scorer.py: bureaucracy tier boundary sweeps OK")
```

- [ ] **Step 9: Run scorer selfcheck; expect PASS**

```bash
python -m app.core.scorer
```

Expected: all existing Young Family OK lines + `scorer.py: bureaucracy tier boundary sweeps OK`.

- [ ] **Step 10: Commit**

```bash
git add app/core/scorer.py
git commit -m "Add bureaucracy tier fns + walk-minutes helper + boundary sweeps"
```

---

## Task 5: `bureaucracy_lens` composer + `_sources_for` extension + composition asserts

**Files:**
- Modify: `app/core/scorer.py` — add composer function + extend `_sources_for` mapping + composition asserts in `__main__`

**Interfaces:**
- Consumes: five `_tier_bureau_*` functions from Task 4; `_lens_provenance` and `_sources_for` from Spec A; `cfg.bureaucracy_lens`, `cfg.lea_office` from Task 2; Index methods from Task 3
- Produces:
  - `bureaucracy_lens(cfg, index, lon: float, lat: float) -> dict` — composer
  - Extended `_sources_for` mapping with 5 new tile keys → attribution lookup
  - Output shape: `{"slug", "label", "audience", "tiles": [5 dicts], "provenance": str}`; each tile is `{key, label, icon, tier, rule, numeric, caveat, sources}`

- [ ] **Step 1: Extend `_sources_for` with bureaucracy tile keys**

Locate `_sources_for(cfg, key, tier)` in `scorer.py`. In the `mapping = {...}` dict, add the five new keys before the closing `}`:

```python
        # Spec B — Bureaucracy lens
        "buergeramt":     [attr.get("buergeramt")],
        "finanzamt":      [attr.get("finanzamt")],
        "standesamt":     [attr.get("standesamt"), attr.get("bezirksgrenzen")],
        "lea":            [attr.get("lea")],
        "arbeitsagentur": [attr.get("arbeitsagentur")],
```

(Standesamt cites both the office directory AND the Bezirksgrenzen source, because the assignment depends on both.)

- [ ] **Step 2: Add the composer at module level**

Append after the last `_tier_bureau_*` function:

```python
def bureaucracy_lens(cfg, index, lon: float, lat: float) -> dict:
    """Assemble 5 tile results for one address. Pure — no I/O on the hot path.

    Reads preloaded data from Index (Bezirksgrenzen, Bürgerämter) and
    curated data from CityConfig (Finanzamt / Standesamt / Arbeitsagentur
    / LEA directories). No external fetches — bureaucracy is deterministic
    (same inputs → byte-for-byte identical output).
    """
    lens = cfg.bureaucracy_lens
    thresholds = {t.key: t.thresholds for t in lens.tiles}
    tile_meta  = {t.key: (t.label, t.icon, t.caveat) for t in lens.tiles}

    buergeramts    = index.buergeramt_near(lon, lat)
    finanzamt      = index.finanzamt_nearest(lon, lat)
    standesamt     = index.standesamt_for(lon, lat)             # None if outside Berlin
    lea            = _with_distance(cfg.lea_office, lon, lat)   # LEA is a single point
    arbeitsagentur = index.arbeitsagentur_near(lon, lat)

    results = [
        ("buergeramt",     _tier_buergeramt(buergeramts, thresholds["buergeramt"])),
        ("finanzamt",      _tier_finanzamt(finanzamt, thresholds["finanzamt"])),
        ("standesamt",     _tier_standesamt(standesamt, thresholds["standesamt"])),
        ("lea",            _tier_lea(lea, thresholds["lea"])),
        ("arbeitsagentur", _tier_arbeitsagentur(arbeitsagentur, thresholds["arbeitsagentur"])),
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


def _with_distance(office: dict, lon: float, lat: float) -> dict:
    """Return office dict with `distance_m` added. Used for the single-point
    LEA (cfg.lea_office doesn't come pre-decorated with distance)."""
    if not office or "lon" not in office or "lat" not in office:
        return None
    d = haversine_m(lon, lat, office["lon"], office["lat"])
    return {**office, "distance_m": round(d)}
```

- [ ] **Step 3: Add composition asserts in `__main__`**

Append below the boundary sweeps in the same `if __name__ == "__main__":` block:

```python
    # -- Bureaucracy composer — determinism, outside-Berlin, all-empty ------
    class _StubIndex:
        def __init__(self, bezirk="Pankow"):
            self._bezirk = bezirk
        def bezirk_for(self, lon, lat): return self._bezirk
        def buergeramt_near(self, lon, lat, radius_m=3000):
            return [{"name":"BA-Test","distance_m":500}]
        def arbeitsagentur_near(self, lon, lat, radius_m=5000):
            return [{"name":"AA-Test","distance_m":800}]
        def finanzamt_nearest(self, lon, lat):
            return {"name":"FA-Test","distance_m":600}
        def standesamt_for(self, lon, lat):
            if not self._bezirk: return None
            return {"name": f"Standesamt {self._bezirk}","distance_m":700}

    # Determinism — two identical calls must produce byte-equal dicts.
    r_a = bureaucracy_lens(_CFG_BUR, _StubIndex(), 13.4, 52.5)
    r_b = bureaucracy_lens(_CFG_BUR, _StubIndex(), 13.4, 52.5)
    assert r_a == r_b, "bureaucracy_lens must be deterministic"

    # All 5 tiles present, keys in expected order.
    _keys = [t["key"] for t in r_a["tiles"]]
    assert _keys == ["buergeramt","finanzamt","standesamt","lea","arbeitsagentur"], _keys

    # Response shape stability (every tile has all 8 keys).
    for t in r_a["tiles"]:
        assert set(t.keys()) == {"key","label","icon","tier","rule","numeric","caveat","sources"}, t
    assert r_a["slug"] == "bureaucracy"
    assert r_a["label"] == "Bureaucracy"

    # Caveat pass-through
    _caveats = {t.key: t.caveat for t in _CFG_BUR.bureaucracy_lens.tiles}
    assert _caveats["buergeramt"], "Bürgeramt tile must carry a caveat"
    assert "Steuernummer" in _caveats["finanzamt"]
    assert "Specialty branches" in _caveats["lea"]
    assert _caveats["standesamt"] == "" and _caveats["arbeitsagentur"] == ""

    # Outside-Berlin — bezirk_for returns None → Standesamt goes unknown
    r_out = bureaucracy_lens(_CFG_BUR, _StubIndex(bezirk=None), 13.4, 52.5)
    _by_out = {t["key"]: t["tier"] for t in r_out["tiles"]}
    assert _by_out["standesamt"] == "unknown", _by_out

    # Empty inputs → red, not unknown (for the "list of many" tiles)
    class _StubEmpty(_StubIndex):
        def buergeramt_near(self, lon, lat, radius_m=3000): return []
        def arbeitsagentur_near(self, lon, lat, radius_m=5000): return []
    r_empty = bureaucracy_lens(_CFG_BUR, _StubEmpty(), 13.4, 52.5)
    _by_empty = {t["key"]: t["tier"] for t in r_empty["tiles"]}
    # Empty preloaded list → UNKNOWN (list "unavailable" from preload failure)
    # For "list of many" tiles, empty-list is genuinely ambiguous — the tier
    # function goes unknown when it can't find any office. This matches Spec A
    # semantics for playground-when-both-sources-fail.
    assert _by_empty["buergeramt"] == "unknown"
    assert _by_empty["arbeitsagentur"] == "unknown"

    # Provenance: for the determinism case (all non-unknown), provenance must
    # cite the sources of all 5 tiles' contributed attribution keys.
    assert "Bürgerämter" in r_a["provenance"], r_a["provenance"]
    assert "Finanzamt" in r_a["provenance"] or "Finanzämter" in r_a["provenance"]

    print("scorer.py: bureaucracy composer OK")
```

- [ ] **Step 4: Run scorer selfcheck; expect PASS**

```bash
python -m app.core.scorer
```

Expected: boundary sweeps OK + `scorer.py: bureaucracy composer OK`.

- [ ] **Step 5: Commit**

```bash
git add app/core/scorer.py
git commit -m "Add bureaucracy_lens composer + _sources_for extension"
```

---

## Task 6: Wire bureaucracy_lens into `/api/lookup`

**Files:**
- Modify: `app/routes/lookup.py` — add a second try/except catch-all next to the existing young_family_lens block; response gains `lens.bureaucracy`

**Interfaces:**
- Consumes: `scorer.bureaucracy_lens` from Task 5 (already imported via `from app.core import scorer` from Spec A's Task 6)
- Produces: `/api/lookup` response's `lens` key now has two siblings — `young_family` (existing) and `bureaucracy` (new)

- [ ] **Step 1: Locate the existing young_family_lens block in `lookup.py`**

```bash
grep -n "young_family_lens\|\"lens\"" app/routes/lookup.py
```

The new block lands IMMEDIATELY AFTER the existing `young_family_lens` try/except, BEFORE the response dict is constructed.

- [ ] **Step 2: Add the bureaucracy_lens try/except block**

Insert after the existing `except Exception as e: lens_yf = {...}` block:

```python
    # --- Bureaucracy lens (Spec B) ----------------------------------------
    # Deterministic — no external fetches on the hot path. Data is either
    # preloaded on Index (Bezirksgrenzen, Bürgerämter) or read from
    # CityConfig curated directories (Finanzamt, Standesamt, Arbeitsagentur,
    # LEA). Wrapped in try/except purely to isolate programming bugs
    # (never break /api/lookup for lens issues, §14.7).
    try:
        lens_bur = scorer.bureaucracy_lens(cfg, index, lon, lat)
    except Exception as e:
        lens_bur = {"slug": "bureaucracy",
                    "error": f"{type(e).__name__}: {e}"}
```

- [ ] **Step 3: Modify the response `"lens"` key to include both lenses**

Find the existing line in the response dict:
```python
        "lens":         {"young_family": lens_yf},
```

Change it to:
```python
        "lens":         {"young_family": lens_yf, "bureaucracy": lens_bur},
```

- [ ] **Step 4: Restart the dev server and verify the response**

```bash
pkill -f "uvicorn app.main"; sleep 1
nohup .venv/bin/uvicorn app.main:app --port 8000 > /tmp/uvicorn-boot.log 2>&1 &
for i in $(seq 1 15); do
  if curl -sf "http://127.0.0.1:8000/ready" > /dev/null 2>&1; then
    echo "ready after ${i}s"; break
  fi; sleep 1
done

curl -s "http://127.0.0.1:8000/api/lookup?address=Kastanienallee+12%2C+10435" \
  | python3 -c "
import json, sys
d = json.load(sys.stdin)
lens = d.get('lens') or {}
print('lens keys:', list(lens.keys()))
bur = lens.get('bureaucracy') or {}
print('bureaucracy present:', bool(bur))
print('bureaucracy tiles count:', len(bur.get('tiles') or []))
print('bureaucracy slug:', bur.get('slug'))
print('provenance sample:', (bur.get('provenance') or '')[:150])
print()
print('Young Family still present:', bool(lens.get('young_family')))
print('YF tiles count:', len((lens.get('young_family') or {}).get('tiles') or []))"
```

Expected:
```
lens keys: ['young_family', 'bureaucracy']
bureaucracy present: True
bureaucracy tiles count: 5
bureaucracy slug: bureaucracy
provenance sample: <non-empty string with at minimum Bürgerämter>
Young Family still present: True
YF tiles count: 7
```

- [ ] **Step 5: Verify one bureaucracy tile in detail**

```bash
curl -s "http://127.0.0.1:8000/api/lookup?address=Kastanienallee+12%2C+10435" \
  | python3 -c "
import json, sys
tiles = json.load(sys.stdin)['lens']['bureaucracy']['tiles']
standesamt = [t for t in tiles if t['key']=='standesamt'][0]
print(json.dumps(standesamt, indent=2, ensure_ascii=False))"
```

Expected: dict with keys `{key, label, icon, tier, rule, numeric, caveat, sources}`. The `numeric` field must contain `"Pankow"` (Kastanienallee 12 is in Pankow Bezirk).

- [ ] **Step 6: Verify graceful degradation — temporarily break the composer**

In `app/core/scorer.py`, at the top of `bureaucracy_lens(...)`, add:
```python
    raise RuntimeError("temp — verify catch-all")
```

Restart the server, then:

```bash
pkill -f "uvicorn app.main"; sleep 1
nohup .venv/bin/uvicorn app.main:app --port 8000 > /tmp/uvicorn-boot.log 2>&1 &
for i in $(seq 1 15); do
  if curl -sf "http://127.0.0.1:8000/ready" > /dev/null 2>&1; then
    echo "ready after ${i}s"; break
  fi; sleep 1
done

curl -s "http://127.0.0.1:8000/api/lookup?address=Kastanienallee+12%2C+10435" \
  | python3 -c "
import json, sys
d = json.load(sys.stdin)
bur = (d.get('lens') or {}).get('bureaucracy') or {}
yf  = (d.get('lens') or {}).get('young_family') or {}
print('bureaucracy error:', bur.get('error'))
print('young_family intact (tiles):', len(yf.get('tiles') or []))
print('rest of lookup intact:', 'address' in d and 'catchment' in d)"
```

Expected:
```
bureaucracy error: RuntimeError: temp — verify catch-all
young_family intact (tiles): 7
rest of lookup intact: True
```

Confirms two-lens independence.

**REVERT the `raise` in `scorer.py` before proceeding.** Restart the server.

- [ ] **Step 7: Commit**

```bash
git add app/routes/lookup.py
git commit -m "Wire bureaucracy_lens into /api/lookup (independent try/except)"
```

---

## Task 7: Live selfcheck for the bureaucracy lens

**Files:**
- Modify: `app/selfcheck.py` — extend `run_live_selfcheck()` with a bureaucracy assertion block

**Interfaces:**
- Consumes: `scorer.bureaucracy_lens` (already imported from Spec A), `Index.bezirk_for` from Task 3
- Produces: `python -m app.selfcheck` now runs bureaucracy assertions on Kastanienallee 12 + Bergmannstraße 27

- [ ] **Step 1: Locate the existing young_family lens block in `run_live_selfcheck`**

```bash
grep -n "young_family lens asserts OK\|→ live selfcheck OK" app/selfcheck.py
```

The new block lands immediately BEFORE the closing `print("→ live selfcheck OK")` (which sits at the end of the function), and AFTER the young_family_lens block.

- [ ] **Step 2: Add the bureaucracy assertion block**

Insert immediately after the young_family lens block's `print("  young_family lens asserts OK")` line:

```python
    # -- Bureaucracy lens ---------------------------------------------------
    # Two known-good addresses cover Bezirk-based assignment (Pankow +
    # Friedrichshain-Kreuzberg) and distance-based tier variation.
    # Kastanienallee 12 is reused from geocode `geo` above.
    lens_bur = scorer.bureaucracy_lens(cfg, idx, geo["lon"], geo["lat"])
    assert len(lens_bur["tiles"]) == 5, f"expected 5 tiles, got {len(lens_bur['tiles'])}"
    _bk = [t["key"] for t in lens_bur["tiles"]]
    assert _bk == ["buergeramt","finanzamt","standesamt","lea","arbeitsagentur"], _bk
    for t in lens_bur["tiles"]:
        assert t["label"] and t["rule"], t
        assert t["tier"] in {"green","amber","red","unknown"}, t
    _by_bur = {t["key"]: t for t in lens_bur["tiles"]}
    # Kastanienallee 12 is in Pankow — Standesamt tile numeric must reference Pankow
    assert idx.bezirk_for(geo["lon"], geo["lat"]) == "Pankow", \
        f"expected Pankow, got {idx.bezirk_for(geo['lon'], geo['lat'])!r}"
    assert "Pankow" in _by_bur["standesamt"]["numeric"], _by_bur["standesamt"]
    # Caveats verbatim
    assert "PLZ" in _by_bur["buergeramt"]["caveat"], _by_bur["buergeramt"]["caveat"]
    assert "Steuernummer" in _by_bur["finanzamt"]["caveat"], _by_bur["finanzamt"]["caveat"]
    assert "Specialty branches" in _by_bur["lea"]["caveat"], _by_bur["lea"]["caveat"]
    # Provenance non-empty; cites at minimum Bürgerämter
    assert "Bürgerämter" in lens_bur["provenance"], lens_bur["provenance"]
    # Determinism guard — two calls must produce equal results
    lens_bur_2 = scorer.bureaucracy_lens(cfg, idx, geo["lon"], geo["lat"])
    assert lens_bur == lens_bur_2, "bureaucracy_lens must be deterministic"

    # -- Bergmannstraße 27 (Friedrichshain-Kreuzberg Bezirk) ---------------
    berg = idx.geocode("Bergmannstraße", "27", "10961")
    if not berg:
        print("  Bergmannstraße 27 geocode failed — skipped Bezirk assignment check")
    else:
        assert idx.bezirk_for(berg["lon"], berg["lat"]) == "Friedrichshain-Kreuzberg", \
            f"expected Friedrichshain-Kreuzberg, got {idx.bezirk_for(berg['lon'], berg['lat'])!r}"
        lens_bur_b = scorer.bureaucracy_lens(cfg, idx, berg["lon"], berg["lat"])
        _by_b = {t["key"]: t for t in lens_bur_b["tiles"]}
        assert "Friedrichshain-Kreuzberg" in _by_b["standesamt"]["numeric"], _by_b["standesamt"]
        # Kreuzberg is farther from Wedding (LEA) than Pankow is — LEA walk-min > Pankow's.
        # Extract minutes from numeric strings like "35 min (LEA Berlin …)".
        import re as _re
        def _min(s):
            m = _re.search(r"(\d+)\s*min", s)
            return int(m.group(1)) if m else None
        lea_pnk_min  = _min(_by_bur["lea"]["numeric"])
        lea_kbg_min  = _min(_by_b["lea"]["numeric"])
        if lea_pnk_min is not None and lea_kbg_min is not None:
            assert lea_kbg_min >= lea_pnk_min, \
                f"LEA from Kreuzberg ({lea_kbg_min}) should be ≥ from Pankow ({lea_pnk_min})"

    print("  bureaucracy lens asserts OK")
```

- [ ] **Step 3: Run the full app selfcheck; expect PASS**

```bash
python -m app.selfcheck
```

Expected sequence: cities isolation → pure module blocks (scorer + others OK) → live selfcheck prints `young_family lens asserts OK`, then `bureaucracy lens asserts OK`, then `→ live selfcheck OK`.

If a WFS is genuinely unavailable at test time, the existing skip pattern handles it.

- [ ] **Step 4: Commit**

```bash
git add app/selfcheck.py
git commit -m "Add live selfcheck for bureaucracy lens (Pankow + Kreuzberg Bezirks)"
```

---

## Task 8: Frontend — 5 tile SVGs + `.lens-picker` CSS block

**Files:**
- Modify: `web/index.html` — add 5 new SVG entries in the shared `ico = {...}` object (only add keys that don't already exist)
- Modify: `web/static/app.css` — append `.lens-picker` block (4 lines)

**Interfaces:**
- Produces: 5 icon keys accessible via `ico['buergeramt']` etc.; CSS class `.lens-picker` styled for a horizontal flex row of pills

**Notes:** Task 8 is visuals-only. No JS wiring yet. This lets a reviewer approve the visuals independently of the state logic.

- [ ] **Step 1: Locate the `ico = {...}` object**

```bash
grep -n "const ico\s*=\|ico\s*=\s*{" web/index.html web/static/app.js | head
```

- [ ] **Step 2: Check which of the 5 keys already exist**

```bash
grep -nE "^\s*(buergeramt|finanzamt|standesamt|lea|arbeitsagentur)\s*:" web/index.html web/static/app.js
```

Note which keys exist. Only add missing ones in the next step.

- [ ] **Step 3: Add missing SVG entries to `ico = {...}`**

For each of the five keys, add an entry if it doesn't already exist. Use `stroke="currentColor"` so tier color propagates.

```javascript
buergeramt: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M3 21V9l9-6 9 6v12"/><path d="M9 13h6v8H9z"/><path d="M9 17h6"/></svg>`,
finanzamt: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3h9l3 3v15H6z"/><path d="M15 3v3h3"/><path d="M9 12h6M9 16h4"/></svg>`,
standesamt: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4 4h9v16H4z"/><path d="M4 4l4.5 3 4.5-3"/><circle cx="17" cy="15" r="3"/><circle cx="19.5" cy="17.5" r="3"/></svg>`,
lea: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="3" width="14" height="18" rx="1"/><circle cx="12" cy="10" r="2.5"/><path d="M8 15h8"/><path d="M8 18h8"/></svg>`,
arbeitsagentur: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4 7h16v13H4z"/><path d="M9 7V5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2"/><path d="M4 12h16"/></svg>`,
```

- [ ] **Step 4: Append the `.lens-picker` CSS block to `web/static/app.css`**

At the end of the file (or after the existing lens styling from Spec A):

```css
/* --- Lens picker (Spec B) --------------------------------------------- */
.lens-picker{
  display:flex; flex-wrap:wrap; gap:.6em;
  margin-bottom:1em;
}
.lens-picker .pill-btn{ font-size:.85em; }
```

- [ ] **Step 5: Visual smoke test**

Reload `http://127.0.0.1:8000/` in the browser. Nothing looks different yet (no picker HTML added). Confirm no console errors and the app still loads.

If the browser dev tools show ico entries loaded, run in the console:
```javascript
console.log(Object.keys(ico));
```
Expect to see the 5 new keys in the array.

- [ ] **Step 6: Commit**

```bash
git add web/index.html web/static/app.css
git commit -m "Add bureaucracy tile SVGs + .lens-picker CSS"
```

---

## Task 9: Frontend — lens picker state + render updates

**Files:**
- Modify: `web/static/app.js` — add `LM_ACTIVE_KEY` constant + 4 functions (`getActiveLens`, `setActiveLens`, `renderLensPicker`, `isAnyLensAvailable`); update `renderLensSingle`, `renderLensCompare`, `renderAllPanels` (or equivalent) to read the active lens; add delegated click handler

**Interfaces:**
- Consumes: `#life-mode-toggle` DOM element + `renderLensTile`/`renderLensDot`/`escapeHtml`/`renderAllPanels` from Spec A
- Produces:
  - Module-level constants: `LM_ACTIVE_KEY = 'berlin-lens-active-v1'`, `LM_DEFAULT_LENS = 'young_family'`
  - `getActiveLens() -> 'young_family' | 'bureaucracy'`
  - `setActiveLens(slug)` — updates picker state, writes localStorage, triggers `renderAllPanels()`
  - `renderLensPicker(activeSlug) -> string` — HTML for the picker
  - `isAnyLensAvailable(addr) -> boolean` — checks both lenses for `.error`
  - Updated `renderLensSingle(addr)` and `renderLensCompare(addresses)` — read `addr.lens[getActiveLens()]` instead of hardcoded `young_family`

- [ ] **Step 1: Add module-level constants**

Near the top of `app.js`, alongside the existing `LM_STATE_KEY` and `LM_SEEN_KEY`:

```javascript
const LM_ACTIVE_KEY   = 'berlin-lens-active-v1';       // "young_family"|"bureaucracy"
const LM_DEFAULT_LENS = 'young_family';                // default for first-time users
```

- [ ] **Step 2: Add `getActiveLens` and `setActiveLens`**

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
  // Update picker button states across any rendered picker in the DOM.
  document.querySelectorAll('.lens-picker [data-lens]').forEach(btn => {
    const on = btn.dataset.lens === slug;
    btn.classList.toggle('pill-btn-brand', on);
    btn.setAttribute('aria-selected', on ? 'true' : 'false');
  });
  if (typeof renderAllPanels === 'function') renderAllPanels();
}
```

- [ ] **Step 3: Add `renderLensPicker`**

```javascript
function renderLensPicker(activeSlug) {
  const active = activeSlug || getActiveLens();
  const yfCls  = active === 'young_family' ? 'pill-btn pill-btn-brand' : 'pill-btn';
  const bCls   = active === 'bureaucracy'  ? 'pill-btn pill-btn-brand' : 'pill-btn';
  const yfSel  = active === 'young_family' ? 'true'  : 'false';
  const bSel   = active === 'bureaucracy'  ? 'true'  : 'false';
  return `
    <div class="lens-picker" role="tablist" aria-label="Choose a lens">
      <button class="${yfCls}" data-lens="young_family"
              role="tab" aria-selected="${yfSel}">Young Family (0–6)</button>
      <button class="${bCls}" data-lens="bureaucracy"
              role="tab" aria-selected="${bSel}">Bureaucracy</button>
    </div>
  `;
}
```

- [ ] **Step 4: Add `isAnyLensAvailable`**

```javascript
function isAnyLensAvailable(addr) {
  const lens = (addr && addr.lens) || {};
  const y = lens.young_family;
  const b = lens.bureaucracy;
  return (y && !y.error) || (b && !b.error);
}
```

- [ ] **Step 5: Add the delegated click handler**

Inside `initLifeMode()` (existing from Spec A), append at the end:

```javascript
  // Delegate picker clicks. One handler covers picker instances rendered
  // in either the single-address view or the compare view.
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('.lens-picker [data-lens]');
    if (btn) setActiveLens(btn.dataset.lens);
  });
```

- [ ] **Step 6: Update `renderLensSingle(addr)` to read the active lens**

Find the existing `renderLensSingle(addr)` (from Spec A). Replace the body so it reads `addr.lens[getActiveLens()]` and prepends the picker.

Locate the existing function and change:

```javascript
// Was (Spec A):
function renderLensSingle(addr) {
  const lens = addr && addr.lens && addr.lens.young_family;
  if (!lens || lens.error) {
    return `<div class="lens-empty">Lens unavailable for this address.</div>`;
  }
  // ... build tilesHtml ...
  return `<div class="lens-view">…</div>`;
}
```

To (Spec B):

```javascript
function renderLensSingle(addr) {
  const active = getActiveLens();
  const lens = addr && addr.lens && addr.lens[active];
  if (!lens || lens.error) {
    return `${renderLensPicker(active)}
            <div class="lens-empty">Lens unavailable for this address.</div>`;
  }
  const tilesHtml = lens.tiles.map(renderLensTile).join('');
  const prov = lens.provenance
    ? `<footer class="lens-provenance">${escapeHtml(lens.provenance)}</footer>`
    : '';
  return `
    ${renderLensPicker(active)}
    <div class="lens-view-body">
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

- [ ] **Step 7: Update `renderLensCompare(addresses)` to read the active lens**

Find the existing `renderLensCompare(addresses)` from Spec A. Replace the body similarly:

```javascript
function renderLensCompare(addresses) {
  const active = getActiveLens();
  if (!addresses || !addresses.length) return '';
  const first = addresses.find(a => a && a.lens && a.lens[active] && !a.lens[active].error);
  if (!first) {
    return `${renderLensPicker(active)}
            <div class="lens-empty">Lens unavailable for the current addresses.</div>`;
  }
  const rowSpec = first.lens[active].tiles;   // 7 rows if young_family, 5 if bureaucracy
  const header = `
    <div class="lens-compare-row lens-compare-head">
      <div class="lens-compare-rowlabel"></div>
      ${addresses.map(a => `
        <div class="lens-compare-collabel">${escapeHtml(
          (a && a.shortLabel) ||
          (a && a.address && a.address.street) ||
          '—')}</div>
      `).join('')}
    </div>`;
  const rows = rowSpec.map(spec => {
    const cells = addresses.map(a => {
      const t = a && a.lens && a.lens[active] && !a.lens[active].error
              ? a.lens[active].tiles.find(x => x.key === spec.key)
              : null;
      return `<div class="lens-compare-cellwrap">${renderLensDot(t)}</div>`;
    }).join('');
    return `
      <div class="lens-compare-row">
        <div class="lens-compare-rowlabel">${escapeHtml(spec.label)}</div>
        ${cells}
      </div>`;
  }).join('');
  return `${renderLensPicker(active)}
          <div class="lens-compare">${header}${rows}</div>`;
}
```

- [ ] **Step 8: Update `renderAllPanels` (or equivalent) to disable the Life Mode toggle when both lenses error**

Find the current `renderAllPanels()` (from Spec A Task 10). Inside its loop over address panels, before the branch that renders lens content, add a check: if `!isAnyLensAvailable(addr)`, the Life Mode toggle in the header gets the `disabled` treatment (matches Spec A's "single-lens error → toggle greyed" behavior, extended to require BOTH lenses to fail before disabling).

The specific edit depends on how `renderAllPanels()` sits after Spec A's Task 10; the general shape:

```javascript
function renderAllPanels() {
  const onLife = document.body.classList.contains('life-mode');
  const toggle = document.getElementById('life-mode-toggle');
  // ... existing per-address panel rendering ...
  // For the toggle's disabled state, check whichever address is currently focused
  // (or the first loaded address if compare view is inactive).
  const focused = /* look up the currently-focused address as existing code does */;
  if (toggle && focused && !isAnyLensAvailable(focused)) {
    toggle.setAttribute('disabled', 'true');
    toggle.setAttribute('title', 'Lens unavailable for this address');
  } else if (toggle) {
    toggle.removeAttribute('disabled');
    toggle.removeAttribute('title');
  }
}
```

If the current `renderAllPanels` shape doesn't map to this cleanly, add a minimal call to `isAnyLensAvailable(addr)` in whatever function looks up the focused address and prepares to render the tile grid — the goal is that BOTH lenses erroring on the focused address should visually disable the header toggle. Keep the Spec A single-lens-error path (which still greys the toggle when only `young_family` errored, if Spec A did that) but the correct behavior is: **toggle disabled iff both lenses error**.

- [ ] **Step 9: Browser QA — picker click, sticky reload, compare-view switch**

Reload `http://127.0.0.1:8000/` in a fresh Incognito window. Enter Kastanienallee 12, 10435. Toggle Life Mode ON.

1. Picker appears above the tile grid with two pills. Young Family pill is `pill-btn-brand` (active).
2. 7 tiles render below the picker.
3. Click "Bureaucracy" pill. It becomes `pill-btn-brand`; Young Family loses brand styling. 5 tiles render.
4. Open DevTools → Application → Local Storage. Confirm `berlin-lens-active-v1 == 'bureaucracy'`.
5. Reload page. Life Mode still ON, active lens still Bureaucracy, 5 tiles still visible.
6. Click Young Family — 7 tiles return, localStorage flips.
7. Add a second address, open compare view. Toggle Life Mode ON. Picker appears above the matrix; active lens applies.
8. Click Bureaucracy in compare view. Matrix re-renders as 5×N. Click Young Family — 7×N.

- [ ] **Step 10: Commit**

```bash
git add web/static/app.js
git commit -m "Add lens picker state (getActiveLens/setActiveLens) + render updates"
```

---

## Task 10: Frontend live-browser QA checklist (§14.12)

**Files:**
- No edits — pure manual QA against the running app.

**Interfaces:** none — this task consumes the entire feature.

**Notes:** Ten checklist items lifted from Spec B's testing section. Do all ten in order on a fresh browser profile.

- [ ] **Step 1: Initial state.** Fresh Incognito window at `http://127.0.0.1:8000/`. Life Mode toggle visible + pulsing (first-visit behavior from Spec A). Load address Kastanienallee 12, 10435. Toggle Life Mode ON. Picker appears with Young Family selected (default). 7 tiles below. PASS.

- [ ] **Step 2: Picker click — switch to Bureaucracy.** Click "Bureaucracy" pill. It becomes `pill-btn-brand`; the other loses brand styling. 5 tiles render. In DevTools Console: `localStorage.getItem('berlin-lens-active-v1') === 'bureaucracy'` returns true. PASS.

- [ ] **Step 3: State persistence for active lens.** Reload page. Life Mode still ON, active lens still Bureaucracy, 5 tiles still visible. PASS.

- [ ] **Step 4: Switch back to Young Family.** Click the pill; 7 tiles return. `localStorage.getItem('berlin-lens-active-v1') === 'young_family'`. PASS.

- [ ] **Step 5: Compare view — Bureaucracy.** Add Kastanienallee 12 to Compare (+ Add to Compare pill). Enter Bergmannstraße 27, 10961. Add that to Compare too. Navigate to Compare view. Toggle Life Mode ON with active=bureaucracy. Verify 5-row × 2-col dot matrix. Hover a dot → tooltip (title attribute) contains rule + numeric. PASS.

- [ ] **Step 6: Compare view — switch lens live.** In compare view, click "Young Family" pill. Matrix re-renders as 7×2. Click "Bureaucracy" back — 5×2. No page reload. PASS.

- [ ] **Step 7: Standesamt correctness at address.** In single-address view, verify Bureaucracy Standesamt tile numeric contains "Pankow" for Kastanienallee 12. Verify it contains "Friedrichshain-Kreuzberg" for Bergmannstraße 27. PASS.

- [ ] **Step 8: Bürgeramt caveat visible.** In single-address view with Life Mode ON + Bureaucracy active, the Bürgeramt tile shows the italic caveat text (e.g. *"Berlin lets you book any Bürgeramt for Anmeldung — not restricted by PLZ."*) at the bottom of the tile. PASS.

- [ ] **Step 9: Outage state — one lens errors.** In `app/core/scorer.py`, at the top of `bureaucracy_lens(...)`, add `raise RuntimeError("qa test")`. Restart the server:

```bash
pkill -f "uvicorn app.main"; sleep 1
nohup .venv/bin/uvicorn app.main:app --port 8000 > /tmp/uvicorn-boot.log 2>&1 &
for i in $(seq 1 15); do
  if curl -sf "http://127.0.0.1:8000/ready" > /dev/null 2>&1; then break; fi
  sleep 1
done
```

Reload the app. Load Kastanienallee 12. Toggle Life Mode ON. Young Family pill still works. Click Bureaucracy pill → shows `.lens-empty` "Lens unavailable" message. Header toggle is still enabled (Young Family works). **Revert the `raise` and restart.** PASS.

- [ ] **Step 10: Both lenses error.** Add the same `raise RuntimeError("qa test")` to BOTH `young_family_lens()` AND `bureaucracy_lens()` at their function tops. Restart the server. Reload the app. Load Kastanienallee 12. The Life Mode toggle in the header is disabled with hover title "Lens unavailable for this address." Clicking is a no-op. **Revert both raises and restart.** PASS.

- [ ] **Step 11: Clean up ephemeral screenshots per §14.12.**

- [ ] **Step 12: Mark ship-ready with an empty commit**

```bash
git commit --allow-empty -m "Bureaucracy lens: live-browser QA passed (Spec B shipped)"
```

---

## Self-Review

**1. Spec coverage:**
- Every Spec B scope-in item mapped: 5-tile lens (Tasks 2 + 4), uniform 15/30 min thresholds (Task 4), Bezirk-assigned Standesamt (Tasks 3 + 5), curated federal directories (Task 2), lens picker with sticky state (Tasks 8 + 9), tile schema unchanged (Tasks 4 + 5 + 9), caveats on 3 tiles (Task 2 + selfcheck asserts in Task 5 + 7), pure + live selfcheck (Tasks 4 + 5 + 7), no live per-request fetches (Task 3 preload + Task 5 pure composer), independent lens error handling in `/api/lookup` (Task 6).
- Locked-decision threshold values (930m/1861m boundaries, 15/30 min tiers, `_walk_minutes = dist_m / 62`) all landed in Task 4 tier fns and boundary sweeps.
- Non-goals honored — no OSM Overpass on the hot path, no new endpoint, no URL fields on tiles, no transit-time API.

**2. Placeholder scan:** Clean. Every code block is complete and runnable. No "TBD" / "TODO" / vague step. The five tier functions and composer are all spelled out. Curated federal directories are populated with concrete coordinates + addresses (implementer must verify against public references at implementation time — that's an actionable step, not a placeholder).

**3. Type consistency across tasks:**
- `bureaucracy_lens` field name matches across `base.py` (Task 1 definition), `berlin.py` (Task 2 assignment), and `lookup.py` (Task 6 access).
- `LensTileConfig.thresholds` dict-key names in Task 2 (`green_min`, `amber_min`) match Task 4 tier fn readers (`t["green_min"]`, `t["amber_min"]`).
- Composer signature `bureaucracy_lens(cfg, index, lon, lat)` matches Task 5 definition and Task 6 call site.
- Tile output keys `{key, label, icon, tier, rule, numeric, caveat, sources}` set in Task 5 composer; read by Task 9's frontend `renderLensSingle` / `renderLensCompare`.
- Index methods `bezirk_for` / `buergeramt_near` / `arbeitsagentur_near` / `finanzamt_nearest` / `standesamt_for` defined in Task 3 and consumed exactly in Task 5.
- `_sources_for` mapping in Task 5 keys against `cfg.attribution` entries added in Task 2 (`bezirksgrenzen`, `buergeramt`, `finanzamt`, `standesamt`, `lea`, `arbeitsagentur`).
- `LM_ACTIVE_KEY = 'berlin-lens-active-v1'` matches spec Locked Decisions.

No inconsistencies. Plan is ready to execute.
