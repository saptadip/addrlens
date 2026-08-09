# Bureaucracy lens — deferred follow-ups

**Source:** captured from the SDD progress ledger before its workspace was deleted after the final whole-branch review of Spec B (commit range `2721709..5e3162c`, final review verdict: MERGE after one fix wave).

Every item below was triaged as **Minor** by the final code-reviewer or during task-level reviews. None blocked shipping. Pick them up opportunistically or bundle them into a small polish PR.

---

## 1. `_geojson` boot loader crashes the app on service.berlin.de outage

**Where:** `app/core/index.py` — the `_geojson` sentinel branch of the Bürgerämter preload in `Index.__init__`.

**Symptom:** The Bürgerämter data source lives at `service.berlin.de/standorte/geojson/buergeramt` (adaptation from Spec B Task 3 — the Berlin Geoportal doesn't publish this as WFS). If `service.berlin.de` returns 5xx at boot, `urllib.request.urlopen()` raises, `Index()` throws, and `main.py`'s lifespan crashes — the whole app fails to start, taking down Young Family lens too.

**Context:** This matches the pre-existing pattern for every other WFS preload in `Index.__init__` (fire / quiet / protection / pools / tram / etc.) — none of them try/except either. So this is not a Spec-B regression. If the project ever wants graceful degradation on lens preloads, it's a project-wide policy change, not a Spec-B follow-up. Filed here for visibility.

**Fix (if adopted project-wide):** wrap each preload block in `try/except`, log the failure, and leave `self.<attr> = []` so the corresponding tile can produce `tier: "unknown"` at request time instead of preventing boot.

## 2. Compare-view column labels use dead `shortLabel` fallback

**Where:** `web/static/app.js` around line 2060 in `renderLensCompare()`.

**Symptom:** The column-header expression is `a.shortLabel || (a.address && a.address.street) || '—'`. `buildSnapshot()` never populates `shortLabel` — the first branch is dead code, kept only as a hopeful fallback that never fires.

**Fix:** either populate `shortLabel` in `buildSnapshot()` with a useful compact label (e.g. `${street} ${hnr}`), OR drop the dead branch and always compute the label inline. If keeping the dead branch, leave a comment naming what it would take to make it fire.

## 3. Finanzamt / Arbeitsagentur curated coord duplicates

**Where:** `app/cities/berlin.py` `_FINANZAMTS` and `_ARBEITSAGENTURS` tuples.

**Symptom:** Two Finanzamt entries share coordinates (`Pankow/Weißensee` and `Prenzlauer Berg` both at `(13.4560, 52.5290)` on Storkower Str. 134). Two Arbeitsagentur pairs share coords likewise (`Nord`/`Charlottenburg` and `Süd`/`Neukölln`). Plausible shared-building situations, but worth confirming.

**Fix:** annual refresh — verify each address at berlin.de/finanzaemter and arbeitsagentur.de/behoerdenauskunft. If the shared-building assumption holds, add a comment naming which pairs share a building. Otherwise correct the coord.

## 4. `Finanzamt Wilmersdorf` address is truncated

**Where:** `app/cities/berlin.py` `_FINANZAMTS` entry for Wilmersdorf: `"Volkslehrer- und Blissestr., 10713 Berlin"`.

**Symptom:** Missing house number; reads like an OCR/paste artefact. Doesn't affect the tile tier (coord-based) but is user-facing when the tile lists the office name.

**Fix:** replace with the correct address (Blissestr. 5, 10713 Berlin, per berlin.de). Coord `(13.3120, 52.4870)` looks reasonable — verify.

## 5. `renderLensSingle` normal branch lacks `|| []` guard on `.tiles`

**Where:** `web/static/app.js` in `renderLensSingle(addr)`, the success branch.

**Symptom:** `lens.tiles.map(renderLensTile).join('')` — if the API ever returns a lens object with no `error` key but also no `tiles` array, this throws at runtime. Backend always returns `tiles` on non-error today, so it's a latent risk, not a live breakage.

**Fix:** `(lens.tiles || []).map(renderLensTile).join('')`. One character.

## 6. `renderAllPanels` toggle-disabled logic uses `eduData` as focused-address proxy

**Where:** `web/static/app.js` in `renderAllPanels()`, the block that toggles `#life-mode-toggle`'s `disabled` attribute.

**Symptom:** The "both lenses error → disable toggle" check reads `focused = eduData || null`. `eduData` is populated only for the single-address view. In compare view, `eduData` is null, so `isAnyLensAvailable(focused)` collapses to `isAnyLensAvailable(null)` → `false`, but the else-branch removes `disabled` unconditionally. Result: in compare view with all addresses failing both lenses, the toggle still appears enabled.

**Fix:** either check against the first address in the compare set when `eduData` is null, or extract a "currently-focused address" helper and use it here. Compare view with both lenses down for all addresses is a rare-but-possible state.

## 7. `finanzamt_nearest` double-computes haversine for the winner

**Where:** `app/core/index.py` `Index.finanzamt_nearest(lon, lat)`.

**Symptom:** `min(offices, key=lambda o: haversine_m(...))` computes distance for every candidate; then a second standalone `haversine_m(...)` for the winner. Microopt with negligible impact — the curated list is 17 items.

**Fix:** compute once by decorating, e.g. `d, best = min((haversine_m(lon,lat,o["lon"],o["lat"]), o) for o in ...)`.

## 8. Bürgeramt WFS-fallback branch missing coord-unpack length guard

**Where:** `app/core/index.py` — the WFS branch of the Bürgerämter preload (dead code for Berlin today; the `_geojson` sentinel is used instead).

**Symptom:** `lo, la = g["coordinates"]` without a length guard. Not exercised for Berlin; latent crash if a future city returns malformed WFS geometry.

**Fix:** add `if not g or len(g.get("coordinates", [])) < 2: continue` before the unpack.

## 9. Stale comment above the empty-inputs asserts in scorer

**Where:** `app/core/scorer.py` inside the `__main__` block, above the bureaucracy composer empty-inputs asserts.

**Symptom:** Comment reads "Empty inputs → red, not unknown" but the asserts below check for `"unknown"`. The block's own inline comment already corrects this, but the header line is misleading.

**Fix:** delete or rephrase the header comment. Purely cosmetic.

## 10. `_WFS_BEZIRKE` / `_WFS_BUERGERAEMTER` grouping seam in berlin.py

**Where:** `app/cities/berlin.py` `_WFS_*` constant block.

**Symptom:** The Spec B WFS URLs land at the seam between the "Phase 2 (Umweltatlas)" and "Base URLs" sub-groups. Readable but the three-group block could use a blank-line separator.

**Fix:** insert a blank line between the existing Phase-2 block and the Spec B block for visual grouping.
