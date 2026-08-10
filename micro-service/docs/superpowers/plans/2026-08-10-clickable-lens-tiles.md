# Clickable Lens Tiles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship Spec D — make every Life Mode lens tile clickable, opening a detail modal with per-feature ⓘ popovers, backed by a dedicated Leaflet map with numbered pins and two-way row↔pin sync. Matches Spec D at `docs/superpowers/specs/2026-08-10-clickable-lens-tiles-design.md`.

**Architecture:** Purely additive to Spec A + Spec B (both already merged; last landed commit `5110613`). Backend: extend `_tier_*` return shape via new `_shape_*` helpers so each tile carries a `features` array (+ optional `metadata` on refuge). Frontend: rewrite `renderLensSingle` to output a 2-col Life Mode layout mirroring raw-mode Amenities (`.grid` + `.map-cell`); add a dedicated `#lens-map` Leaflet instance, an absolute-positioned `.lens-modal` overlay opened per tile click, and reuse the existing `<details class="info-tip">` disclosure pattern for per-feature detail popovers.

**Tech Stack:** Python 3.11+, FastAPI, shapely — no new deps. Leaflet (already loaded via CDN). Vanilla JS + hand-authored CSS — no build step, no bundler, no npm.

## Global Constraints

- **Purely additive.** No `CityConfig` field changes. No new attribution keys. `/api/lookup` response gains one required field (`features`) per tile + one optional field (`metadata`, refuge only) — no renames, no removals.
- **`app/core/*` pure.** New shape helpers (`_shape_*`) do no I/O. Composers still read from preloaded `Index` state + config; no new fetches.
- **Feature drop rule.** `_shape_*` returns `None` when required fields (`name`, `lat`, `lon`, `distance_m`) are missing/invalid. Composers filter via `[f for f in (...) if f]`. Empty list is better than a broken row.
- **`<button>` for tiles.** Not `<section>` — native keyboard + focus, no ARIA fixup needed.
- **`<details class="info-tip">` for per-feature popovers.** Reuse existing CSS (`app.css:409-421`) + tooltip portal + `dropOrphanTooltips()` cleanup. No new disclosure widget.
- **Reuse `.amen-modal` visual language** — same `position:absolute`, `inset:0`, backdrop blur, top-right ✕. Own selectors `.lens-modal` etc. so the raw-mode close listener bound to `.amen-modal-close` doesn't fire on lens close.
- **Dedicated `#lens-map`** — new Leaflet instance, not reusing raw-mode `#map`. Own lifecycle: create on Life Mode ON, remove on OFF.
- **Numbered pins.** `lensNumberedPin(idx, color)` → `L.divIcon` with `<div>N</div>` HTML. Colored per tile tier — green `#22C55E`, amber `#F59E0B`, red `#EF4444`, unknown `#9CA3AF`. Address pin stays pink `#EC4899`.
- **Two-way sync.** Feature row click (outside `.info-tip`) → `lensMap.setView([f.lat, f.lon], max(currentZoom, 16))`. Pin click → `_highlightLensRow(idx)` scrolls the row into view + brief background pulse.
- **Aggregate tiles (noise/heat/air) get info-only modals.** Explanations hardcoded client-side in `LENS_TILE_EXPLANATIONS` const, keyed by `tile.key`. Backend sends nothing extra.
- **Refuge is composite.** `features` = 0 or 1 quiet-zone dict (only if within amber radius). `metadata.trees` = tree stats dict, always present when refuge tile exists.
- **Testing without pytest.** Every helper carries `__main__` asserts. Live asserts extend `app.selfcheck.run_live_selfcheck`.
- **Neumorphic UI reuse only.** No new tokens. Shadow colors `--neumo-sh-light` / `--neumo-sh-dark`. Tier colors `--success` / `--amber` / `--danger`. Plus Jakarta Sans. Inline SVGs in `ico = {...}`.
- **`ponytail:` comments** mark deliberate simplifications with a named ceiling and upgrade path.
- **Commit after every task passes its selfcheck.** Short imperative subject; split by concern.

## File Structure

**Backend (Python):**

| File | Responsibility | Task |
|---|---|---|
| `app/core/scorer.py` | Add shape helpers: `_prune`, `_int_or_none`, `_valid_latlon`, `_shape_kita`, `_shape_playground`, `_shape_paediatric_gp`, `_shape_office`, `_shape_refuge_quiet`, `_shape_refuge_trees` + `__main__` selfcheck | 1 |
| `app/core/scorer.py` | Extend `young_family_lens` composer to emit `features` per tile + `metadata` on refuge + composer selfcheck | 2 |
| `app/core/scorer.py` | Extend `bureaucracy_lens` composer to emit `features` per tile + composer selfcheck | 3 |
| `app/selfcheck.py` | Live-selfcheck asserts for feature arrays on Kastanienallee 12 + Bergmannstraße 27 | 4 |

**Frontend:**

| File | Responsibility | Task |
|---|---|---|
| `web/static/app.css` | All new selectors — `.lens-body`, `.lens-tiles-col`, `.lens-map-col`, `#lens-map`, `.lens-tile` hover/focus, `.lens-modal` + sub-selectors, `.lens-feature`, `.modal-trees`, `.modal-explanation`, media query | 5 |
| `web/static/app.js` | Rewrite `renderLensSingle` → 2-col layout. Change `renderLensTile` → `<button data-tile-key>` and drop caveat from tile face | 6 |
| `web/static/app.js` | Add modal render helpers (`renderLensModalBody`, `renderLensFeature`, `_lensFeatureDetailHtml`, `renderLensTreesBlock`) + module consts (`LENS_TILE_EXPLANATIONS`, `TIER_PIN_COLORS`) | 7 |
| `web/static/app.js` | Add map lifecycle (`initLensMap`, `lensNumberedPin`, `_updateLensMapPins`) + module-level state; wire into `renderAllPanels` | 8 |
| `web/static/app.js` | Add event handlers (`openLensModal`, `closeLensModal`, `_highlightLensRow`; delegated tile click, modal close, feature-row click, pin click, Escape; portal + `dropOrphanTooltips` cleanup on all lens transitions) | 9 |

**QA:**

| Location | Responsibility | Task |
|---|---|---|
| Browser | 12-item §14.12 QA checklist against live app; empty ship-marker commit | 10 |

---

## Task 1: Shape helpers in `app/core/scorer.py`

**Files:**
- Modify: `app/core/scorer.py` — add 9 module-level helpers + pure asserts in the existing `__main__` block

**Interfaces:**
- Consumes: existing tier-fn input shapes (kita items from `Index.kitas_near_bod`, playground items from `amenities.playgrounds.items`, paediatrician items from `amenities.gps.items`, office dicts from `Index.buergeramt_near`/`arbeitsagentur_near`/`finanzamt_nearest`/`standesamt_for`/`cfg.lea_office`, quiet_zone dict from `Index.nearest_quiet_zone`, trees dict from `Index.trees_bbox`)
- Produces:
  - `_prune(d: dict) -> dict` — drops keys whose value is `None` or `""`
  - `_int_or_none(x) -> Optional[int]` — coerce str-int / int to int; else None
  - `_valid_latlon(d: dict) -> bool` — checks `lat, lon` are finite floats in `[-90, 90] × [-180, 180]`
  - `_shape_kita(o: dict, fm: dict) -> Optional[dict]`
  - `_shape_playground(o: dict) -> Optional[dict]`
  - `_shape_paediatric_gp(o: dict) -> Optional[dict]`
  - `_shape_office(o: dict) -> Optional[dict]` — used by buergeramt, finanzamt, standesamt, lea, arbeitsagentur
  - `_shape_refuge_quiet(q: dict, amber_quiet_m: int) -> list` — 0 or 1 dict
  - `_shape_refuge_trees(t: dict) -> dict` — passthrough of Index.trees_bbox output, cleaned

**Notes:** No composer changes yet — this task only lands the shape helpers so Tasks 2 + 3 can consume them.

- [ ] **Step 1: Read `scorer.py` and find the boundary between existing tier fns and the composer**

```bash
grep -n "^def _tier_\|^def young_family_lens\|^def bureaucracy_lens\|^def _lens_provenance\|^def _sources_for\|^def _walk_minutes\|__main__" app/core/scorer.py
```

The new shape helpers land AFTER `_walk_minutes` and BEFORE `_lens_provenance` (existing helpers cluster). Alternatively — just before `young_family_lens`. Pick a spot; the plan places them together.

- [ ] **Step 2: Add utility helpers `_prune`, `_int_or_none`, `_valid_latlon`**

Insert after the last existing helper (near `_walk_minutes` or `_lens_provenance`):

```python
# ---------------------------------------------------------------- Spec D
# Feature shape helpers — each _shape_<tile> returns a response-ready
# feature dict, or None if required fields are missing/invalid.

def _prune(d: dict) -> dict:
    """Drop keys whose value is None or empty string. Keeps 0, False, [], {}
    so 'if feature.wheelchair:' still works but 'website: ""' doesn't leak
    an empty link into the response."""
    return {k: v for k, v in d.items() if v not in (None, "")}


def _int_or_none(x):
    """Coerce BOD raw field (str-int like '65' from kita e_platz) to int.
    Returns None on empty/None/unparseable."""
    try:
        return int(x) if x not in (None, "") else None
    except (ValueError, TypeError):
        return None


def _valid_latlon(d: dict) -> bool:
    """Check `lat`/`lon` are finite floats in real-world range. Prevents
    the frontend from trying to pin at (NaN, NaN) or (999, 999)."""
    lat, lon = d.get("lat"), d.get("lon")
    return (isinstance(lat, (int, float)) and isinstance(lon, (int, float))
            and -90 <= lat <= 90 and -180 <= lon <= 180)
```

- [ ] **Step 3: Add `_shape_kita`**

```python
def _shape_kita(o: dict, fm: dict) -> Optional[dict]:
    """Response-shape a kita feature from Index.kitas_near_bod output.
    Required: name, lat, lon, distance_m. Optional: capacity (BOD e_platz —
    int-in-str), operator_type (t_art), approach (ang_1)."""
    p = o.get("props") or {}
    r = _prune({
        "name": (o.get("name") or "").strip(),
        "lat":  o.get("lat"), "lon": o.get("lon"),
        "distance_m": o.get("distance_m"),
        "capacity":       _int_or_none(p.get(fm["capacity"])),
        "operator_type": (p.get(fm["operator_type"]) or "").strip(),
        "approach":      (p.get(fm["approach"]) or "").strip(),
    })
    if not r.get("name") or not _valid_latlon(r) or r.get("distance_m") is None:
        return None
    return r
```

- [ ] **Step 4: Add `_shape_playground`**

```python
def _shape_playground(o: dict) -> Optional[dict]:
    """Response-shape a playground feature. BOD side has area (katasterfl
    or nettospfl) + optional renovation year (sanierjahr). OSM side just
    has {name, lat, lon, distance_m}. This shape covers both."""
    p = o.get("props") or {}
    r = _prune({
        "name": (o.get("name") or "").strip(),
        "lat":  o.get("lat"), "lon": o.get("lon"),
        "distance_m": o.get("distance_m"),
        "area_m2":        _int_or_none(p.get("katasterfl") or p.get("nettospfl")),
        "renovated_year": _int_or_none(p.get("sanierjahr")),
    })
    if not r.get("name") or not _valid_latlon(r) or r.get("distance_m") is None:
        return None
    return r
```

- [ ] **Step 5: Add `_shape_paediatric_gp`**

```python
def _shape_paediatric_gp(o: dict) -> Optional[dict]:
    """Response-shape a paediatric doctor feature from OSM gps bucket.
    Composes address from OSM addr:* tags. `wheelchair` only surfaced
    when yes (opt-in disclosure of accessibility)."""
    t = o.get("tags") or {}
    street = (t.get("addr:street") or "").strip()
    hnr    = (t.get("addr:housenumber") or "").strip()
    plz    = (t.get("addr:postcode") or "").strip()
    city   = (t.get("addr:city") or "").strip()
    addr_left  = f"{street} {hnr}".strip()
    addr_right = f"{plz} {city}".strip()
    address = ", ".join(p for p in [addr_left, addr_right] if p)

    r = _prune({
        "name": (o.get("name") or "").strip(),
        "lat":  o.get("lat"), "lon": o.get("lon"),
        "distance_m": o.get("distance_m"),
        "address": address,
        "phone":   (t.get("phone") or "").strip(),
        "website": (t.get("website") or "").strip(),
        "hours":   (t.get("opening_hours") or "").strip(),
        "wheelchair": True if t.get("wheelchair") == "yes" else None,
    })
    if not r.get("name") or not _valid_latlon(r) or r.get("distance_m") is None:
        return None
    return r
```

- [ ] **Step 6: Add `_shape_office`**

```python
def _shape_office(o: dict) -> Optional[dict]:
    """Response-shape a bureaucracy office feature. Used for both BOD
    Bürgerämter (which carry address+website already normalized in
    Index.buergeramt_near) and curated federal-directory offices
    (Finanzamt/Standesamt/LEA/Arbeitsagentur — all already
    {name,address,lat,lon,distance_m}).

    walk_min is computed here from distance_m via _walk_minutes and
    rounded to int (matches the tile-face rounding rule from Spec B)."""
    d = o.get("distance_m")
    r = _prune({
        "name": (o.get("name") or "").strip(),
        "lat":  o.get("lat"), "lon": o.get("lon"),
        "distance_m": d,
        "address": (o.get("address") or "").strip(),
        "website": (o.get("website") or "").strip(),
        "walk_min": round(_walk_minutes(d)) if isinstance(d, (int, float)) else None,
    })
    if not r.get("name") or not _valid_latlon(r) or r.get("distance_m") is None:
        return None
    return r
```

- [ ] **Step 7: Add `_shape_refuge_quiet` and `_shape_refuge_trees`**

```python
def _shape_refuge_quiet(q: dict, amber_quiet_m: int) -> list:
    """Return [feature] iff the quiet zone is within amber radius; else [].
    Refuge is composite (quiet zone OR tree crown) — a tile that went
    amber via TREES alone should NOT surface a distant quiet zone as a
    feature because the map pin would be misleading."""
    if not q or q.get("distance_m") is None:
        return []
    if q["distance_m"] > amber_quiet_m:
        return []
    r = _prune({
        "name": (q.get("name") or "").strip() or "Quiet zone",
        "lat":  q.get("lat"), "lon": q.get("lon"),
        "distance_m": q.get("distance_m"),
        "size_ha": q.get("size_ha"),
        "kind":    q.get("kind"),
    })
    if not _valid_latlon(r):
        return []
    return [r]


def _shape_refuge_trees(t: dict) -> dict:
    """Return trees summary for refuge tile's metadata. Passes through
    Index.trees_bbox keys, pruned. Returns {} if trees fetch failed
    (frontend hides the trees block when empty)."""
    if not t or t.get("error"):
        return {}
    top = t.get("top_species") or []
    return _prune({
        "count":               t.get("count"),
        "avg_age_yr":          t.get("avg_age_yr"),
        "tallest_m":           t.get("tallest_m"),
        "crown_coverage_pct":  t.get("crown_coverage_pct"),
        "top_species": [{"name": s.get("name"), "n": s.get("n")}
                        for s in top[:5] if s.get("name")],
    })
```

Note: `_shape_refuge_trees` might need `Optional` typing; `Optional` is likely already imported in scorer.py.

- [ ] **Step 8: Check that `Optional` is imported**

```bash
grep -n "from typing" app/core/scorer.py
```

If `Optional` is missing, extend the typing import at the top of the file:

```python
from typing import Optional
```

- [ ] **Step 9: Add shape-helper asserts in the module's `__main__` block**

Locate the `if __name__ == "__main__":` block. After the existing bureaucracy composer OK line, append:

```python
    # -- Spec D shape helpers -----------------------------------------------
    # _prune drops None + "" but keeps 0, False, [], {}
    assert _prune({"a":"x","b":None,"c":"","d":0,"e":False,"f":[],"g":{}}) \
        == {"a":"x","d":0,"e":False,"f":[],"g":{}}

    # _int_or_none
    assert _int_or_none("65") == 65
    assert _int_or_none(65)   == 65
    assert _int_or_none(None) is None
    assert _int_or_none("")   is None
    assert _int_or_none("abc") is None

    # _valid_latlon
    assert _valid_latlon({"lat": 52.5, "lon": 13.4}) is True
    assert _valid_latlon({"lat": 100.0, "lon": 13.4}) is False
    assert _valid_latlon({"lat": None, "lon": 13.4})  is False
    assert _valid_latlon({"lat": 52.5})                is False

    # _shape_kita — realistic BOD input
    _fm_k = _CFG_YF.kita_field_map
    _raw = {"name": "Kita Sonnenschein",
            "lat": 52.5388, "lon": 13.3948, "distance_m": 180,
            "props": {_fm_k["capacity"]: "65",
                      _fm_k["operator_type"]: "freie Träger",
                      _fm_k["approach"]: "Situationsansatz"}}
    assert _shape_kita(_raw, _fm_k) == {
        "name": "Kita Sonnenschein",
        "lat": 52.5388, "lon": 13.3948, "distance_m": 180,
        "capacity": 65, "operator_type": "freie Träger",
        "approach": "Situationsansatz"}
    # Drops when required fields missing
    assert _shape_kita({"name": "", "lat": 52.5, "lon": 13.4,
                        "distance_m": 100, "props": {}}, _fm_k) is None
    assert _shape_kita({"name": "X", "distance_m": 100, "props": {}}, _fm_k) is None

    # _shape_playground
    _pg = {"name": "Marheinekeplatz, Spiel", "lat": 52.489, "lon": 13.396,
           "distance_m": 75, "props": {"katasterfl": 446, "sanierjahr": "2018"}}
    assert _shape_playground(_pg) == {
        "name": "Marheinekeplatz, Spiel",
        "lat": 52.489, "lon": 13.396, "distance_m": 75,
        "area_m2": 446, "renovated_year": 2018}
    _pg_bare = {"name": "P2", "lat": 52.5, "lon": 13.4, "distance_m": 200,
                "props": {}}
    assert _shape_playground(_pg_bare) == {
        "name": "P2", "lat": 52.5, "lon": 13.4, "distance_m": 200}

    # _shape_paediatric_gp — realistic OSM tags
    _gp = {"name": "Praxis für Kinderheilkunde Dr. Berns",
           "lat": 52.4893, "lon": 13.3889, "distance_m": 430,
           "tags": {"addr:street": "Bergmannstraße", "addr:housenumber": "5",
                    "addr:postcode": "10961", "addr:city": "Berlin",
                    "phone": "+49 30 693 80 05",
                    "website": "https://kinderarztpraxis-berns.de",
                    "opening_hours": "Mo-Fr 09:00-12:00; Mo,Tu,Th 15:00-18:00",
                    "wheelchair": "yes"}}
    _rgp = _shape_paediatric_gp(_gp)
    assert _rgp["address"] == "Bergmannstraße 5, 10961 Berlin"
    assert _rgp["phone"]   == "+49 30 693 80 05"
    assert _rgp["website"] == "https://kinderarztpraxis-berns.de"
    assert _rgp["hours"].startswith("Mo-Fr")
    assert _rgp["wheelchair"] is True
    # wheelchair only surfaces on "yes" (not "limited" / "no" / missing)
    _gp2 = {**_gp, "tags": {**_gp["tags"], "wheelchair": "limited"}}
    assert "wheelchair" not in _shape_paediatric_gp(_gp2)

    # _shape_office — walk_min computed via _walk_minutes and rounded
    _off = {"name": "Bürgeramt X",
            "address": "Y-Str. 1, 10000 Berlin",
            "lat": 52.5, "lon": 13.4, "distance_m": 620,
            "website": "https://x.example/"}
    _roff = _shape_office(_off)
    assert _roff["walk_min"] == 10        # 620 / 62 = 10.0
    assert _roff["website"]  == "https://x.example/"

    # _shape_refuge_quiet — within amber returns [feature]; beyond returns []
    _q_within = {"name": "Volkspark", "lat": 52.53, "lon": 13.42,
                 "distance_m": 350, "size_ha": 29, "kind": "Erholungsgebiet"}
    assert _shape_refuge_quiet(_q_within, 1000) == [{
        "name": "Volkspark", "lat": 52.53, "lon": 13.42,
        "distance_m": 350, "size_ha": 29, "kind": "Erholungsgebiet"}]
    assert _shape_refuge_quiet({"name": "Far", "lat": 52.6, "lon": 13.5,
                                "distance_m": 5000}, 1000) == []
    assert _shape_refuge_quiet(None, 1000) == []

    # _shape_refuge_trees — pass through, drop empties, cap top_species
    _tr = {"count": 42, "avg_age_yr": 35, "tallest_m": 22,
           "crown_coverage_pct": 27,
           "top_species": [{"name":"Silberlinde","n":12},
                           {"name":"Winterlinde","n":8},
                           {"name":"","n":0}]}
    _rtr = _shape_refuge_trees(_tr)
    assert _rtr["count"] == 42
    assert _rtr["top_species"] == [{"name":"Silberlinde","n":12},
                                    {"name":"Winterlinde","n":8}]
    assert _shape_refuge_trees({"error": "trees down"}) == {}
    assert _shape_refuge_trees(None) == {}

    print("scorer.py: Spec D shape helpers OK")
```

Note the block references `_CFG_YF` which was already defined by Spec A's boundary-sweep block. If for some reason it's not in scope, add:

```python
    from app.cities.berlin import BERLIN as _CFG_YF
```

- [ ] **Step 10: Run scorer selfcheck; expect PASS**

```bash
python -m app.core.scorer
```

Expected tail:
```
scorer.py selfcheck OK
scorer.py: young_family tier boundary sweeps OK
scorer.py: young_family composer + provenance OK
scorer.py: bureaucracy tier boundary sweeps OK
scorer.py: bureaucracy composer OK
scorer.py: Spec D shape helpers OK
```

- [ ] **Step 11: Commit**

```bash
git add app/core/scorer.py
git commit -m "Add Spec D shape helpers (_prune, _shape_*)"
```

---

## Task 2: Extend `young_family_lens` composer to emit features + metadata

**Files:**
- Modify: `app/core/scorer.py` — inside `young_family_lens(...)`, extend the tile-assembly loop to add `features` + `metadata` (refuge)
- Modify: `app/core/scorer.py` — extend `__main__` composer asserts to verify shape

**Interfaces:**
- Consumes: `_shape_kita`, `_shape_playground`, `_shape_paediatric_gp`, `_shape_refuge_quiet`, `_shape_refuge_trees` from Task 1
- Produces: every tile in the returned `tiles` list now has a `features` list (may be empty); the `refuge` tile also has `metadata = {"trees": {...}}`

**Notes:** The composer currently assembles `tile` from `{key, label, icon, tier, rule, numeric, caveat, sources}`. This task extends that assembly. The threshold dict for refuge is `thresholds["refuge"]` — has key `amber_quiet_m` per Spec A.

- [ ] **Step 1: Locate the tile-assembly loop inside `young_family_lens`**

```bash
grep -n "def young_family_lens\|for key, res in results" app/core/scorer.py
```

You'll see something like:

```python
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
```

- [ ] **Step 2: Extend the assembly loop with per-tile-key features + refuge metadata**

Replace the existing `tiles.append({...})` with:

```python
tiles = []
for key, res in results:
    label, icon, caveat = tile_meta[key]
    tile = {
        "key":     key,
        "label":   label,
        "icon":    icon,
        "tier":    res["tier"],
        "rule":    res["rule"],
        "numeric": res["numeric"],
        "caveat":  caveat,
        "sources": _sources_for(cfg, key, res["tier"]),
    }
    # -- Spec D: features per tile ---------------------------------------
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
        tile["features"] = _shape_refuge_quiet(
            quiet_zone, thresholds["refuge"]["amber_quiet_m"])
        tile["metadata"] = {"trees": _shape_refuge_trees(trees)}
    else:
        # noise, heat, air — aggregate readings, no per-feature list
        tile["features"] = []
    tiles.append(tile)
```

- [ ] **Step 3: Add composer-output asserts in `__main__`**

Locate the existing `young_family composer + provenance OK` block. Extend it with feature-shape asserts. Add just before the `print("scorer.py: young_family composer + provenance OK")`:

```python
    # -- Spec D: features on young_family output ----------------------------
    _r_full = young_family_lens(
        _CFG_YF, _StubIndex(), 13.4, 52.5,
        air={"no2_ugm3": 15}, heat={"day_class": "geringe Belastung"},
        noise={"l_den": {"total": 50}},
        amenities={"playgrounds": {"items": [
            {"name": "P1", "lat": 52.5, "lon": 13.4, "distance_m": 350,
             "props": {"katasterfl": 500}}]},
                   "gps": {"items": []}},
        trees={"count": 40, "crown_coverage_pct": 30,
               "top_species": [{"name":"Silberlinde","n":10}]},
        quiet_zone={"name": "Q", "lat": 52.5, "lon": 13.4, "distance_m": 380},
    )
    _by = {t["key"]: t for t in _r_full["tiles"]}
    # Every tile has `features` key
    for k in ["kita","playground","pediatrician","noise","heat","air","refuge"]:
        assert "features" in _by[k], f"{k} missing features"
    # Aggregate tiles → []
    assert _by["noise"]["features"] == []
    assert _by["heat"]["features"]  == []
    assert _by["air"]["features"]   == []
    # Refuge always carries metadata.trees (populated or empty dict)
    assert "metadata" in _by["refuge"]
    assert "trees" in _by["refuge"]["metadata"]
    # Playground feature shaped correctly
    assert _by["playground"]["features"] == [
        {"name":"P1","lat":52.5,"lon":13.4,"distance_m":350,"area_m2":500}]
    # Refuge quiet zone becomes 1 feature (within 400m green threshold)
    assert len(_by["refuge"]["features"]) == 1
    assert _by["refuge"]["features"][0]["name"] == "Q"

    # Refuge with quiet zone BEYOND amber: features drops to []
    _r_no_quiet = young_family_lens(
        _CFG_YF, _StubIndex(), 13.4, 52.5,
        air={"no2_ugm3": 15}, heat={"day_class": "geringe Belastung"},
        noise={"l_den": {"total": 50}},
        amenities={"playgrounds": {"items": []}, "gps": {"items": []}},
        trees={"count": 40, "crown_coverage_pct": 30},
        quiet_zone={"name":"Far","lat":52.6,"lon":13.5,"distance_m":5000},
    )
    _rf = next(t for t in _r_no_quiet["tiles"] if t["key"] == "refuge")
    assert _rf["features"] == []
    assert _rf["metadata"]["trees"]["crown_coverage_pct"] == 30
```

- [ ] **Step 4: Run scorer selfcheck**

```bash
python -m app.core.scorer
```

Expected: existing OK lines + `scorer.py: young_family composer + provenance OK` (unchanged tail).

- [ ] **Step 5: Commit**

```bash
git add app/core/scorer.py
git commit -m "young_family_lens: emit features + metadata per tile"
```

---

## Task 3: Extend `bureaucracy_lens` composer to emit features

**Files:**
- Modify: `app/core/scorer.py` — inside `bureaucracy_lens(...)`, extend the tile-assembly loop with per-tile-key features
- Modify: `app/core/scorer.py` — extend the bureaucracy composer asserts in `__main__` block

**Interfaces:**
- Consumes: `_shape_office` from Task 1
- Produces: every tile in `bureaucracy_lens(...)`'s returned `tiles` has `features` — a list of 0..N office dicts

**Notes:** Nearest-single tiles (finanzamt, standesamt, lea) always have `features.length == 1` when data is present. Nearest-of-many (buergeramt, arbeitsagentur) have all offices within the tier fn's radius.

- [ ] **Step 1: Locate the tile-assembly loop inside `bureaucracy_lens`**

```bash
grep -n "def bureaucracy_lens\|for key, res in results" app/core/scorer.py
```

- [ ] **Step 2: Extend the loop with features**

Same pattern as young_family. Replace the existing `tiles.append({...})` with:

```python
tiles = []
for key, res in results:
    label, icon, caveat = tile_meta[key]
    tile = {
        "key":     key,
        "label":   label,
        "icon":    icon,
        "tier":    res["tier"],
        "rule":    res["rule"],
        "numeric": res["numeric"],
        "caveat":  caveat,
        "sources": _sources_for(cfg, key, res["tier"]),
    }
    # -- Spec D: features per bureaucracy tile ---------------------------
    if key == "buergeramt":
        tile["features"] = [f for f in
            (_shape_office(o) for o in buergeramts) if f]
    elif key == "arbeitsagentur":
        tile["features"] = [f for f in
            (_shape_office(o) for o in arbeitsagentur) if f]
    elif key == "finanzamt":
        single = _shape_office(finanzamt) if finanzamt else None
        tile["features"] = [single] if single else []
    elif key == "standesamt":
        single = _shape_office(standesamt) if standesamt else None
        tile["features"] = [single] if single else []
    elif key == "lea":
        single = _shape_office(lea) if lea else None
        tile["features"] = [single] if single else []
    else:
        tile["features"] = []
    tiles.append(tile)
```

Confirm the variable names (`buergeramts`, `finanzamt`, `standesamt`, `lea`, `arbeitsagentur`) match what the composer already computed above. If any differs (e.g. the composer named it `_arbeitsagenturs`), match the existing name.

- [ ] **Step 3: Add composer-output asserts in `__main__`**

Locate the existing `scorer.py: bureaucracy composer OK` block. Extend it just before that print:

```python
    # -- Spec D: features on bureaucracy output ----------------------------
    _r_bur_full = bureaucracy_lens(_CFG_BUR, _StubIndex(), 13.4, 52.5)
    _by_bur = {t["key"]: t for t in _r_bur_full["tiles"]}
    # Every bureaucracy tile has features
    for k in ["buergeramt","finanzamt","standesamt","lea","arbeitsagentur"]:
        assert "features" in _by_bur[k], f"{k} missing features"
    # Nearest-single tiles have exactly 1 feature (when stub returns them)
    assert len(_by_bur["finanzamt"]["features"])  == 1
    assert len(_by_bur["standesamt"]["features"]) == 1
    assert len(_by_bur["lea"]["features"])        == 1
    # Every feature has walk_min (int, from _shape_office)
    for k in ["buergeramt","finanzamt","standesamt","lea","arbeitsagentur"]:
        for f in _by_bur[k]["features"]:
            assert isinstance(f.get("walk_min"), int), f
    # Malformed input → filtered out
    class _StubEmpty(_StubIndex):
        def buergeramt_near(self, lon, lat, r=3000): return []
        def arbeitsagentur_near(self, lon, lat, r=5000): return []
        def finanzamt_nearest(self, lon, lat): return None
        def standesamt_for(self, lon, lat): return None
    # LEA feature will still be present (comes from cfg.lea_office, not the index)
    _r_empty = bureaucracy_lens(_CFG_BUR, _StubEmpty(), 13.4, 52.5)
    _bym = {t["key"]: t for t in _r_empty["tiles"]}
    assert _bym["buergeramt"]["features"]     == []
    assert _bym["arbeitsagentur"]["features"] == []
    assert _bym["finanzamt"]["features"]      == []
    assert _bym["standesamt"]["features"]     == []
```

- [ ] **Step 4: Run scorer selfcheck**

```bash
python -m app.core.scorer
```

Expected: previous OK lines + `scorer.py: bureaucracy composer OK` at the tail (unchanged).

- [ ] **Step 5: Commit**

```bash
git add app/core/scorer.py
git commit -m "bureaucracy_lens: emit features per tile"
```

---

## Task 4: Live selfcheck asserts for feature arrays

**Files:**
- Modify: `app/selfcheck.py` — extend `run_live_selfcheck` with feature-array asserts on Kastanienallee 12 + Bergmannstraße 27

**Interfaces:**
- Consumes: the extended composer output from Tasks 2 + 3 (features arrays present on both lenses)
- Produces: `python -m app.selfcheck` now asserts feature shape on known-good Berlin addresses

**Notes:** The existing young_family + bureaucracy live-selfcheck blocks already compute `lens_yf` / `lens_bur` / `lens_b`. This task adds new asserts inside those existing blocks — no new blocks.

- [ ] **Step 1: Locate the young_family lens block in `run_live_selfcheck`**

```bash
grep -n "young_family lens asserts OK\|bureaucracy lens asserts OK" app/selfcheck.py
```

- [ ] **Step 2: Append feature asserts to the Kastanienallee 12 young_family block**

Immediately BEFORE the `print("  young_family lens asserts OK")` line, add:

```python
    # -- Spec D: feature arrays present ---------------------------------
    _by = {t["key"]: t for t in lens_yf["tiles"]}
    _kita_f = _by["kita"]["features"]
    assert isinstance(_kita_f, list) and len(_kita_f) >= 3, \
        f"expected ≥3 kita features in dense Pankow, got {len(_kita_f)}"
    _first = _kita_f[0]
    assert _first.get("name") and _first.get("distance_m", 0) > 0
    assert 52.3 < _first["lat"] < 52.7 and 13.0 < _first["lon"] < 13.8
    # At least one kita should carry BOD e_platz capacity (usually all do)
    assert any("capacity" in f for f in _kita_f), \
        "BOD kita records should carry e_platz capacity for most entries"
    # Aggregate tiles → []
    assert _by["noise"]["features"] == []
    assert _by["heat"]["features"]  == []
    assert _by["air"]["features"]   == []
    # Refuge metadata carries trees dict (may be empty on trees WFS outage)
    assert _by["refuge"].get("metadata", {}).get("trees") is not None
```

- [ ] **Step 3: Locate the Bergmannstraße 27 block (inside the same run_live_selfcheck)**

The existing block computes `lens_b`. Immediately BEFORE the block's closing `print("  bureaucracy lens asserts OK")`, wait — Bergmannstraße 27 selfcheck asserts sit inside the bureaucracy live-selfcheck block. Let me re-check by looking at the file.

Actually the young_family live-selfcheck already asserts pediatrician tier at Bergmannstraße 27 (from Spec A Task 7). Look for `lens_b` inside `run_live_selfcheck` — that's the Bergmannstraße young_family lens result. Extend that block.

Find:

```python
    if berg:
        lens_b = scorer.young_family_lens(cfg, index, berg["lon"], berg["lat"], ...)
```

After the existing paediatric tier assertion (`_by_b["pediatrician"]["tier"] == "green"`), add:

```python
        # -- Spec D: pediatrician feature has phone + website + hours ---
        _ped_features = _by_b["pediatrician"]["features"]
        assert len(_ped_features) >= 1
        _berns = next((f for f in _ped_features if "Berns" in f.get("name", "")), None)
        assert _berns is not None, "Dr. Berns expected in pediatrician features"
        assert _berns.get("phone", "").startswith("+49"), _berns
        assert _berns.get("website", "").startswith("http"), _berns
        assert "Mo" in _berns.get("hours", ""), _berns.get("hours")
```

- [ ] **Step 4: Extend the bureaucracy live-selfcheck block**

The existing bureaucracy block computes `lens_bur` at Kastanienallee 12. Immediately BEFORE the `print("  bureaucracy lens asserts OK")` line, append:

```python
    # -- Spec D: bureaucracy feature arrays ----------------------------
    _by_bur = {t["key"]: t for t in lens_bur["tiles"]}
    # Standesamt: exactly 1 feature, name contains "Pankow"
    assert len(_by_bur["standesamt"]["features"]) == 1
    assert "Pankow" in _by_bur["standesamt"]["features"][0]["name"]
    # LEA: exactly 1 feature, name contains "LEA"
    assert len(_by_bur["lea"]["features"]) == 1
    assert "LEA" in _by_bur["lea"]["features"][0]["name"]
    # Every buergeramt feature has walk_min as int
    for f in _by_bur["buergeramt"]["features"]:
        assert isinstance(f.get("walk_min"), int), f
```

- [ ] **Step 5: Run the full app selfcheck; expect PASS**

```bash
python -m app.selfcheck
```

Expected: existing OK lines, plus the new asserts pass silently, plus `young_family lens asserts OK` and `bureaucracy lens asserts OK` and `→ live selfcheck OK`.

- [ ] **Step 6: Commit**

```bash
git add app/selfcheck.py
git commit -m "Live selfcheck: assert feature arrays on known-good addresses"
```

---

## Task 5: CSS for 2-col layout, modal, features, map

**Files:**
- Modify: `web/static/app.css` — append the full Spec D CSS block

**Interfaces:**
- Produces: CSS classes `.lens-body`, `.lens-tiles-col`, `.lens-map-col`, `#lens-map`, `.lens-tile:hover/:focus-visible`, `.lens-modal` + sub-selectors, `.lens-feature` + sub, `.modal-trees` + sub, `.modal-explanation`, `.lens-map-col .map-hint`, media query for mobile. `.info-tip` / `.info-body.details-block` / `.det-row` are pre-existing (`app.css:409-421`) — reused as-is.

**Notes:** Task 5 is CSS-only. Nothing renders differently yet — the JS in Tasks 6-9 references these selectors. Reviewer inspects the CSS for well-formed rules + neumorphic-token discipline.

- [ ] **Step 1: Locate the tail of `web/static/app.css`**

```bash
tail -20 web/static/app.css
```

The Spec D CSS lands at the end of the file, under a new section comment.

- [ ] **Step 2: Append the Spec D CSS block**

```css
/* --- Spec D: clickable lens tiles, 2-col layout, modal, map ------------- */

/* 2-col split — mirrors raw-mode Amenities .grid + .map-cell */
.lens-body        { display:flex; gap:14px; margin-top:0; }
.lens-tiles-col   { position:relative; flex:1.15 1 0; min-width:0; }
.lens-map-col     { flex:.85 1 0; min-width:0; position:relative; }
#lens-map         { height:100%; min-height:500px; border-radius:16px; overflow:hidden; }

@media (max-width: 900px) {
  .lens-body      { flex-direction:column; }
  #lens-map       { min-height:320px; }
}

/* Tile — now a <button>; tighter grid + padding; drop caveat from face */
.lens-grid        { grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap:12px; }
.lens-tile        { min-height:100px; padding:12px 14px 12px 18px; cursor:pointer;
                    border:0; text-align:left; width:100%; }
.lens-tile:hover  { background: var(--result-bg-hover); }
.lens-tile:focus-visible { outline:2px solid var(--brand); outline-offset:2px; }

/* Modal — reuses .amen-modal visual language via new selectors */
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
.lens-modal .modal-head .icon-badge {
  width:44px; height:44px; border-radius:12px;
  display:flex; align-items:center; justify-content:center;
  background:var(--neumo-bg);
}
.lens-modal .modal-head .icon-badge svg { width:22px; height:22px; }
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
.lens-feature .info-tip        { flex-shrink:0; }

/* Refuge trees block */
.modal-trees                   { padding:10px 14px; background:var(--neumo-bg);
                                 border-radius:10px; margin-bottom:12px; }
.modal-trees-summary           { font-weight:600; }
.modal-trees-species           { color:var(--ink-2); font-size:13px; margin-top:4px; }

/* Provenance footer */
.lens-modal .modal-provenance  { color:var(--muted); font-size:12px;
                                 padding-top:8px; border-top:1px solid var(--border); }

/* Map hint pill — mirrors raw-mode .map-hint */
.lens-map-col .map-hint        { position:absolute; top:12px; left:12px; z-index:500;
                                 background: rgba(255,255,255,.94);
                                 padding:7px 12px; border-radius:8px;
                                 font-size:12px; font-weight:600; color:var(--ink-2);
                                 box-shadow: var(--sh-1); pointer-events:none; }

/* Numbered pin — for L.divIcon HTML */
.lens-pin                      { width:30px; height:30px; border-radius:50%;
                                 background:var(--pin-color, #9CA3AF); color:#fff;
                                 display:flex; align-items:center; justify-content:center;
                                 font:700 12px 'Plus Jakarta Sans', system-ui, sans-serif;
                                 box-shadow: 0 2px 6px rgba(17,24,39,.35); }

/* Empty state when features list is empty on a geo tile */
.modal-empty                   { padding:14px; color:var(--muted); font-style:italic;
                                 background:var(--neumo-bg); border-radius:10px; }
```

- [ ] **Step 3: Visual smoke test — reload the browser**

```bash
# Frontend static files serve fresh per request — no server restart needed.
# Just hard-refresh in the browser.
```

Open `http://127.0.0.1:8000/` and confirm:
- The app still loads normally.
- No new visual artifacts appear (Task 5 is CSS-only; nothing references the new classes yet).
- No CSS parse errors in DevTools console.

- [ ] **Step 4: Commit**

```bash
git add web/static/app.css
git commit -m "Add Spec D CSS: 2-col layout, modal, features, map, numbered pin"
```

---

## Task 6: Rewrite `renderLensSingle` for 2-col + `renderLensTile` → `<button>`

**Files:**
- Modify: `web/static/app.js` — replace `renderLensSingle`, replace `renderLensTile`

**Interfaces:**
- Consumes: existing `renderLensPicker(active)` from Spec B, existing `escapeHtml`, `ico = {...}` — all pre-existing.
- Produces:
  - `renderLensSingle(addr)` — 2-col HTML: `.lens-picker-row`, `.lens-body` (`.lens-tiles-col` + `.lens-map-col`), `.lens-provenance` footer. Modal element `#lens-modal` embedded inside `.lens-tiles-col`.
  - `renderLensTile(tile)` — `<button class="lens-tile ..." data-tile-key="<key>">` with icon, label, tier badge, rule, numeric. NO caveat on face (moved to modal in Task 7).
- Ties in later:
  - Modal populated by `openLensModal(tileKey)` — Task 9.
  - Map initialized by `initLensMap(addr)` — Task 8.

**Notes:** After this task, tiles render as buttons but clicking does nothing (no handler yet). Map div renders empty (no Leaflet init yet). Layout is 2-col. Modal element sits hidden.

- [ ] **Step 1: Locate existing `renderLensSingle` and `renderLensTile`**

```bash
grep -n "^function renderLensSingle\|^function renderLensTile" web/static/app.js
```

- [ ] **Step 2: Replace `renderLensSingle`**

Find the existing function body (a big template-string with `.lens-picker-row`, current `.lens-empty` path, current picker/tile grid + prov). Replace with:

```javascript
function renderLensSingle(addr) {
  const active = getActiveLens();
  const lens = addr && addr.lens && addr.lens[active];
  if (!lens || lens.error) {
    return `
      <div class="lens-picker-row">
        ${renderLensPicker(active)}
      </div>
      <div class="lens-empty">Lens unavailable for this address.</div>
    `;
  }
  const tilesHtml = lens.tiles.map(renderLensTile).join('');
  const audience  = escapeHtml(lens.audience || '');
  const prov = lens.provenance
    ? `<footer class="lens-provenance">${escapeHtml(lens.provenance)}</footer>`
    : '';
  return `
    <div class="lens-picker-row">
      ${renderLensPicker(active)}
      ${audience ? `<p class="lens-audience">${audience}</p>` : ''}
    </div>
    <div class="lens-body">
      <div class="lens-tiles-col">
        <div class="lens-grid">${tilesHtml}</div>
        <div class="lens-modal" id="lens-modal" role="dialog"
             aria-modal="true" aria-labelledby="lens-modal-title" hidden></div>
      </div>
      <div class="lens-map-col">
        <div class="map-hint" id="lens-map-hint">Click a tile to plot its locations</div>
        <div id="lens-map"></div>
      </div>
    </div>
    ${prov}
  `;
}
```

- [ ] **Step 3: Replace `renderLensTile`**

Find the existing function body and replace with:

```javascript
function renderLensTile(tile) {
  const tier    = tile.tier || 'unknown';
  const iconSVG = (typeof ico !== 'undefined' && ico[tile.icon]) || '';
  const badge   = tier === 'unknown' ? 'N/A' : tier.toUpperCase();
  const aria    = `${tile.label}, tier ${tier}: ${tile.rule}`;
  const numeric = tile.numeric
    ? `<div class="tile-numeric">${escapeHtml(tile.numeric)}</div>`
    : '';
  // Caveat is intentionally NOT rendered on the tile face — it lives in
  // the modal (renderLensModalBody) so tile heights stay consistent.
  return `
    <button class="cell lens-tile tier-${escapeHtml(tier)}"
            data-tile-key="${escapeHtml(tile.key)}"
            aria-label="${escapeHtml(aria)}"
            type="button">
      <div class="tile-head">
        <span class="tile-icon" aria-hidden="true">${iconSVG}</span>
        <span class="tile-label">${escapeHtml(tile.label)}</span>
        <span class="tile-tier-badge">${escapeHtml(badge)}</span>
      </div>
      <div class="tile-rule">${escapeHtml(tile.rule)}</div>
      ${numeric}
    </button>
  `;
}
```

- [ ] **Step 4: Reload the browser and inspect the DOM**

Hard-refresh `http://127.0.0.1:8000/`, enter Kastanienallee 12, toggle Life Mode ON. Open DevTools → Elements:

- Verify `#lens-view` contains `.lens-body` with two children: `.lens-tiles-col` (with `.lens-grid` + `#lens-modal[hidden]`) and `.lens-map-col` (with hint + `#lens-map`).
- Verify each `.lens-tile` is a `<button>` with `data-tile-key="kita"` etc.
- Verify the layout renders side-by-side on desktop (2-col) — tiles column visible, map column empty for now.

Clicking a tile does nothing (no handler yet — Task 9). That's expected.

- [ ] **Step 5: Commit**

```bash
git add web/static/app.js
git commit -m "renderLensSingle: 2-col layout; renderLensTile: <button>"
```

---

## Task 7: Modal render helpers + constants

**Files:**
- Modify: `web/static/app.js` — add module-level constants and 4 render helper functions

**Interfaces:**
- Consumes: `escapeHtml`, `ico = {...}` — pre-existing.
- Produces:
  - Module consts: `LENS_TILE_EXPLANATIONS`, `TIER_PIN_COLORS`.
  - `renderLensModalBody(tile) -> string` — HTML for the modal body.
  - `renderLensFeature(tileKey, feature, idx) -> string` — HTML for one feature `<li>`.
  - `_lensFeatureDetailHtml(tileKey, feature) -> string` — label/value rows inside the ⓘ popover; empty string when feature has no optional fields.
  - `renderLensTreesBlock(trees) -> string` — refuge tree stats block.
- Ties in later: `openLensModal()` in Task 9 will call `renderLensModalBody(tile)` to populate the modal.

**Notes:** These are pure render functions. They don't fire any interactions yet. After this task, the modal HTML can be generated on demand, but nothing calls it yet.

- [ ] **Step 1: Locate a good spot to add module-level constants**

Constants live near the top of the file with the existing `LM_STATE_KEY`, `LM_ACTIVE_KEY`, etc. Grep:

```bash
grep -n "^const LM_" web/static/app.js
```

- [ ] **Step 2: Add module-level constants near the other lens constants**

```javascript
// -- Spec D: aggregate-tile explanations (rendered in modal only) -----------
const LENS_TILE_EXPLANATIONS = {
  noise: "L_DEN is EU-standard day-evening-night noise averaging. WHO recommends ≤55 dB in residential areas; above 60 dB is linked to sleep disturbance.",
  heat:  "Berlin's Umweltatlas classifies each block's bioclimate (PET at 14:00 in summer). 'Belastung' = burden; higher classes indicate more heat stress.",
  air:   "NO₂ measured µg/m³ per street segment (Umweltatlas trend scenario). WHO 2021 annual guideline is 10 µg/m³; Germany's legal limit is 40.",
};

// -- Spec D: map-pin color per tier ------------------------------------------
const TIER_PIN_COLORS = {
  green:   '#22C55E',   // matches --success
  amber:   '#F59E0B',   // matches --amber
  red:     '#EF4444',   // matches --danger
  unknown: '#9CA3AF',
};
```

- [ ] **Step 3: Add `renderLensFeature`**

Add near the other render functions (grep for `renderLensSingle` to find the neighborhood):

```javascript
function renderLensFeature(tileKey, feature, idx) {
  const details = _lensFeatureDetailHtml(tileKey, feature);
  // ⓘ button only if the feature has anything beyond required fields.
  // Matches raw-mode Amenities pattern (app.js:1801 — `details?`).
  const tip = details
    ? `<details class="info-tip"><summary aria-label="More info">${ico.info || 'ⓘ'}</summary><div class="info-body details-block">${details}</div></details>`
    : '';
  const dist = feature.distance_m != null
    ? `${feature.distance_m} m`
    : '';
  return `
    <li class="lens-feature" data-feature-idx="${idx}">
      <span class="feature-marker">${idx + 1}</span>
      <span class="feature-name">${escapeHtml(feature.name)}</span>
      <span class="feature-distance">${escapeHtml(dist)}</span>
      ${tip}
    </li>
  `;
}
```

- [ ] **Step 4: Add `_lensFeatureDetailHtml`**

```javascript
function _lensFeatureDetailHtml(tileKey, f) {
  const rows = [];
  const row = (label, val) =>
    `<div class="det-row"><span class="det-label">${label}</span><span class="det-val">${val}</span></div>`;

  // Common optional fields
  if (f.address)          rows.push(row('Address',   escapeHtml(f.address)));
  if (f.walk_min != null) rows.push(row('Walk time', `~${f.walk_min} min`));
  if (f.phone)            rows.push(row('Phone',
                              `<a href="tel:${escapeHtml(f.phone)}">${escapeHtml(f.phone)}</a>`));
  if (f.website)          rows.push(row('Website',
                              `<a href="${escapeHtml(f.website)}" target="_blank" rel="noopener">Visit ↗</a>`));
  if (f.hours)            rows.push(row('Hours',     escapeHtml(f.hours)));
  if (f.wheelchair)       rows.push(row('Access',    'Step-free'));

  // Tile-specific rows
  if (tileKey === 'kita') {
    if (f.capacity != null)      rows.push(row('Places',    escapeHtml(String(f.capacity))));
    if (f.operator_type)         rows.push(row('Operator',  escapeHtml(f.operator_type)));
    if (f.approach)              rows.push(row('Approach',  escapeHtml(f.approach)));
  } else if (tileKey === 'playground') {
    if (f.area_m2 != null)       rows.push(row('Area',       `${f.area_m2} m²`));
    if (f.renovated_year != null) rows.push(row('Renovated', escapeHtml(String(f.renovated_year))));
  } else if (tileKey === 'refuge') {
    if (f.size_ha != null)       rows.push(row('Size',       `${f.size_ha} ha`));
    if (f.kind)                  rows.push(row('Type',       escapeHtml(f.kind)));
  }

  return rows.join('');
}
```

- [ ] **Step 5: Add `renderLensTreesBlock`**

```javascript
function renderLensTreesBlock(trees) {
  if (!trees) return '';
  const bits = [];
  if (trees.count != null)              bits.push(`${trees.count} street trees`);
  if (trees.crown_coverage_pct != null) bits.push(`${trees.crown_coverage_pct}% crown coverage`);
  if (trees.avg_age_yr != null)         bits.push(`avg age ${trees.avg_age_yr}y`);
  if (trees.tallest_m != null)          bits.push(`tallest ${trees.tallest_m}m`);
  if (bits.length === 0) return '';
  const species = Array.isArray(trees.top_species) && trees.top_species.length
    ? `Top: ${trees.top_species.slice(0, 3).map(s => escapeHtml(s.name)).join(', ')}`
    : '';
  return `
    <div class="modal-trees">
      <div class="modal-trees-summary">${bits.join(' · ')}</div>
      ${species ? `<div class="modal-trees-species">${species}</div>` : ''}
    </div>
  `;
}
```

- [ ] **Step 6: Add `renderLensModalBody`**

```javascript
function renderLensModalBody(tile) {
  const iconSVG = (typeof ico !== 'undefined' && ico[tile.icon]) || '';
  const tier    = tile.tier || 'unknown';
  const badge   = tier === 'unknown' ? 'N/A' : tier.toUpperCase();
  const features = Array.isArray(tile.features) ? tile.features : [];
  const explanation = LENS_TILE_EXPLANATIONS[tile.key] || '';
  const trees = tile.metadata && tile.metadata.trees;

  const caveat = tile.caveat
    ? `<div class="modal-caveat">${escapeHtml(tile.caveat)}</div>`
    : '';
  const explBlock = explanation
    ? `<div class="modal-explanation">${escapeHtml(explanation)}</div>`
    : '';
  const featuresHtml = features.length
    ? `<ul class="modal-features-list">${
        features.map((f, i) => renderLensFeature(tile.key, f, i)).join('')
      }</ul>`
    : (explanation ? '' : '<div class="modal-empty">No matching items nearby.</div>');
  const treesHtml = renderLensTreesBlock(trees);
  const sourcesHtml = Array.isArray(tile.sources) && tile.sources.length
    ? `<div class="modal-provenance">Sources: ${
        tile.sources.map(escapeHtml).join(' · ')
      }</div>`
    : '';

  return `
    <button class="lens-modal-close" aria-label="Close details" type="button">✕</button>
    <div class="modal-head">
      <span class="icon-badge tier-${escapeHtml(tier)}" aria-hidden="true">${iconSVG}</span>
      <h3 id="lens-modal-title">${escapeHtml(tile.label)}</h3>
      <span class="tile-tier-badge tier-${escapeHtml(tier)}">${escapeHtml(badge)}</span>
    </div>
    <div class="modal-rule">${escapeHtml(tile.rule || '')}</div>
    ${tile.numeric ? `<div class="modal-numeric">${escapeHtml(tile.numeric)}</div>` : ''}
    ${caveat}
    ${explBlock}
    ${featuresHtml}
    ${treesHtml}
    ${sourcesHtml}
  `;
}
```

- [ ] **Step 7: Sanity — reload and confirm no console errors**

Hard-refresh browser. Nothing renders differently yet (no caller invokes the new functions). Open DevTools → Console: no errors. Open DevTools → Sources: search for `LENS_TILE_EXPLANATIONS` and confirm it's defined.

- [ ] **Step 8: Commit**

```bash
git add web/static/app.js
git commit -m "Add modal render helpers + LENS_TILE_EXPLANATIONS + TIER_PIN_COLORS"
```

---

## Task 8: Map lifecycle (`initLensMap`, `lensNumberedPin`, `_updateLensMapPins`)

**Files:**
- Modify: `web/static/app.js` — add map state + 3 map helpers; wire `initLensMap` into `renderAllPanels`

**Interfaces:**
- Consumes: `TIER_PIN_COLORS` (from Task 7), Leaflet `L`, existing `iconPin(svg, color)` at `app.js:1983` (used only as a pattern reference — we write our own `lensNumberedPin`), existing `TILE_URL` / `TILE_ATTRIBUTION` constants (find via grep — the raw-mode `L.tileLayer` calls tell us where they live), `ico = {...}`.
- Produces:
  - Module-level state: `lensMap` (Leaflet Map or null), `lensAddressMarker` (Leaflet Marker), `lensMapFeaturePins` (array of Markers).
  - `initLensMap(addr)` — teardown any prior instance, create fresh at `#lens-map`, plant address pin.
  - `lensNumberedPin(idx, color) -> L.divIcon` — the numbered-circle pin used for feature markers.
  - `_updateLensMapPins(tile)` — clear old feature pins, add new pins from `tile.features`, fitBounds, update hint text.
  - `renderAllPanels()` calls `initLensMap(eduData.address)` after inserting lens-view innerHTML (when Life Mode ON + `eduData.address` present); calls `lensMap.remove()` cleanup when Life Mode OFF.

**Notes:** After this task, entering an address in Life Mode → address pink pin appears on the map. Clicking a tile still does nothing (Task 9 wires the click handler). The `_updateLensMapPins(tile)` helper is ready to consume.

- [ ] **Step 1: Find `TILE_URL` / `TILE_ATTRIBUTION` (or equivalent) used by raw-mode map**

```bash
grep -n "L\.tileLayer\|OpenStreetMap contributors" web/static/app.js | head -10
```

Note the exact call. Something like:

```javascript
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
            {attribution: '© OpenStreetMap contributors'}).addTo(mapRef);
```

You'll reuse the same URL + attribution in `initLensMap`. If a `TILE_URL` const exists at module level, reuse it. If it's inline in raw-mode code, either inline it in `initLensMap` too or hoist to a const at module top and reference from both sites (hoisting is one-line refactor and doesn't change raw-mode behavior). Prefer inline for this task; hoist only if it feels natural.

- [ ] **Step 2: Add module-level lens map state**

Near the other `let lm* / lens*` module state (grep for `let lensMap` — none yet — add after the constants block):

```javascript
// -- Spec D: dedicated Leaflet instance for the lens view -------------------
let lensMap             = null;
let lensAddressMarker   = null;
let lensMapFeaturePins  = [];   // Leaflet markers for the currently-open tile's features
let lensLastTileKey     = null; // for focus-restore on modal close
```

- [ ] **Step 3: Add `lensNumberedPin` helper**

```javascript
function lensNumberedPin(idx, color) {
  // divIcon HTML — .lens-pin CSS class handles size/shape; --pin-color from inline style
  return L.divIcon({
    className: '',
    html: `<div class="lens-pin" style="--pin-color:${color}" aria-label="Feature ${idx + 1}">${idx + 1}</div>`,
    iconSize: [30, 30], iconAnchor: [15, 15], popupAnchor: [0, -14],
  });
}
```

- [ ] **Step 4: Add `initLensMap`**

```javascript
function initLensMap(addr) {
  const el = document.getElementById('lens-map');
  if (!el || !addr) return;
  // Tear down any previous instance first (address change / re-render)
  if (lensMap) {
    try { lensMap.remove(); } catch (e) {}
    lensMap = null;
    lensAddressMarker = null;
    lensMapFeaturePins = [];
  }
  try {
    lensMap = L.map('lens-map', { scrollWheelZoom: false })
               .setView([addr.lat, addr.lon], 14);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap contributors',
    }).addTo(lensMap);
    lensAddressMarker = L.marker([addr.lat, addr.lon],
        { icon: iconPin(ico.home || ico.pin || '📍', '#EC4899') })
      .addTo(lensMap)
      .bindPopup('Your address');
  } catch (e) {
    // Leaflet CDN blocked or offline — fail visible but don't crash the app.
    // Tiles + modal still work; just no map pins.
    lensMap = null;
    el.innerHTML = '<div style="padding:14px;color:var(--muted);font-style:italic">Map unavailable.</div>';
  }
}
```

- [ ] **Step 5: Add `_updateLensMapPins`**

```javascript
function _updateLensMapPins(tile) {
  if (!lensMap) return;
  // Clear previous feature pins (address pin stays)
  lensMapFeaturePins.forEach(m => { try { lensMap.removeLayer(m); } catch (e) {} });
  lensMapFeaturePins = [];

  const features = Array.isArray(tile.features) ? tile.features : [];
  const hint = document.getElementById('lens-map-hint');
  if (features.length === 0) {
    if (hint) hint.textContent = 'Reading at your address';
    return;
  }

  const color = TIER_PIN_COLORS[tile.tier || 'unknown'] || TIER_PIN_COLORS.unknown;
  features.forEach((f, i) => {
    if (typeof f.lat !== 'number' || typeof f.lon !== 'number') return;
    const marker = L.marker([f.lat, f.lon], { icon: lensNumberedPin(i, color) })
      .addTo(lensMap)
      .bindPopup(`<b>${escapeHtml(f.name)}</b><br>${f.distance_m != null ? f.distance_m + ' m' : ''}`);
    marker._lensFeatureIdx = i;         // for two-way sync — see Task 9's pin-click callback
    lensMapFeaturePins.push(marker);
  });

  // Fit bounds to include address + all feature pins, with padding
  const latlngs = [
    [lensAddressMarker.getLatLng().lat, lensAddressMarker.getLatLng().lng],
    ...features.filter(f => typeof f.lat === 'number' && typeof f.lon === 'number')
               .map(f => [f.lat, f.lon])
  ];
  if (latlngs.length > 1) {
    lensMap.fitBounds(latlngs, { padding: [30, 30] });
  } else {
    lensMap.setView([lensAddressMarker.getLatLng().lat, lensAddressMarker.getLatLng().lng], 14);
  }

  if (hint) hint.textContent = `${tile.label}: ${features.length} on map`;
}
```

- [ ] **Step 6: Wire `initLensMap` into `renderAllPanels`**

Locate `renderAllPanels`. Find where it sets `lensEl.innerHTML = renderLensSingle(eduData);` (the Life Mode ON branch). Immediately after that line, call `initLensMap`:

```javascript
if (onLife) {
  lensEl.innerHTML = eduData ? renderLensSingle(eduData) : '';
  // Spec D: initialize lens map after HTML is in the DOM
  if (eduData && eduData.address) {
    initLensMap(eduData.address);
  }
}
```

And in the OFF branch (`lensEl.innerHTML = '';`), tear down:

```javascript
} else {
  lensEl.innerHTML = '';
  if (lensMap) {
    try { lensMap.remove(); } catch (e) {}
    lensMap = null;
    lensAddressMarker = null;
    lensMapFeaturePins = [];
  }
}
```

- [ ] **Step 7: Browser QA — address pin visible**

Hard-refresh the app. Enter Kastanienallee 12, Life Mode ON. Verify:
- 2-col layout with map column on the right.
- Address pink pin visible at Kastanienallee 12 coords.
- Popup on pin click reads "Your address".
- Toggle Life Mode OFF → map disappears (innerHTML cleared).
- Toggle Life Mode ON again → new map instance created, pin visible.

Clicking a tile still does nothing (Task 9 wires that). Map pans/zooms normally otherwise.

- [ ] **Step 8: Commit**

```bash
git add web/static/app.js
git commit -m "Add lens map lifecycle + numbered pin + _updateLensMapPins"
```

---

## Task 9: Interaction handlers + `dropOrphanTooltips` cleanup

**Files:**
- Modify: `web/static/app.js` — add `openLensModal`, `closeLensModal`, `_highlightLensRow`; add delegated event handlers (tile click, modal close, feature-row click, pin click callback via Leaflet, Escape key); wire tooltip-portal `dropOrphanTooltips` cleanup calls.

**Interfaces:**
- Consumes: `renderLensModalBody` (Task 7), `_updateLensMapPins` (Task 8), Leaflet markers with `._lensFeatureIdx` set by `_updateLensMapPins` (Task 8), existing `dropOrphanTooltips` (pre-existing at `app.js:1547-1610` area — the tooltip portal mechanism).
- Produces:
  - `openLensModal(tileKey)`.
  - `closeLensModal()`.
  - `_highlightLensRow(idx)`.
  - Event handlers wired at module init.

**Notes:** After this task, the full interactive flow works. Tile click opens modal, features render, pins appear, ⓘ popovers work, row↔pin sync works, Escape/close-button close modal, Life Mode OFF cleans everything up.

- [ ] **Step 1: Add `openLensModal`**

Near `renderLensModalBody`:

```javascript
function openLensModal(tileKey) {
  if (!eduData || !eduData.lens) return;
  const active = getActiveLens();
  const lens = eduData.lens[active];
  if (!lens || !lens.tiles) return;
  const tile = lens.tiles.find(t => t.key === tileKey);
  if (!tile) return;

  const modal = document.getElementById('lens-modal');
  if (!modal) return;
  modal.innerHTML = renderLensModalBody(tile);
  modal.hidden = false;
  lensLastTileKey = tileKey;

  // Focus the close button for keyboard users
  const closeBtn = modal.querySelector('.lens-modal-close');
  if (closeBtn) closeBtn.focus();

  // Update map pins for geo tiles; leave map untouched for aggregate tiles
  _updateLensMapPins(tile);

  // Set up Leaflet marker → row sync (pin click highlights the row)
  lensMapFeaturePins.forEach(marker => {
    marker.off('click');
    marker.on('click', () => _highlightLensRow(marker._lensFeatureIdx));
  });
}
```

- [ ] **Step 2: Add `closeLensModal`**

```javascript
function closeLensModal() {
  const modal = document.getElementById('lens-modal');
  if (!modal || modal.hidden) return;
  modal.hidden = true;
  modal.innerHTML = '';
  // Sweep any open ⓘ popovers (they may have been portaled to document.body)
  if (typeof dropOrphanTooltips === 'function') dropOrphanTooltips();
  // Clear feature pins from map; restore address-centered view
  if (lensMap) {
    lensMapFeaturePins.forEach(m => { try { lensMap.removeLayer(m); } catch (e) {} });
    lensMapFeaturePins = [];
    if (lensAddressMarker) {
      lensMap.setView(lensAddressMarker.getLatLng(), 14);
    }
  }
  const hint = document.getElementById('lens-map-hint');
  if (hint) hint.textContent = 'Click a tile to plot its locations';
  // Return focus to the last-clicked tile
  if (lensLastTileKey) {
    const tile = document.querySelector(`.lens-tile[data-tile-key="${lensLastTileKey}"]`);
    if (tile) tile.focus();
  }
}
```

- [ ] **Step 3: Add `_highlightLensRow`**

```javascript
function _highlightLensRow(idx) {
  const row = document.querySelector(`.lens-feature[data-feature-idx="${idx}"]`);
  if (!row) return;
  row.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  row.classList.add('highlighted');
  setTimeout(() => row.classList.remove('highlighted'), 900);
}
```

- [ ] **Step 4: Add the delegated event handlers**

Find a good place near existing document-level handlers (grep for `document.addEventListener('click'`). Add a new delegated listener that handles tile click, modal close, and feature-row click. Also add Escape key handler and address-change cleanup.

```javascript
// -- Spec D: delegated event handlers ---------------------------------------

// Tile click → open modal.
// Modal close button → close.
// Feature row click (outside .info-tip) → pan/zoom map to that pin.
document.addEventListener('click', (e) => {
  // Close button
  if (e.target.closest('.lens-modal-close')) {
    closeLensModal();
    return;
  }
  // Feature row → map pan (skip clicks inside the ⓘ details widget)
  const featureRow = e.target.closest('.lens-feature');
  if (featureRow && !e.target.closest('.info-tip')) {
    const idx = parseInt(featureRow.dataset.featureIdx, 10);
    if (!Number.isNaN(idx) && lensMap && lensMapFeaturePins[idx]) {
      const marker = lensMapFeaturePins[idx];
      lensMap.setView(marker.getLatLng(), Math.max(lensMap.getZoom(), 16), { animate: true });
      marker.openPopup();
    }
    return;
  }
  // Tile click → open modal
  const tile = e.target.closest('.lens-tile');
  if (tile) {
    const key = tile.dataset.tileKey;
    if (key) openLensModal(key);
    return;
  }
});

// Escape → close modal (unless a native <details> is open — it consumes Escape first)
document.addEventListener('keydown', (e) => {
  if (e.key !== 'Escape') return;
  const modal = document.getElementById('lens-modal');
  if (modal && !modal.hidden) closeLensModal();
});
```

- [ ] **Step 5: Wire `dropOrphanTooltips` into lens transitions**

Find `setActiveLens` (Spec B). Add a `dropOrphanTooltips()` call right before `renderAllPanels()`:

```javascript
function setActiveLens(slug) {
  if (slug !== 'young_family' && slug !== 'bureaucracy') return;
  try { localStorage.setItem(LM_ACTIVE_KEY, slug); } catch (e) {}
  document.querySelectorAll('.lens-picker [data-lens]').forEach(btn => {
    const on = btn.dataset.lens === slug;
    btn.classList.toggle('active', on);
    btn.setAttribute('aria-selected', on ? 'true' : 'false');
  });
  // Spec D: any open modal/popover belongs to the OLD lens — sweep first
  const modal = document.getElementById('lens-modal');
  if (modal && !modal.hidden) closeLensModal();
  if (typeof dropOrphanTooltips === 'function') dropOrphanTooltips();
  if (typeof renderAllPanels === 'function') renderAllPanels();
  if (location.hash === '#compare' && typeof renderCompare === 'function') renderCompare();
}
```

Find `setLifeMode`. Similarly, in the OFF branch (or unconditionally at the top), close any open modal and drop orphan tooltips:

```javascript
function setLifeMode(on) {
  const btn = document.getElementById('life-mode-toggle');
  document.body.classList.toggle('life-mode', on);
  btn.classList.toggle('on', on);
  btn.setAttribute('aria-pressed', on ? 'true' : 'false');
  btn.setAttribute('aria-label', on
    ? 'Life Mode on (toggle to switch off)'
    : 'Life Mode off (toggle to switch on)');
  try { localStorage.setItem(LM_STATE_KEY, on ? 'on' : 'off'); } catch (e) {}
  // Spec D: sweep any lingering modal/tooltip state on mode switch
  const modal = document.getElementById('lens-modal');
  if (modal && !modal.hidden) closeLensModal();
  if (typeof dropOrphanTooltips === 'function') dropOrphanTooltips();
  renderAllPanels();
  if (location.hash === '#compare') renderCompare();
}
```

Address-change flow: `renderAllPanels()` handles it — when a new address is submitted, `eduData` updates and `renderAllPanels` re-renders the lens view (innerHTML replaced), which discards the old modal DOM. Add a `dropOrphanTooltips()` call inside `renderAllPanels` before the innerHTML assignment for safety:

```javascript
function renderAllPanels() {
  const onLife = document.body.classList.contains('life-mode');
  let lensEl = document.getElementById('lens-view');
  if (!lensEl) {
    // ... existing lazy-create code ...
  }
  // Spec D: sweep any tooltip popovers still portaled from an earlier render
  if (typeof dropOrphanTooltips === 'function') dropOrphanTooltips();
  if (onLife) {
    lensEl.innerHTML = eduData ? renderLensSingle(eduData) : '';
    if (eduData && eduData.address) initLensMap(eduData.address);
  } else {
    // ... existing OFF branch ...
  }
  // ... rest of function unchanged (isAnyLensAvailable check etc.) ...
}
```

- [ ] **Step 6: Browser QA — full click flow**

Hard-refresh app. Enter Kastanienallee 12, Life Mode ON.

Manual walk-through:
1. Click the Kita tile → modal appears over tiles column; features list has 3-10 kita entries; map shows numbered green pins + address pin; hint text updates.
2. Click ⓘ on the first kita → popover opens with `Places`, `Operator`, `Approach` rows. Click ⓘ again → closes.
3. Click the 3rd feature row's name (not the ⓘ) → map pans + zooms to that pin; popup opens.
4. Click a numbered pin on the map → matching row highlights briefly (background pulse) and scrolls into view.
5. Click ✕ → modal closes; feature pins disappear; map re-centers on address.
6. Click Noise tile → modal opens with explanation text; no map changes.
7. Press Escape while modal is open → modal closes.
8. Switch lens via picker (Bureaucracy) → modal closes (if open); tiles re-render for bureaucracy.
9. Toggle Life Mode OFF while modal is open → modal disappears; lens-view innerHTML clears; map destroyed. Inspect DevTools → no `.info-body` elements linger in `document.body`.

- [ ] **Step 7: Commit**

```bash
git add web/static/app.js
git commit -m "Wire lens tile click → modal + map pins + row↔pin sync"
```

---

## Task 10: Frontend live-browser QA (§14.12)

**Files:**
- No edits — pure manual QA against the running app.

**Interfaces:** none — consumes the whole Spec D delivery.

**Notes:** 12-item §14.12 checklist per Spec D testing section. Do all 12 in order on a fresh browser profile. Any failure → return to the responsible task, fix, re-QA.

- [ ] **Step 1: Initial state — 2-col layout.** Fresh Incognito → `http://127.0.0.1:8000/`. Enter Kastanienallee 12, 10435. Toggle Life Mode ON. Verify tiles column (~55%) + map column (~45%). Address pink pin visible on map. Hint reads "Click a tile to plot its locations". No feature pins. PASS.

- [ ] **Step 2: Geo tile click — kita.** Click Kita tile. Modal covers tiles column with backdrop blur. Head shows kita icon + "Kita reachability" + GREEN badge. Features list has ≥3 numbered rows. Map shows numbered green pins + address pin; map bounds fit both. Hint updates to "Kita reachability: N on map". PASS.

- [ ] **Step 3: Row → map sync.** Click feature row #2's name area (not the ⓘ). Map pans + zooms (min zoom 16) to that pin; Leaflet popup opens. PASS.

- [ ] **Step 4: Pin → row sync.** Click a numbered pin on the map. Leaflet popup opens with feature name. The corresponding row briefly highlights (background pulses) and scrolls into view if off-screen. PASS.

- [ ] **Step 5: ⓘ popover.** Click ⓘ on the first kita row. Popover appears above the row showing Places / Operator / Approach rows (whichever populated). Click ⓘ again → popover closes. Verify popover doesn't get clipped by the modal (portal moves it to `document.body`). PASS.

- [ ] **Step 6: Modal close via ✕.** Click ✕. Modal disappears. Feature pins clear. Map re-centers on address. Hint resets to "Click a tile to plot its locations". Focus returns to the tile that opened the modal. PASS.

- [ ] **Step 7: Modal close via Escape.** Open a tile. Press Esc. Modal closes; pins clear. (If an ⓘ popover is open, Esc closes that first — native `<details>` behavior. Press Esc again → modal closes.) PASS.

- [ ] **Step 8: Aggregate tile — noise.** Click Noise tile. Modal shows tier + rule + numeric + explanation paragraph + sources footer. Map unchanged — no new pins. Hint text unchanged. Click ⓘ — no ⓘ appears (aggregate tiles have no features → no ⓘ). PASS.

- [ ] **Step 9: Pediatrician detail — Bergmannstraße 27.** Change address to Bergmannstraße 27, 10961. Click Pediatrician tile. Modal opens. Row for Dr. Berns visible. Click ⓘ. Popover shows Address / Walk time / Phone (tel-link) / Website (Visit ↗) / Hours / Access (Step-free). PASS.

- [ ] **Step 10: Refuge tile.** Return to Kastanienallee 12. Click Refuge tile. Modal shows quiet-zone row (if contributed) + trees stats block (count + crown % + avg age + top species). Map pin at quiet zone if applicable. PASS.

- [ ] **Step 11: Bureaucracy — Standesamt.** Switch to Bureaucracy lens via picker. Click Standesamt tile. Modal shows "Standesamt Pankow" with address, walk_min via ⓘ popover. Single map pin. PASS.

- [ ] **Step 12: Lifecycle sanity.** Open a tile modal → open ⓘ popover → toggle Life Mode OFF. Lens-view innerHTML clears; modal + popover + pins disappear. Open DevTools → search DOM for `.info-body` — no orphaned popovers should remain in `document.body`. Toggle Life Mode ON again → fresh lens renders with no lingering state. PASS.

- [ ] **Step 13: Clean up ephemeral screenshots per §14.12.**

- [ ] **Step 14: Mark ship-ready with an empty commit**

```bash
git commit --allow-empty -m "Clickable Lens Tiles: live-browser QA passed (Spec D shipped)"
```

---

## Self-Review

**1. Spec coverage:**

- Spec D "In scope" list — every item mapped:
  - `<button class="lens-tile">` with keyboard + mouse (Task 6).
  - 2-col Life Mode layout, mobile-collapsed (Tasks 5+6).
  - `.lens-modal` absolute overlay with backdrop blur + ✕ close + Escape (Tasks 5+7+9).
  - `<details class="info-tip">` info popover reuse — no new disclosure (Task 7).
  - Numbered map pins colored by tier + two-way sync (Tasks 8+9).
  - New shape helpers `_prune`/`_int_or_none`/`_valid_latlon`/`_shape_kita`/`_shape_playground`/`_shape_paediatric_gp`/`_shape_office`/`_shape_refuge_quiet`/`_shape_refuge_trees` (Task 1).
  - Both composers extended (Tasks 2+3).
  - Pure + live selfcheck (Tasks 1-4).
  - "See also" pointers in Spec A + Spec B docs — already landed in the spec commit (`2f48c3b`); the plan doesn't touch them again.

- Locked-decision threshold values are all in Tasks 1-3 code or Task 5 CSS.
- Non-goals honored — no compare-view clickability, no LLM narration, no feature caps, no URL/hours normalization, no deep-link URLs.

**2. Placeholder scan:** clean. Every code block is complete and runnable. The `Optional` import check in Task 1 Step 8 is a conditional based on grep result — the fix is one line, spelled out. Task 8 Step 1 also has an "if hoist feels natural" note — that's a legit judgment call, not a placeholder (both branches spelled out in Step 4).

**3. Type consistency across tasks:**

- Shape-helper signatures match their consumers exactly:
  - `_shape_kita(o, fm) -> Optional[dict]` used at composer site as `[f for f in (_shape_kita(o, cfg.kita_field_map) for o in kitas) if f]` (Task 2).
  - `_shape_office(o) -> Optional[dict]` used for both nearest-of-many (list comprehension) and nearest-single (`single = _shape_office(x) if x else None; features = [single] if single else []`) — Task 3.
  - `_shape_refuge_quiet(q, amber_quiet_m) -> list` — Task 2 passes `thresholds["refuge"]["amber_quiet_m"]`.
  - `_shape_refuge_trees(t) -> dict` — Task 2 stores as `tile["metadata"] = {"trees": _shape_refuge_trees(trees)}`.
- JS names:
  - `renderLensSingle` produces `<button class="lens-tile" data-tile-key="...">` (Task 6). Handler in Task 9 reads `e.target.closest('.lens-tile').dataset.tileKey`. Match.
  - `.lens-modal` id `lens-modal` (Task 6 markup); `openLensModal`/`closeLensModal` (Task 9) query `document.getElementById('lens-modal')`. Match.
  - `.lens-feature` with `data-feature-idx="${idx}"` (Task 7). Handler (Task 9) reads `parseInt(featureRow.dataset.featureIdx, 10)`. Match.
  - `_lensFeatureDetailHtml` reads `f.address`, `f.phone`, `f.website`, `f.hours`, `f.wheelchair`, `f.walk_min`, `f.capacity`, `f.operator_type`, `f.approach`, `f.area_m2`, `f.renovated_year`, `f.size_ha`, `f.kind` (Task 7) — all match the `_shape_*` output field names (Task 1).
  - `lensMapFeaturePins[i]` used by Task 9 (`lensMap.setView(marker.getLatLng(), ...)`) matches Task 8's `lensMapFeaturePins.push(marker)` + `marker._lensFeatureIdx = i` custom prop.
  - `TIER_PIN_COLORS[tile.tier]` used by Task 8; defined by Task 7 (module const).
  - `LENS_TILE_EXPLANATIONS[tile.key]` used by Task 7; defined in the same task.
- CSS ↔ JS class names:
  - `.lens-body`/`.lens-tiles-col`/`.lens-map-col` — Task 5 defines; Task 6 emits.
  - `.lens-modal`/`.lens-modal-close`/`.modal-head`/`.modal-rule`/`.modal-numeric`/`.modal-caveat`/`.modal-explanation`/`.modal-features-list`/`.modal-trees`/`.modal-provenance`/`.modal-empty` — Task 5 defines; Task 7 emits.
  - `.lens-feature`/`.feature-marker`/`.feature-name`/`.feature-distance` — Task 5 defines; Task 7 emits.
  - `.lens-feature.highlighted` — Task 5 defines; Task 9's `_highlightLensRow` toggles it.
  - `.info-tip`/`.info-body.details-block`/`.det-row`/`.det-label`/`.det-val` — pre-existing (`app.css:409-421`); Task 7 emits.
  - `.lens-pin` — Task 5 defines; Task 8's `lensNumberedPin` emits via `L.divIcon` HTML.
  - `#lens-map` — Task 5 defines; Task 6 emits (markup) + Task 8 initializes (Leaflet).
  - `#lens-map-hint` — Task 5 styles; Task 6 emits; Tasks 8+9 update text.

No inconsistencies found. Plan is ready to execute.
