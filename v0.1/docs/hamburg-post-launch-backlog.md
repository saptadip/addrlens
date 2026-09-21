# Hamburg post-launch backlog

Items surfaced by the PR #81 review chain that were deferred as non-launch-blocking. Land these before the Hamburg marketing push OR as capacity allows.

## Data + integration

### Replace `hamburg.svg` placeholder outline
- **What:** the hero-scanner SVG at `v0.1/web/static/img/city-outlines/hamburg.svg` is a ~40-vertex hand-approximated silhouette. Berlin's is a 128-vertex accurate union of Bezirke polygons.
- **Why:** visible on every Hamburg landing page. Placeholder is fine for staging + soft launch; replace before any marketing push where the visual quality matters.
- **How:** simplify OSM boundary relation 62782 (Hamburg admin boundary) to ~128 vertices via `ogr2ogr` or Turf.js; save as raw `<path>` snippet matching Berlin's format. Inline comment at the top of the file documents this TODO.

### Wire Hamburg schools 2nd layer (private + international)
- **What:** `hamburg.py:schools_layer="de.hh.up:staatliche_schulen"` only loads state schools. `gs_intl` filter (Newcomer lens) filters for "international/english/bilingual" keywords — most Hamburg internationals are private (International School Hamburg, Ida Ehre) so this list is currently empty.
- **Why:** English-speaking newcomers looking for intl schools see no results; SEO / feature-completeness gap vs Berlin.
- **How:** extend `CityConfig` with a `schools_layers: tuple` field (like `hospital_layers`), or add a `schools_private_layer` field. Rewrite `Index._load_catchments_and_schools` to load and merge both layers. Discovery via `curl "https://geodienste.hamburg.de/HH_WFS_Schulen?service=WFS&request=GetCapabilities" | grep -A2 "Name>de.hh.up"`.

### Route `oaf_geocoder.py` through shared httpx retry client
- **What:** `v0.1/app/core/loaders/oaf_geocoder.py:40` uses `httpx.get(...)` (sync, 10s timeout, one-shot, no retry). Berlin's `wfs()` runs through a pooled `Client` with retry envelope.
- **Why:** Hamburg's every `/api/lookup` opens a fresh TCP conn to `api.hamburg.de` — no keep-alive, no 502/503/504 retry. When Hamburg's OAF endpoint hiccups, Hamburg users see one-shot failures where Berlin users would silently retry.
- **How:** factor `_get_client()` from `app/core/wfs.py` into a shared helper (or expose it), then call from `oaf_geocoder.py` with the same connect/read/write timeouts + retry-on-5xx behaviour.

## Frontend

### Playwright smoke for `constants.js` top-level `await` on Safari 15
- **What:** `constants.js` uses top-level dynamic import + `await` to load per-city constants. Supported in Chrome 89+ / FF 89+ / Safari 15+ per MDN, but no automated test confirms it actually works on Safari 15 (documented lower-bound of supported browsers).
- **Why:** if Safari 15 evaluates the dispatcher before `<body data-city>` is parsed, Hamburg's dispatcher falls back to Berlin defaults — Hamburg users see Berlin glossaries. Silent failure.
- **How:** Playwright test loading `hamburg.addrlens.de` on Safari 15 (via BrowserStack or Playwright's `webkit` runner pinned to matching version), asserting `document.body.dataset.city === 'hamburg'` AND `constants.js` exports contain Hamburg-specific values (e.g., HVV in GLOSSARY).

### Server-side filter `other_cities` in `/api/config`
- **What:** `v0.1/app/routes/config.py` returns `other_cities` list including the current city. `web/static/modules/city-switch.js` filters client-side.
- **Why:** minor API cleanliness; any 3rd-party consumer of `/api/config` gets a self-entry unless they filter.
- **How:** filter in the config handler: `[c for c in cfg.other_cities if c["slug"] != cfg.slug]`.

## Data quality (ledgered from T27)

### 10 vbb_hamburg_su.csv rows carry stop_id integers as name
- **What:** the HVV GTFS feed has 10 fringe U-Bahn extension stops with no `stop_name` — `refresh_hvv.py` writes the raw stop_id integer as the display name (e.g., `369006`, `729007`).
- **Why:** users querying near those stops see a numeric string as the station name.
- **How:** cross-reference against HVV's `translations.txt` or a secondary lookup; if still empty, format as `"HVV Stop #<id>"` for readability. Post-ship dedup + name-quality pass.

### ~6 duplicate ferry pier rows
- **What:** `hvv_hamburg_ferry.csv` contains 3 rows for `Landungsbrücken Brücke 1` (different pier positions) + duplicates for Finkenwerder, Neumühlen/Övelgönne, Altona (Fischmarkt).
- **Why:** harmless — `nearest_ferry` uses `min()` which picks the closest — but the list is larger than necessary and could confuse a lens summary that iterates all piers.
- **How:** dedup by `(round(lat, 4), round(lon, 4))` in `refresh_hvv.py` or drop pier-position rows keeping only station-name canonical entries.

## Composer + scorer polish (from post-fix review round 2)

### Wire `_tier_noise_band` — currently dead
- **What:** `_tier_noise_band` in `v0.1/app/core/scoring/tiers.py` and `Index.noise_bands_at` in `v0.1/app/core/index.py` are defined + unit-tested but never called from any composer or route.
- **Why:** Hamburg's noise picture uses BUKEA's isoline model (`noise_model="isoline"` in hamburg.py) not point-based. Currently the noise data path is completely unwired for Hamburg.
- **How:** either (a) add a `noise_band` tile to Hamburg's Newcomer/Commuter/Quiet Living lenses and wire the tier fn in the composers, OR (b) refactor `noise_at()` in `app/core/wfs.py` to dispatch on `cfg.noise_model` and call the isoline path for Hamburg's `air`/`heat`-style noise reads. NOTE: `Index.noise_bands_at` currently does live WFS on the hot path — needs boot-preload (like `_load_quiet_zones`) before wiring.

### Compose `_INDEX_HTML` inside `lifespan()` instead of module import
- **What:** `main.py:_INDEX_HTML = _load_index_html()` runs at module import — before `lifespan()` sets `app.state.city`. `_load_index_html` reads `CITY` env var directly.
- **Why:** double read of city selection (module + lifespan); test-only concern in practice, but a footgun if a future test changes `CITY` mid-process.
- **How:** move `_INDEX_HTML` compute into `lifespan()`, stash on `app.state.index_html`, adjust the `/` handler.

### Refactor SSR text-swap ordering in `_load_index_html`
- **What:** `main.py:170-190` does a sequence of `html.replace(...)` calls where earlier swaps consume substrings that later swaps expect to find.
- **Why:** currently correct but fragile — reordering the swap lines silently breaks a swap.
- **How:** consolidate into a single `re.sub` with an ordered longest-first pattern list, OR a list of `(old, new)` tuples processed longest-first.

## Ops observability

### Widen or set Sentry env for Berlin
- **What:** `T24` changed Sentry env default from literal `"production"` to `f"{city}-production"`. Berlin dashboards filtering on exact `environment=production` no longer match — Berlin events now tag `berlin-production`.
- **Why:** dashboards / alert rules using the old exact filter stop firing.
- **How:** either (a) set `SENTRY_ENV=production` in `.env.production` to preserve the literal, OR (b) update dashboard filter to `environment~*-production` regex match. Ideally (b) so Berlin/Hamburg events are individually filterable AND collectively aggregatable.

### Berlin live selfcheck Overpass rate-limit
- **What:** `_live_selfcheck_berlin` asserts `pediatrician.tier == "green"` — reads OSM Overpass API. Overpass is rate-limit-happy and often 429s or 406s.
- **Why:** selfcheck failure is an unreliable signal (pre-existing flake, not a code regression).
- **How:** either (a) mark the pediatrician assert as `pytest.mark.flaky(reruns=2, reruns_delay=30)`, OR (b) fold Overpass reads into a cached fixture that lives for the selfcheck run.

## Rollout hygiene

### Full rollback dry-run in a scratch worktree
- **What:** verify `git revert` of the Hamburg merge commit produces a Berlin-only tree that builds + tests green.
- **Why:** the rollback path in `hamburg-rollout-checklist.md § Rollback path` is `docker compose stop` + Cloudflare hostname removal. A full code rollback is untested.
- **How:** `git worktree add /tmp/rollback-dryrun main && cd /tmp/rollback-dryrun && git revert <hamburg-merge-sha> && pytest -q && python -m app.cities.berlin`. Confirm 249 baseline + Berlin selfcheck clean. Delete worktree.

---

**Priority order for post-launch capacity:**
1. Widen Sentry env filter (immediate — dashboards blind otherwise)
2. Replace hamburg.svg placeholder (before marketing push)
3. Wire schools 2nd layer for private/intl (SEO/completeness)
4. Route oaf_geocoder through shared retry (Hamburg availability parity with Berlin)
5. Wire `_tier_noise_band` (feature completeness)
6. Playwright Safari 15 smoke (defensive)
7. Rest (data-quality + composer polish + rollback dry-run) as capacity allows
