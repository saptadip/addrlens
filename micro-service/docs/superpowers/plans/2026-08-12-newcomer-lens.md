# Newcomer / Relocation Lens Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the Newcomer (0–90 days) lens — a 6-tile Life-Mode view over an address's first-90-days readiness for an English-speaking expat — matching Spec E at `docs/superpowers/specs/2026-08-12-newcomer-lens-design.md`.

**Architecture:** Server-side tier logic in `v0.1/app/core/scorer.py` reads data already resident in `Index` (OSM local snapshot, VBB coords, GESIx polygons) — no new WFS live-fetches on the hot path. The lens folds into every `/api/lookup` response under `lens.newcomer`, next to the existing `lens.young_family` block. Six insight templates land in `v0.1/inference/templates/` behind the existing `POST /api/card_insight` dispatcher (`_CARD_CONTEXT_BUILDERS` extension only, no new route). Frontend picks the new lens up automatically through the existing `LIFE_MODE_LENSES` registry — one entry, no toggle code changes.

**Tech Stack:** Python 3.11+, FastAPI, shapely, httpx (existing app deps only — no new deps). pyosmium in the refresh script (already present). Vanilla JS + hand-authored CSS (no build step, no bundler, no npm).

**Implementation surface:** `v0.1/` tree only. The `micro-service/` (live-Overpass) build is out of scope per Spec E.

## Global Constraints

Inherited from Spec A (Young Family) and Spec D (Clickable Lens Tiles):

- **Frozen dataclasses, no defaults on `CityConfig` fields.** `newcomer_lens: LensConfig` is required; missing values fail at import (per Ship-B rule).
- **`app/core/*` modules are pure.** No I/O, no live WFS in the composer path. Data flows in as arguments from the `Index` built at boot.
- **Per-city facts live in `app/cities/<slug>.py`.** No hard-coded Berlin values inside `core/`.
- **BOD-first, OSM as fallback / supplement.** Every tile carries `source: "bod" | "osm"` on its features; provenance strings come from `cfg.attribution[<key>]` verbatim — never fabricated.
- **Testing without pytest.** Every module carries an `if __name__ == "__main__"` block with `assert` statements. Live asserts extend `app.selfcheck` orchestrator.
- **Threshold convention:** every boundary is inclusive on the greener side (1500m green, 1500.01m amber; 800m green, 800.01m amber).
- **Insight templates follow `<card>_insight` naming convention.** Six new template files, six new `TEMPLATES` rows in `inference/main.py`, six new `_CARD_CONTEXT_BUILDERS` rows in `app/routes/card_insight.py`.
- **Spec D tile shape is mandatory.** Every tile carries `{key, label, icon, tier, rule, numeric, caveat, features, metadata?, sources}`. The `gesix_newcomer` tile emits `tier: "unknown"` and reuses the YF quintile-bar modal.
- **Neumorphic UI unchanged.** `.cell` shape + `--neumo-sh-*` tokens + Plus Jakarta Sans + inline SVG in the shared `ico = {...}` object. No new components.
- **Cache-buster on every frontend edit.** Bump `?v=` on both `app.js` and `app.css` in `v0.1/web/index.html`.
- **No build step for the frontend.** Edit-refresh. No bundler, no npm, no framework.
- **`ponytail:` comments** mark deliberate simplifications; do not strip.
- **Commit after every task passes its selfcheck.** Short imperative subject; split by concern.

## File Structure

**Backend (Python) — all paths relative to `v0.1/`:**

| File | Responsibility | Task |
|---|---|---|
| `scripts/refresh_osm_amenities.py` | Extend `_TAG_RULES` with `intl_food`, `coworking`, `english_clinic`, `buergeramt` (OSM fallback) | 1 |
| `app/cities/base.py` | Add `newcomer_lens: LensConfig` field to `CityConfig`; add `buergeramt_wfs_url: Optional[str]` field | 2 |
| `app/cities/berlin.py` | Instantiate `NEWCOMER_LENS` (6 tiles) + wire onto `BERLIN`; add `buergeramt` attribution key | 2 |
| `app/core/scorer.py` | Extract shared `_shape_gesix(index, lat, lon)` helper used by both lenses | 3 |
| `app/core/scorer.py` | Add 5 tier functions + `newcomer_lens(cfg, index, ...)` composer + pure selfchecks | 4 |
| `app/routes/lookup.py` | Call `newcomer_lens` at end of handler; fold under `lens.newcomer` behind try/except | 5 |
| `inference/templates/*.py` | 6 new template files (`buergeramt_insight`, `transit_newcomer_insight`, `intl_food_insight`, `coworking_insight`, `english_clinic_insight`, `gesix_newcomer_insight`) | 6 |
| `inference/main.py` | Register 6 new templates in `TEMPLATES` | 6 |
| `app/routes/card_insight.py` | Extend `_CARD_CONTEXT_BUILDERS` with 6 new rows | 7 |
| `app/selfcheck.py` | Live asserts for Bergmannstraße 27 (mid-quintile, mostly green) + Marzahner Promenade (higher quintile, mixed) | 10 |

**Frontend (vanilla) — all paths relative to `v0.1/`:**

| File | Responsibility | Task |
|---|---|---|
| `web/static/app.js` | Extend `LIFE_MODE_LENSES` registry with `newcomer` entry (6 tiles + `insightKeys`) | 8 |
| `web/static/app.js` | Extend `_INSIGHT_VINTAGE` with 6 new card entries | 8 |
| `web/static/app.js` | Wire `gesix_newcomer` modal render to reuse the existing YF quintile-bar branch (same metadata shape) | 8 |
| `web/index.html` | Add SVG icons in shared `ico = {...}` for buergeramt / intl_food / coworking / english_clinic (bump cache-buster) | 9 |
| — | Live-browser QA checklist (manual) | 11 |

---

## Task 1: Extend Geofabrik refresh script with newcomer categories

**Files:**
- Modify: `v0.1/scripts/refresh_osm_amenities.py`
- Test: `v0.1/scripts/refresh_osm_amenities.py::__main__` (add fixture-based assertion if a bottom block exists; otherwise assert against the JSON snapshot after a real refresh run)

**Interfaces:**
- Consumes: existing `_TAG_RULES` dict shape (tuple-based rules, `vs=None` sentinel for wildcard match)
- Produces: JSON snapshot on disk with 4 new keys under the same `{lat, lon, tags}` per-item shape:
  - `intl_food: list[{lat, lon, tags}]`
  - `coworking: list[{lat, lon, tags}]`
  - `english_clinic: list[{lat, lon, tags}]`
  - `buergeramt: list[{lat, lon, tags}]` (OSM fallback until Task 12 replaces with WFS)

**Notes:** Preserve the atomic-write pattern (temp file + `os.replace`). Do not touch the existing bucket categories — additive only.

- [ ] **Step 1: Read the existing `_TAG_RULES` block for style reference**

```bash
head -200 v0.1/scripts/refresh_osm_amenities.py
```

- [ ] **Step 2: Append four new `_TAG_RULES` entries**

The rule format is tuple-based `(tag_key, allowed_values | None)` — `None` matches any value. Where a rule needs "value not in set", express as an inclusion set covering the acceptable values (see the existing `pharmacies` and `supermarkets` entries as templates).

```python
# intl_food — international grocers + non-german restaurants.
# Two disjunct filter groups; entities matching either bucket are collected.
"intl_food": [
    # International origin grocers
    {"amenity": ("shop",),
     "shop": ("supermarket", "greengrocer", "convenience"),
     "origin": ("asian", "turkish", "indian", "african", "russian",
                "polish", "arab", "italian", "vietnamese", "korean")},
    # International restaurants — cuisine tag set, excluding german/regional.
    {"amenity": ("restaurant",),
     "cuisine": None,   # any non-empty value; germanness filtered post-load
     "_exclude_cuisine": ("german", "regional", "european", "bavarian",
                          "berlin", "brandenburg")},
],

# coworking — coworking spaces + laptop-friendly cafés with wifi.
"coworking": [
    {"office": ("coworking",)},
    {"amenity": ("cafe",),
     "internet_access": ("wlan", "yes")},
],

# english_clinic — English-language medical practices from OSM community tags.
"english_clinic": [
    {"amenity": ("doctors", "clinic", "hospital"),
     "language:en": ("yes",)},
],

# buergeramt — Berlin district registration offices (OSM fallback until WFS).
"buergeramt": [
    {"office": ("government",),
     "government": ("register_office",)},
    # Also catch the German tag which OSM community sometimes uses:
    {"amenity": ("townhall",),
     "government": ("register_office",)},
],
```

For the `_exclude_cuisine` field on `intl_food`, extend the filter loop in the refresh script to skip entries whose `cuisine` tag lies in the excluded set. If the current filter loop does not support exclusion, add a post-filter pass after the pyosmium collect step.

- [ ] **Step 3: Run the refresh once end-to-end**

```bash
cd v0.1
uv run python -m scripts.refresh_osm_amenities
```

Verify the emitted JSON has non-empty arrays for at least `intl_food` and `coworking` in Berlin, and non-empty (or exactly-zero — Berlin has ~50 Bürgerämter, all OSM-tagged) for `buergeramt`.

- [ ] **Step 4: Add a __main__ assertion**

```python
if __name__ == "__main__":
    import json, pathlib
    snap = pathlib.Path("data/osm_local/berlin_snapshot.json")
    if snap.exists():
        j = json.loads(snap.read_text())
        for key in ("intl_food", "coworking", "english_clinic", "buergeramt"):
            assert key in j, f"missing bucket {key!r}"
            assert isinstance(j[key], list), f"{key} not list"
        print("selfcheck ok:", {k: len(j[k]) for k in
              ("intl_food", "coworking", "english_clinic", "buergeramt")})
    else:
        print("selfcheck skipped — no snapshot yet")
```

- [ ] **Step 5: Commit**

```bash
git add v0.1/scripts/refresh_osm_amenities.py v0.1/data/osm_local/berlin_snapshot.json
git commit -m "refresh: add newcomer-lens categories to OSM extract"
```

---

## Task 2: `CityConfig` field + `NEWCOMER_LENS` instantiation

**Files:**
- Modify: `v0.1/app/cities/base.py`
- Modify: `v0.1/app/cities/berlin.py`
- Test: `v0.1/app/cities/berlin.py::__main__` (bottom-of-file assertion block)

**Interfaces:**
- Consumes: existing `LensConfig`, `LensTileConfig` dataclasses (from Spec A)
- Produces: `NEWCOMER_LENS: LensConfig` module-level constant; `BERLIN.newcomer_lens = NEWCOMER_LENS`; `BERLIN.attribution["buergeramt"] = "…"`; new `buergeramt_wfs_url: Optional[str]` field on `CityConfig` (default `None`, so v1 falls back to OSM)

- [ ] **Step 1: Read `CityConfig` current shape**

```bash
grep -n "class CityConfig\|newcomer_lens\|young_family_lens\|osm_local_path\|buergeramt" v0.1/app/cities/base.py
```

- [ ] **Step 2: Add fields to `CityConfig`**

```python
# in v0.1/app/cities/base.py, inside @dataclass(frozen=True) class CityConfig:
newcomer_lens: LensConfig             # required — Spec E lens
buergeramt_wfs_url: Optional[str] = None   # v1: None → OSM fallback; v2: WFS URL
```

Note: `young_family_lens` is already a required field; keep `newcomer_lens` required too so Berlin instantiation fails fast if this task lands mis-wired.

- [ ] **Step 3: Add attribution entry in `berlin.py`**

```python
# in v0.1/app/cities/berlin.py, extend the existing `attribution` dict on BERLIN:
"buergeramt": "Berlin Geoportal — Bezirks-Services WFS · Data licence Berlin (dl-de/by-2-0)",
# osm_geofabrik, vbb, gesix already present from prior specs
```

- [ ] **Step 4: Instantiate `NEWCOMER_LENS`**

```python
# in v0.1/app/cities/berlin.py, add a module-level constant:

NEWCOMER_LENS = LensConfig(
    slug="newcomer",
    label="Newcomer",
    audience_hint="First 90 days in Berlin — registration, transit, English-friendly services.",
    tiles=(
        LensTileConfig(
            key="buergeramt", label="Bürgeramt reach", icon="buergeramt",
            thresholds={"green_m": 1500, "amber_m": 3000},
            caveat=""),
        LensTileConfig(
            key="transit_newcomer", label="Transit reach", icon="transit",
            thresholds={"sbahn_m": 800, "ubahn_m": 500, "any_rail_m": 1200},
            caveat=""),
        LensTileConfig(
            key="intl_food", label="International food", icon="intl_food",
            thresholds={"radius_m": 800, "green_count": 5, "amber_count": 2},
            caveat=""),
        LensTileConfig(
            key="coworking", label="Coworking + Wi-Fi cafés", icon="coworking",
            thresholds={"radius_m": 1000, "green_count": 3, "amber_count": 1},
            caveat=""),
        LensTileConfig(
            key="english_clinic", label="English-speaking clinic", icon="english_clinic",
            thresholds={"green_m": 1200, "amber_m": 3000},
            caveat="OSM community-tagged — inner-district coverage good, outer may under-report"),
        LensTileConfig(
            key="gesix_newcomer", label="Neighbourhood profile", icon="gesix",
            thresholds={},   # shape-only — no tier logic
            caveat=""),
    ),
)
```

- [ ] **Step 5: Wire onto `BERLIN`**

```python
# extend BERLIN = CityConfig(...) with:
newcomer_lens=NEWCOMER_LENS,
```

- [ ] **Step 6: Add __main__ assertions**

```python
if __name__ == "__main__":
    from app.cities.berlin import BERLIN, NEWCOMER_LENS
    assert BERLIN.newcomer_lens is NEWCOMER_LENS
    assert BERLIN.buergeramt_wfs_url is None    # v1: OSM fallback
    keys = [t.key for t in BERLIN.newcomer_lens.tiles]
    assert keys == ["buergeramt", "transit_newcomer", "intl_food",
                    "coworking", "english_clinic", "gesix_newcomer"], keys
    assert "buergeramt" in BERLIN.attribution
    print("selfcheck ok: NEWCOMER_LENS wired")
```

- [ ] **Step 7: Run the selfcheck**

```bash
cd v0.1 && CITY=berlin uv run python -m app.cities.berlin
```

- [ ] **Step 8: Commit**

```bash
git add v0.1/app/cities/base.py v0.1/app/cities/berlin.py
git commit -m "cities: add newcomer_lens config to Berlin"
```

---

## Task 3: Extract shared `_shape_gesix` helper

**Files:**
- Modify: `v0.1/app/core/scorer.py`
- Test: `v0.1/app/core/scorer.py::__main__`

**Interfaces:**
- Consumes: `Index.gesix_at(lon, lat) -> Optional[dict]`
- Produces: `_shape_gesix(index, lat, lon, card_key="gesix") -> dict` — returns the Spec D tile shape with `tier="unknown"`, no `rule`/`numeric` on face, metadata carrying `{plr_name, quintile_5, rang, total}`. The `card_key` argument lets the YF composer emit `key="gesix"` while the newcomer composer emits `key="gesix_newcomer"` — the frontend routes the insight button by this key.

**Rationale:** Both lenses need the identical shape-only GESIx tile with only the tile key + insight template diverging. Extract the shared body now so Task 4's composer stays small.

- [ ] **Step 1: Find the current YF gesix inline block**

```bash
grep -n "gesix\|_tier_gesix\|_shape_gesix" v0.1/app/core/scorer.py
```

- [ ] **Step 2: Extract the helper**

```python
def _shape_gesix(index, lat: float, lon: float, *,
                 card_key: str = "gesix",
                 label: str = "Neighbourhood profile") -> dict:
    """Shape-only GESIx tile. No tier badge, no numeric on face.
    Face renders label + one-line hint; modal renders the 5-segment
    quintile bar (frontend responsibility). Metadata carries the raw
    GESIx attributes; the insight template consumes them via
    _ctx_gesix in card_insight.py.
    """
    g = index.gesix_at(lon, lat) or {}
    return {
        "key":      card_key,
        "label":    label,
        "icon":     "gesix",
        "tier":     "unknown",
        "rule":     "socioeconomic band of this Planungsraum · tap for detail",
        "numeric":  "",
        "caveat":   "",
        "features": [],
        "metadata": {"gesix": g},
        "sources":  ["gesix"],
    }
```

- [ ] **Step 3: Replace the inline block in the YF composer**

```python
# Before: young_family_lens(...) built the gesix tile inline
# After: young_family_lens(...) calls _shape_gesix(index, lat, lon, card_key="gesix")
```

- [ ] **Step 4: Assert the extracted helper**

```python
# in __main__:
class _StubIdx:
    def gesix_at(self, lon, lat): return {"plr_name":"X","quintile_5":3,"rang":200,"total":447}
t = _shape_gesix(_StubIdx(), 52.5, 13.4)
assert t["key"] == "gesix" and t["tier"] == "unknown"
assert t["metadata"]["gesix"]["quintile_5"] == 3
t2 = _shape_gesix(_StubIdx(), 52.5, 13.4, card_key="gesix_newcomer")
assert t2["key"] == "gesix_newcomer"
```

- [ ] **Step 5: Run selfcheck + commit**

```bash
cd v0.1 && uv run python -m app.core.scorer
git add v0.1/app/core/scorer.py
git commit -m "scorer: extract _shape_gesix helper for reuse across lenses"
```

---

## Task 4: Newcomer tier functions + composer

**Files:**
- Modify: `v0.1/app/core/scorer.py`
- Test: `v0.1/app/core/scorer.py::__main__` (extend existing block)

**Interfaces:**
- Consumes: `Index` public methods (`Index.osm_local.query(bucket, lat, lon, radius_m)`, `Index.vbb_query(lat, lon, radius_m)`, `Index.gesix_at`), `CityConfig` (for thresholds + attribution keys)
- Produces:
  - `_tier_buergeramt(features, thresholds) -> tile_dict`
  - `_tier_transit_newcomer(features, thresholds) -> tile_dict`
  - `_tier_intl_food(features, thresholds) -> tile_dict`
  - `_tier_coworking(features, thresholds) -> tile_dict`
  - `_tier_english_clinic(features, thresholds) -> tile_dict`
  - `newcomer_lens(cfg, index, lat: float, lon: float) -> {"version": 1, "tiles": [...]}`

**Threshold reference:** boundaries are inclusive on the greener side — a distance exactly equal to the green cutoff is green, one metre beyond is amber.

- [ ] **Step 1: Add `_tier_buergeramt`**

```python
def _tier_buergeramt(features: list[dict], th: dict) -> dict:
    """Distance-to-nearest logic. Green ≤ 1500m; amber ≤ 3000m; red > 3000m.
    features: list of {name, lat, lon, distance_m, meta} sorted by distance.
    """
    if not features:
        return _tile("buergeramt", "Bürgeramt reach", "buergeramt",
                     tier="red", rule="no Bürgeramt within reach",
                     numeric="", features=[], sources=["osm_geofabrik"])
    nearest = features[0]
    d = nearest["distance_m"]
    if d <= th["green_m"]:
        tier, rule = "green", "Bürgeramt within a 15-minute walk"
    elif d <= th["amber_m"]:
        tier, rule = "amber", "reachable but you'll need transit"
    else:
        tier, rule = "red", "cross-district trip required"
    return _tile("buergeramt", "Bürgeramt reach", "buergeramt",
                 tier=tier, rule=rule,
                 numeric=f"{int(d)}m to {nearest['name']}",
                 features=features, sources=["osm_geofabrik"])
```

(`_tile(...)` is a lightweight helper already present in the YF composer path; if it does not yet exist, factor it out here.)

- [ ] **Step 2: Add `_tier_transit_newcomer`**

```python
def _tier_transit_newcomer(features: list[dict], th: dict) -> dict:
    """Newcomer framing: prefers S/U over tram; surfaces intercity access.
    features: VBB stops with {name, mode ∈ {'S','U','SU','R','T','B'}, distance_m}.
    """
    if not features:
        return _tile("transit_newcomer", "Transit reach", "transit",
                     tier="red", rule="no rail stop within 1.2 km",
                     numeric="", features=[], sources=["vbb"])
    # green: S-Bahn ≤ 800m OR U-Bahn ≤ 500m
    for f in features:
        if f["distance_m"] > max(th["sbahn_m"], th["ubahn_m"]):
            break
        if "S" in f.get("mode","") and f["distance_m"] <= th["sbahn_m"]:
            return _tile("transit_newcomer", "Transit reach", "transit",
                         tier="green",
                         rule="rail door-to-door for arrivals and departures",
                         numeric=f"{int(f['distance_m'])}m to {f['mode']}-Bahn {f['name']}",
                         features=features, sources=["vbb"])
        if "U" in f.get("mode","") and f["distance_m"] <= th["ubahn_m"]:
            return _tile("transit_newcomer", "Transit reach", "transit",
                         tier="green",
                         rule="rail door-to-door for arrivals and departures",
                         numeric=f"{int(f['distance_m'])}m to {f['mode']}-Bahn {f['name']}",
                         features=features, sources=["vbb"])
    # amber: any rail within 1.2 km
    for f in features:
        if f["distance_m"] <= th["any_rail_m"]:
            return _tile("transit_newcomer", "Transit reach", "transit",
                         tier="amber",
                         rule="one interchange for intercity",
                         numeric=f"{int(f['distance_m'])}m to {f['mode']} {f['name']}",
                         features=features, sources=["vbb"])
    # red
    return _tile("transit_newcomer", "Transit reach", "transit",
                 tier="red", rule="cabs or long transfers to leave the city",
                 numeric="", features=features, sources=["vbb"])
```

- [ ] **Step 3: Add `_tier_intl_food`, `_tier_coworking` (count-based)**

```python
def _tier_intl_food(features: list[dict], th: dict) -> dict:
    n = len(features)
    if n >= th["green_count"]:
        tier, rule = "green", "cluster of international food and grocery"
    elif n >= th["amber_count"]:
        tier, rule = "amber", "a few options, mostly one direction"
    else:
        tier, rule = "red", "mainstream Rewe/Edeka territory"
    return _tile("intl_food", "International food", "intl_food",
                 tier=tier, rule=rule,
                 numeric=f"{n} international spots within {th['radius_m']} m walk",
                 features=features, sources=["osm_geofabrik"])

def _tier_coworking(features: list[dict], th: dict) -> dict:
    n = len(features)
    if n >= th["green_count"]:
        tier, rule = "green", "walkable coworking scene"
    elif n >= th["amber_count"]:
        tier, rule = "amber", "one or two anchors"
    else:
        tier, rule = "red", "no laptop-friendly options nearby"
    return _tile("coworking", "Coworking + Wi-Fi cafés", "coworking",
                 tier=tier, rule=rule,
                 numeric=f"{n} remote-work spots within {th['radius_m']} m",
                 features=features, sources=["osm_geofabrik"])
```

- [ ] **Step 4: Add `_tier_english_clinic`**

```python
def _tier_english_clinic(features: list[dict], th: dict) -> dict:
    if not features:
        return _tile("english_clinic", "English-speaking clinic", "english_clinic",
                     tier="red",
                     rule="no English-tagged practice nearby — expect German or telemedicine",
                     numeric="", features=[], caveat="OSM community-tagged — inner-district coverage good, outer may under-report",
                     sources=["osm_geofabrik"])
    nearest = features[0]
    d = nearest["distance_m"]
    if d <= th["green_m"]:
        tier, rule = "green", "English-speaking medical care in walking distance"
    elif d <= th["amber_m"]:
        tier, rule = "amber", "reachable, will need a short transit ride"
    else:
        tier, rule = "red", "no English-tagged practice nearby — expect German or telemedicine"
    return _tile("english_clinic", "English-speaking clinic", "english_clinic",
                 tier=tier, rule=rule,
                 numeric=f"{int(d)}m to {nearest['name']} (English)",
                 features=features,
                 caveat="OSM community-tagged — inner-district coverage good, outer may under-report",
                 sources=["osm_geofabrik"])
```

- [ ] **Step 5: Add the composer**

```python
def newcomer_lens(cfg, index, lat: float, lon: float) -> dict:
    """Compose the 6-tile Newcomer lens block. Reads only pre-loaded
    Index state — no live-fetch on hot path. Each tier function is
    a small pure translation from feature list + thresholds to tile dict.
    """
    th = {t.key: t.thresholds for t in cfg.newcomer_lens.tiles}
    tiles = [
        _tier_buergeramt(
            _walk_features(index.osm_local.query("buergeramt", lat, lon, 3500), lat, lon),
            th["buergeramt"]),
        _tier_transit_newcomer(
            _walk_features(index.vbb_query(lat, lon, 1500), lat, lon),
            th["transit_newcomer"]),
        _tier_intl_food(
            _walk_features(index.osm_local.query("intl_food", lat, lon,
                th["intl_food"]["radius_m"]), lat, lon),
            th["intl_food"]),
        _tier_coworking(
            _walk_features(index.osm_local.query("coworking", lat, lon,
                th["coworking"]["radius_m"]), lat, lon),
            th["coworking"]),
        _tier_english_clinic(
            _walk_features(index.osm_local.query("english_clinic", lat, lon, 3500), lat, lon),
            th["english_clinic"]),
        _shape_gesix(index, lat, lon, card_key="gesix_newcomer"),
    ]
    return {"version": 1, "tiles": tiles}
```

`_walk_features(...)` is the shared feature-shaper (name / distance_m / lat / lon / meta) that the YF composer already uses; extract if not already shared.

- [ ] **Step 6: Extend `__main__` selfchecks**

For each tier function, assert green / amber / red / empty branches with hand-crafted feature lists. Sample:

```python
# _tier_buergeramt
assert _tier_buergeramt([{"name":"X","distance_m":1000,"lat":0,"lon":0,"meta":{}}],
                        {"green_m":1500,"amber_m":3000})["tier"] == "green"
assert _tier_buergeramt([{"name":"X","distance_m":1500,"lat":0,"lon":0,"meta":{}}],
                        {"green_m":1500,"amber_m":3000})["tier"] == "green"   # inclusive
assert _tier_buergeramt([{"name":"X","distance_m":1500.01,"lat":0,"lon":0,"meta":{}}],
                        {"green_m":1500,"amber_m":3000})["tier"] == "amber"
assert _tier_buergeramt([], {"green_m":1500,"amber_m":3000})["tier"] == "red"
# ...repeat for the other four tier functions
# composer smoke:
class _StubIdx:
    class osm_local:
        @staticmethod
        def query(bucket, lat, lon, r): return []
    def vbb_query(self, lat, lon, r): return []
    def gesix_at(self, lon, lat): return {"plr_name":"X","quintile_5":3,"rang":1,"total":1}
out = newcomer_lens(BERLIN, _StubIdx(), 52.5, 13.4)
assert [t["key"] for t in out["tiles"]] == \
    ["buergeramt","transit_newcomer","intl_food","coworking","english_clinic","gesix_newcomer"]
```

- [ ] **Step 7: Run selfcheck**

```bash
cd v0.1 && uv run python -m app.core.scorer
```

- [ ] **Step 8: Commit**

```bash
git add v0.1/app/core/scorer.py
git commit -m "scorer: newcomer lens tier fns + composer (5 tiles + gesix reuse)"
```

---

## Task 5: Wire composer into `/api/lookup`

**Files:**
- Modify: `v0.1/app/routes/lookup.py`
- Test: live run against Bergmannstraße 27

**Interfaces:**
- Consumes: `app.core.scorer.newcomer_lens`
- Produces: response body grows `.lens.newcomer = {version, tiles}`

**Notes:** Wrap in a try/except that logs but does not fail the whole lookup — same defensive pattern the YF composer uses. Per-category failure is tolerated behind the `_error` pattern (§14 conventions).

- [ ] **Step 1: Locate the YF composer call site**

```bash
grep -n "young_family_lens\|lens\[" v0.1/app/routes/lookup.py
```

- [ ] **Step 2: Add the newcomer composer call**

```python
# after the YF composer call:
try:
    lens_out["newcomer"] = newcomer_lens(cfg, index, addr["lat"], addr["lon"])
except Exception as e:
    lens_out["newcomer"] = {"_error": f"{type(e).__name__}: {e}"}
```

- [ ] **Step 3: Add the import**

```python
from app.core.scorer import newcomer_lens
```

- [ ] **Step 4: Live smoke test**

```bash
cd v0.1
CITY=berlin INFERENCE_URL=http://localhost:8080 \
  uv run uvicorn app.main:app --port 8003 &
sleep 8
curl -s 'http://localhost:8003/api/lookup?address=Bergmannstra%C3%9Fe+27%2C+10961' | \
  python -c "import json,sys; d=json.load(sys.stdin); \
    tiles=d['lens']['newcomer']['tiles']; \
    print([(t['key'], t['tier']) for t in tiles])"
```

Expected: six tuples, most green in Bergmannstraße (Kreuzberg — dense international food + coworking, S/U close).

- [ ] **Step 5: Commit**

```bash
git add v0.1/app/routes/lookup.py
git commit -m "lookup: fold lens.newcomer into /api/lookup response"
```

---

## Task 6: Six new inference templates

**Files:**
- Create: `v0.1/inference/templates/buergeramt_insight.py`
- Create: `v0.1/inference/templates/transit_newcomer_insight.py`
- Create: `v0.1/inference/templates/intl_food_insight.py`
- Create: `v0.1/inference/templates/coworking_insight.py`
- Create: `v0.1/inference/templates/english_clinic_insight.py`
- Create: `v0.1/inference/templates/gesix_newcomer_insight.py`
- Modify: `v0.1/inference/main.py` — register all six in `TEMPLATES`
- Test: each template's `__main__` selfcheck (pure — no model load)

**Interfaces:**
- Consumes: `context` dict shaped by the corresponding `_ctx_*` builder in Task 7
- Produces: `run(backend, ctx) -> {"insight": str}`

**Template shape (copy from `refuge_insight.py`):**

```python
from __future__ import annotations

SAMPLER = {"temperature": 0.55, "max_tokens": 180, "top_p": 0.9}

_SYSTEM = """You write short paragraphs (2–3 sentences) for someone new to Berlin.
Address them in second-person plural ("we"). Do not use German admin terms without
a one-line English gloss. Never invert the meaning of a red tier into positive
framing."""

def build_messages(ctx: dict) -> list[dict]:
    tier = ctx.get("tier", "unknown")
    rule = ctx.get("rule", "")
    features = ctx.get("features", [])[:5]
    user = (
        f"Tier: {tier}. Rule: {rule}.\n"
        f"Nearby: {', '.join(f['name'] for f in features) if features else 'none'}.\n"
        "Write 2–3 sentences of practical framing for a newcomer."
    )
    return [
        {"role": "system", "content": _SYSTEM},
        # one-shot exemplar of red-tier response (anti-inversion):
        {"role": "user",   "content": "Tier: red. Rule: no options nearby. Nearby: none."},
        {"role": "assistant", "content": "Nothing in walking distance, so plan on a transit ride when we need this. It's not a dealbreaker — many Berliners commute for niche services — but factor it into your daily rhythm."},
        {"role": "user",   "content": user},
    ]

def run(backend, ctx: dict) -> dict:
    msgs = build_messages(ctx)
    text = backend.chat(msgs, **SAMPLER)
    return {"insight": text.strip()}

if __name__ == "__main__":
    m = build_messages({"tier": "red", "rule": "no options nearby", "features": []})
    assert m[0]["role"] == "system"
    assert "Never invert" in m[0]["content"] or "invert" in m[0]["content"].lower()
    assert "red" in m[-1]["content"].lower()
    print("selfcheck ok")
```

**Per-template `_SYSTEM` variations:**

- `buergeramt_insight` — mention that Bürgeramt slots are city-wide bookable; proximity matters for last-minute openings.
- `transit_newcomer_insight` — mention Hauptbahnhof + BER access, not tram frequency.
- `intl_food_insight` — mention weekly-shop convenience, not restaurant nightlife.
- `coworking_insight` — mention first-month laptop-friendly anchor before permanent desk.
- `english_clinic_insight` — surface the OSM caveat; mention TK/AOK helplines and Doctolib as English-language backups.
- `gesix_newcomer_insight` — see the extra requirements below.

**`gesix_newcomer_insight` — extra requirements per Spec E:**

```python
_SYSTEM = """You interpret the Berlin GESIx 2022 socioeconomic band of a Planungsraum
for a newcomer expat. Frame quintiles as tradeoffs, never as rankings. Do not use the
words "better", "worse", or "avoid" in a ranking sense. Always mention: (a) likely
language mix on the block, (b) rent-band signal, (c) a "walk the block before
signing" caveat. Second-person plural."""

def build_messages(ctx: dict) -> list[dict]:
    g = ctx  # from _ctx_gesix — {plr_name, quintile_5, rang, total, lens}
    user = (
        f"Planungsraum: {g.get('plr_name','?')}. GESIx quintile: {g.get('quintile_5','?')}/5. "
        f"Rank: {g.get('rang','?')} of {g.get('total','?')}. Audience: newcomer expat, first 90 days."
    )
    return [
        {"role":"system","content":_SYSTEM},
        # one-shot q1 exemplar
        {"role":"user","content":"Planungsraum: Grunewald. GESIx quintile: 1/5. Rank: 12 of 447. Audience: newcomer expat."},
        {"role":"assistant","content":"Quiet, monolingual-German streets with the highest rent band in the city — you'll trade language immersion for a calmer routine. Expect fewer international grocers within walking distance. Walk the block on a weekday evening before signing so you know how the neighbourhood feels off business hours."},
        # one-shot q5 exemplar
        {"role":"user","content":"Planungsraum: Neukölln-Reuterkiez. GESIx quintile: 5/5. Rank: 401 of 447. Audience: newcomer expat."},
        {"role":"assistant","content":"Dense, multilingual streets with cheaper rent bands and a mixed international presence — you'll pick up services in English or Turkish easily. Nightlife runs late and the block is busy. Walk the block after 22:00 before signing so you know whether the noise matches your rhythm."},
        {"role":"user","content":user},
    ]

if __name__ == "__main__":
    # anti-ranking assertion
    m = build_messages({"plr_name":"X","quintile_5":1,"rang":10,"total":447})
    joined = "\n".join(x["content"] for x in m if x["role"] == "assistant")
    for word in ("better", "worse", "avoid"):
        assert word not in joined.lower(), f"ranking word {word!r} leaked into exemplar"
    for req in ("walk the block", "rent", "language" ):
        assert req in joined.lower(), f"missing required framing token {req!r}"
    print("selfcheck ok")
```

- [ ] **Step 1: Create the six template files** (one file per bullet above)

- [ ] **Step 2: Register in `inference/main.py`**

```python
from inference.templates import buergeramt_insight as buergeramt_insight_tpl
from inference.templates import coworking_insight as coworking_insight_tpl
from inference.templates import english_clinic_insight as english_clinic_insight_tpl
from inference.templates import gesix_newcomer_insight as gesix_newcomer_insight_tpl
from inference.templates import intl_food_insight as intl_food_insight_tpl
from inference.templates import transit_newcomer_insight as transit_newcomer_insight_tpl

TEMPLATES = {
    # ...existing entries...
    "buergeramt_insight":        buergeramt_insight_tpl.run,
    "transit_newcomer_insight":  transit_newcomer_insight_tpl.run,
    "intl_food_insight":         intl_food_insight_tpl.run,
    "coworking_insight":         coworking_insight_tpl.run,
    "english_clinic_insight":    english_clinic_insight_tpl.run,
    "gesix_newcomer_insight":    gesix_newcomer_insight_tpl.run,
}
```

- [ ] **Step 3: Run each template's selfcheck**

```bash
cd v0.1
for t in buergeramt_insight transit_newcomer_insight intl_food_insight \
         coworking_insight english_clinic_insight gesix_newcomer_insight; do
  uv run python -m inference.templates.$t
done
```

- [ ] **Step 4: Commit**

```bash
git add v0.1/inference/templates/*.py v0.1/inference/main.py
git commit -m "inference: 6 newcomer-lens insight templates + register"
```

---

## Task 7: Extend `_CARD_CONTEXT_BUILDERS`

**Files:**
- Modify: `v0.1/app/routes/card_insight.py`
- Test: bottom-of-file `__main__` block (add if not present)

**Interfaces:**
- Consumes: existing `_ctx_features` and `_ctx_gesix` builders
- Produces: six new rows in `_CARD_CONTEXT_BUILDERS` mapping card key → context builder

- [ ] **Step 1: Extend the dispatcher**

```python
_CARD_CONTEXT_BUILDERS = {
    # ...existing YF entries...
    "buergeramt":         _ctx_features,   # or _ctx_buergeramt if WFS meta needed
    "transit_newcomer":   _ctx_features,
    "intl_food":          _ctx_features,
    "coworking":          _ctx_features,
    "english_clinic":     _ctx_features,
    "gesix_newcomer":     _ctx_gesix,
}
```

- [ ] **Step 2: Live test**

```bash
curl -s -X POST http://localhost:8003/api/card_insight \
  -H 'content-type: application/json' \
  -d '{"card":"buergeramt","lens":"newcomer","tile":{"tier":"green","rule":"walk","features":[{"name":"Bürgeramt Kreuzberg"}]}}'
```

Expect a 200 with an `insight` string in the response.

- [ ] **Step 3: Commit**

```bash
git add v0.1/app/routes/card_insight.py
git commit -m "card_insight: wire 6 newcomer-lens card keys into dispatcher"
```

---

## Task 8: Extend `LIFE_MODE_LENSES` frontend registry

**Files:**
- Modify: `v0.1/web/static/app.js`
- Test: live browser QA (Task 11)

**Interfaces:**
- Consumes: existing `LIFE_MODE_LENSES` registry + `renderLensPicker` + `renderLensTile` + `renderLensModalBody`
- Produces: `LIFE_MODE_LENSES.newcomer` entry; `_INSIGHT_VINTAGE` grows six rows

- [ ] **Step 1: Add the registry entry**

```js
const LIFE_MODE_LENSES = {
  young_family: { /* existing */ },
  newcomer: {
    label: 'Newcomer',
    desc:  'First 90 days in Berlin — registration, transit, English-friendly services.',
    tiles: ['buergeramt','transit_newcomer','intl_food','coworking','english_clinic','gesix_newcomer'],
    insightKeys: {
      buergeramt:       'buergeramt_insight',
      transit_newcomer: 'transit_newcomer_insight',
      intl_food:        'intl_food_insight',
      coworking:        'coworking_insight',
      english_clinic:   'english_clinic_insight',
      gesix_newcomer:   'gesix_newcomer_insight',
    },
  },
};
```

- [ ] **Step 2: Add `_INSIGHT_VINTAGE` entries**

```js
const _INSIGHT_VINTAGE = {
  // ...existing YF entries...
  buergeramt:       'BOD Bezirks-Services · 2026',
  transit_newcomer: 'VBB · 2026',
  intl_food:        'OSM Geofabrik weekly extract',
  coworking:        'OSM Geofabrik weekly extract',
  english_clinic:   'OSM Geofabrik weekly extract',
  gesix_newcomer:   'BOD GESIx · 2022',
};
```

- [ ] **Step 3: Route `gesix_newcomer` modal to the existing quintile-bar renderer**

Locate the `renderLensModalBody` branch that currently keys on `tile.key === 'gesix'` and either broaden the condition (`tile.key === 'gesix' || tile.key === 'gesix_newcomer'`) or introspect `tile.metadata?.gesix` presence. Preserve the existing quintile-bar DOM.

- [ ] **Step 4: Bump cache-buster**

```html
<!-- v0.1/web/index.html -->
<link rel="stylesheet" href="/static/app.css?v=20260812j">
<script src="/static/app.js?v=20260812l" defer></script>
```

(Use the next letter suffix in the running sequence.)

- [ ] **Step 5: Commit**

```bash
git add v0.1/web/static/app.js v0.1/web/index.html
git commit -m "frontend: LIFE_MODE_LENSES gains newcomer entry (6 tiles)"
```

---

## Task 9: Frontend SVG icons for new cards

**Files:**
- Modify: `v0.1/web/index.html` — extend the shared `ico = {...}` object

**Interfaces:**
- Consumes: existing inline-SVG icon convention
- Produces: `ico.buergeramt`, `ico.intl_food`, `ico.coworking`, `ico.english_clinic` (transit and gesix already have icons from YF)

- [ ] **Step 1: Locate the `ico = {...}` block**

```bash
grep -n "ico = {\|ico\." v0.1/web/index.html | head
```

- [ ] **Step 2: Add the four icons**

Use inline SVGs with `stroke="currentColor"`, `stroke-width="2"`, `fill="none"` so they inherit the neumorphic accent color. Icon suggestions:
- `buergeramt` — official building glyph (columns + roof).
- `intl_food` — shopping basket or globe-fork combo.
- `coworking` — laptop + wifi arcs.
- `english_clinic` — medical cross + speech bubble.

- [ ] **Step 3: Bump cache-buster** (already done in Task 8 if same edit session — otherwise bump again).

- [ ] **Step 4: Commit**

```bash
git add v0.1/web/index.html
git commit -m "icons: buergeramt / intl_food / coworking / english_clinic SVGs"
```

---

## Task 10: Selfcheck orchestrator + live assertions

**Files:**
- Modify: `v0.1/app/selfcheck.py`

**Interfaces:**
- Consumes: running `Index` from a real boot
- Produces: extended live-assert coverage that hits `/api/lookup` and validates the `lens.newcomer` block

- [ ] **Step 1: Add two live-address assertions**

```python
# Bergmannstraße 27 — Kreuzberg baseline (mostly green expected)
r = client.get("/api/lookup?address=Bergmannstra%C3%9Fe+27%2C+10961").json()
assert "newcomer" in r["lens"]
tiles = {t["key"]: t for t in r["lens"]["newcomer"]["tiles"]}
assert set(tiles) == {"buergeramt","transit_newcomer","intl_food",
                      "coworking","english_clinic","gesix_newcomer"}
assert tiles["transit_newcomer"]["tier"] == "green"     # multiple S/U nearby
assert tiles["intl_food"]["tier"] in ("green","amber")  # Kreuzberg → international
assert tiles["gesix_newcomer"]["tier"] == "unknown"     # shape-only
assert "gesix" in tiles["gesix_newcomer"]["metadata"]

# Marzahner Promenade — high-quintile edge district
r = client.get("/api/lookup?address=Marzahner+Promenade+1%2C+12679").json()
tiles = {t["key"]: t for t in r["lens"]["newcomer"]["tiles"]}
assert tiles["english_clinic"]["tier"] in ("amber","red")   # coverage thinner outer
```

- [ ] **Step 2: Run the orchestrator**

```bash
cd v0.1 && CITY=berlin uv run python -m app.selfcheck
```

- [ ] **Step 3: Commit**

```bash
git add v0.1/app/selfcheck.py
git commit -m "selfcheck: live asserts for lens.newcomer at two Berlin addresses"
```

---

## Task 11: Live-browser QA checklist (manual)

**Preconditions:**
- Inference service running on 8080 (`INFERENCE_BACKEND=mlx`).
- `v0.1` app running on 8003 (`CITY=berlin`).
- Hard-refreshed browser after cache-buster bump.

**Checklist:**

- [ ] Life Mode toggle exposes both **Young Family** and **Newcomer** entries in the picker.
- [ ] Selecting Newcomer shows exactly 6 tiles in the fixed order: Bürgeramt · Transit · International food · Coworking · English clinic · Neighbourhood profile.
- [ ] Each of the 5 traffic-light tiles renders a tier color + rule text on the face (no numeric text on the face — Spec A UI rule).
- [ ] The Neighbourhood profile face renders a label + one-line hint, no tier badge.
- [ ] Clicking any tile opens the modal per Spec D — feature list + map pins for the 5 traffic-light tiles; quintile bar for the Neighbourhood profile tile.
- [ ] Get Insight button on each tile POSTs `/api/card_insight` with the correct `card` key + `lens: "newcomer"`; the returned prose is second-person, English, and framed for a newcomer.
- [ ] `gesix_newcomer_insight` prose contains no ranking words (better/worse/avoid) and mentions language mix + rent band + walk-the-block caveat.
- [ ] Bergmannstraße 27 shows mostly green tiles; Marzahner Promenade shows the expected amber/red mix.
- [ ] Compare-up-to-5 view renders the newcomer tiles side-by-side without layout regressions.
- [ ] Provenance footer contains the `buergeramt` attribution line.

- [ ] **After manual QA passes, mark this task complete.**

---

## Task 12: (Deferred fast-follow) Bürgeramt WFS upgrade

**Not required to ship Spec E v1.** Ship the OSM-fallback version first, then swap in the WFS layer.

**Files:**
- Modify: `v0.1/app/cities/berlin.py` — populate `buergeramt_wfs_url` with the Berlin Geoportal URL.
- Modify: `v0.1/app/core/index.py` — add a boot-time load of the `wfs_bezirksservice` layer (mirroring the existing WFS loaders).
- Modify: `v0.1/app/core/scorer.py::_tier_buergeramt` — prefer WFS features when present, fall back to OSM.

Ship as its own commit once the primary lens is live and stable in production.

---

## Self-Review

**Spec coverage:**
- Task 1 → Spec E §Data sources (four Geofabrik categories).
- Task 2 → Spec E §Architecture (CityConfig field, NEWCOMER_LENS, buergeramt attribution).
- Task 3 → Spec E §Locked decisions (`gesix_newcomer` shape-only tile reuse).
- Task 4 → Spec E §Data sources (five tier functions + composer).
- Task 5 → Spec E §Architecture (`/api/lookup` fold).
- Task 6 → Spec E §LLM insight templates.
- Task 7 → Spec E §Architecture (`_CARD_CONTEXT_BUILDERS` extension).
- Task 8–9 → Spec E §Frontend (`LIFE_MODE_LENSES` registry + icons).
- Task 10 → Spec E §Selfchecks.
- Task 11 → Spec E §Rollout order §6 (live QA).
- Task 12 → Spec E §Rollout order §7 (WFS upgrade fast-follow).

**Placeholder scan:** all code steps carry concrete snippets; no TBD / TODO / "implement later" tokens.

**Type consistency:** tier-function signatures uniform (`features: list[dict], th: dict -> dict`); composer signature `(cfg, index, lat, lon) -> dict`; template signature `(backend, ctx) -> dict` matches existing pattern in `refuge_insight.py`.

**Open questions from Spec E (unchanged, not blocking):**
- Q1: OSM fallback ships v1, WFS is Task 12 — recommended default.
- Q2: language-school bonus line inside English-clinic modal is out of scope for v1.
- Q3: Young Family remains default when Life Mode toggles on.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-12-newcomer-lens.md`. Two execution options:

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
