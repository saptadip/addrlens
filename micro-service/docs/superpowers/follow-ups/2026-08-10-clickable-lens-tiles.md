# Clickable Lens Tiles (Spec D) — deferred follow-ups

**Source:** captured from the SDD progress ledger + final whole-branch review of Spec D (commit range `5e807c1..446a048`, final review verdict: SHIP_WITH_FIXES — the one Important finding was fixed in `446a048`; items below are the Minor findings, all safe to defer).

Every item below was triaged as **Minor** by the final code-reviewer or during task-level reviews. None block shipping. Bundle into a small polish PR when convenient.

---

## 1. Life-Mode-OFF teardown order in `renderAllPanels`

**Where:** `web/static/app.js` — the OFF branch that clears `lensEl.innerHTML` and then removes `lensMap`

**Symptom:** `lensEl.innerHTML = ''` runs before `lensMap.remove()`. Leaflet is defensive against being removed from a detached container so there is no user-visible bug, but the correct order is `lensMap.remove(); lensMap = null; lensEl.innerHTML = ''`.

**Fix:** swap the two statements in the Life Mode OFF branch of `renderAllPanels`. One-line change.

## 2. `_updateLensMapPins` re-filters the features array

**Where:** `web/static/app.js` in `_updateLensMapPins`

**Symptom:** The `latlngs` array is rebuilt by re-filtering `features` for valid `lat`/`lon`, duplicating the guard applied when pushing markers. The backend `_shape_*` helpers already enforce `_valid_latlon`, so the guard is redundant twice over.

**Fix:** build `latlngs` from `lensMapFeaturePins.map(m => m.getLatLng())` instead of re-walking `features`. Simplifies the function.

## 3. `iconPin` emoji fallback in `initLensMap`

**Where:** `web/static/app.js` in `initLensMap`

**Symptom:** The address-marker call uses `iconPin(ico.home || ico.pin || '📍', '#EC4899')`. `ico.home` is always defined at module load so the `📍` fallback is unreachable. If it ever did fire, an emoji inside the SVG `iconPin` template would render as raw text — cosmetic surprise, not a crash.

**Fix:** drop the emoji, use `''` or a static SVG dot as last-resort fallback. Cosmetic.

## 4. Delegated tile-click listener re-registration on hot reload

**Where:** `web/static/app.js` where the delegated `.lens-tile` click listener is bound to `document` at module-load time

**Symptom:** On hot reload or double-inclusion of the script, listeners stack. This project has no build step and only one `<script>` tag, so it's not currently a real risk — flagged only for future refactors.

**Fix:** gate the bind on a module-level `if (!__lensListenersInstalled)` flag, or move to an idempotent `once`-style registration.

## 5. Empty-lens path still calls `initLensMap`

**Where:** `web/static/app.js` — `renderAllPanels` Life-Mode-ON branch calls `initLensMap(eduData.address)` guarded only on address presence

**Symptom:** When `lens.error`, `renderLensSingle` returns markup with no `#lens-map` div. `initLensMap` bails on missing element so no bug — just a saved cycle.

**Fix:** also check `document.getElementById('lens-map')` before calling `initLensMap`, or restructure so the empty-lens branch skips the map init explicitly.

## 6. Pedestrian-speed constant drift between raw-mode and Life Mode

**Where:** `app/core/scorer.py` `_walk_minutes` (62 m/min) vs `web/static/app.js` `walkMin` (80 m/min)

**Symptom:** Raw-mode Amenities and Life Mode modal show *different* walking times for the same POI (~30% divergence). Life Mode is internally consistent (both tile face and modal use the same 62 m/min value from the backend), but users switching between raw-mode and Life Mode will notice the drift. Not a Spec D regression — the constant mismatch predates this branch.

**Fix:** unify on one constant. Backend value is the more defensible (4.8 km/h × 1.3 route factor). Change `walkMin` in `app.js` to `Math.round(m/62)` or expose the backend value via config.
