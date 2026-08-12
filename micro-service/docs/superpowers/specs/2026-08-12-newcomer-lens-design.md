# Newcomer / Relocation Lens — Design (Spec E)

**Date:** 2026-08-12
**Status:** Draft — pending review
**Predecessor specs:**
- [Spec A — Young Family Lens](2026-08-09-young-family-lens-design.md) — establishes the `LIFE_MODE_LENSES` registry, `LensConfig` / `LensTileConfig` dataclasses, tier scoring shape, and the toggle-switch UX.
- [Spec D — Clickable Lens Tiles](2026-08-10-clickable-lens-tiles-design.md) — mandates the `features` array + modal / map integration for every tile.
- Spec B (Bureaucracy) is superseded — Bureaucracy has been rolled off Life Mode.

**Implementation surface:** `v0.1/` (Geofabrik-backed variant). This lens leans heavily on the OSM local snapshot that the `v0.1` build already refreshes weekly; the `micro-service/` (live-Overpass) build is not in scope.

## Context

The Young Family lens answers "is this address good for someone with kids under 6?". It works because the target user has a shared, well-defined set of needs.

Expat newcomers to Berlin have an equally sharp — and different — set of needs. The first 90 days revolve around a fixed script: register at the Bürgeramt, open a bank account, get a SIM, find a doctor, survive without German-language services, connect socially. Miss any one of those and the whole relocation stalls.

Today the app cannot answer *"is this address good for me if I'm new to Berlin and don't speak German yet?"*. Spec E introduces the **Newcomer lens** — an opinionated view over already-loaded open data that answers exactly that question.

This is the second lens in the `LIFE_MODE_LENSES` registry. The registry pattern is already in place (Young Family), so most of the abstraction cost is paid. Spec E adds one lens config, one composer, five tier functions, and five insight templates.

## Scope

**In scope:**
- One new lens: **Newcomer (0–90 days in Berlin)**.
- Six tiles: five traffic-light tiles (Bürgeramt reach, transit reach, international food, coworking + Wi-Fi cafés, English-speaking clinic) plus one profile tile (Neighbourhood profile — GESIx quintile band, no tier badge).
- Server-computed tier logic in `v0.1/app/core/scorer.py`.
- `NEWCOMER_LENS: LensConfig` in `v0.1/app/cities/berlin.py`.
- New Geofabrik snapshot filters where required (see §Data sources). The Neighbourhood-profile tile reuses `Index.gesix_at(lon, lat)` — no new data load.
- Extension of `LIFE_MODE_LENSES` frontend registry so the Life Mode picker lists both lenses.
- Compare-up-to-5 view: newcomer tiles rendered under the same lens picker.
- Six new inference templates: `buergeramt_insight`, `transit_newcomer_insight`, `intl_food_insight`, `coworking_insight`, `english_clinic_insight`, `gesix_newcomer_insight`. The GESIx template is a *distinct* file from the YF `gesix_insight` — same context shape, newcomer-tuned system prompt (see §LLM insight templates).
- Pure + live selfcheck coverage.

**Out of scope (deliberate):**
- Rent-fairness / Mietspiegel tile — deferred; requires PDF-table parser and per-Planungsraum join. Ship the five cheap tiles first.
- German-language onboarding services (Volkshochschule, integration courses) — v2.
- Embassy / consulate proximity tile — low signal for most nationalities.
- Multilingual dentist / mental-health filters — v2, OSM tag coverage too thin today.
- User-configurable "which country am I from" filter — v1 is nationality-agnostic.
- New lenses beyond this one (Student, Digital Nomad, Senior) — future.

## Locked decisions

- **Persona duration:** 0–90 days in Berlin (arrival window). The lens is optimised for the first-90-days script; long-term residents drift toward the raw-data mode.
- **Scoring shape:** 5 independent green / amber / red tiles. No aggregate. Same rationale as YF Spec A §Locked decisions.
- **Boundary convention:** inclusive on the greener side (matches YF).
- **Tile set (final):** Bürgeramt reach · Transit reach · International food · Coworking / Wi-Fi cafés · English-speaking clinic · Neighbourhood profile.
- **Neighbourhood profile treatment:** identical UI shape to the YF `gesix` tile — quintile bar in modal, no tier badge on the face, no numeric on the face. Card key is `gesix_newcomer` so the dispatcher routes to a newcomer-tuned insight template; the underlying context (`plr_name`, `quintile_5`, `rang`, `total`) is identical to YF.
- **Naming:** lens slug is `newcomer_lens`; display label is **Newcomer**. Emoji-free label per the Spec A neumorphic UI rules.
- **Compute location:** server-side, always included in `/api/lookup` under `lens.newcomer`. Zero-latency toggle. Same pattern as YF.
- **Insight templates:** one per card (`<card>_insight`), no per-lens fan-out. When a card key already exists in another lens (e.g. `transit`), the newcomer variant uses a distinct key (`transit_newcomer`) so its system prompt can address the newcomer audience directly. Naming convention: `<card>` for the lens-specific card key; template is `<card>_insight`.
- **Language of the modal narration:** English, second-person, first-person-plural ("we"). Assumes the reader is new and does not speak German.
- **Data-lift order:** ship transit + intl food + coworking + english_clinic first (all OSM-local, cheap); ship buergeramt second because it needs a new WFS layer.

## Architecture

*Where the code lives (v0.1/):*

- `app/cities/base.py` — no dataclass changes; `NEWCOMER_LENS` reuses the existing `LensConfig` / `LensTileConfig` shape from Spec A.
- `app/cities/berlin.py` — add `NEWCOMER_LENS: LensConfig` with the five `LensTileConfig` entries and their threshold values. Add one `CityConfig` field: `newcomer_lens: LensConfig` (frozen, no default — per Ship-B rule).
- `app/cities/base.py` — one new `Optional[str]` field: `buergeramt_wfs_url` (Berlin Geoportal). No default in Berlin means "not configured" — the buergeramt tile falls back to the OSM-local `office=government` filter.
- `app/core/scorer.py` — five new tier functions (`_tier_buergeramt`, `_tier_transit_newcomer`, `_tier_intl_food`, `_tier_coworking`, `_tier_english_clinic`) plus one composer `newcomer_lens(cfg, index, ...)`. Each returns the Spec D tile shape (`tier`, `rule`, `numeric`, `caveat`, `features`, optional `metadata`). The Neighbourhood-profile tile does not need a `_tier_*` function — the composer emits a shape-only tile (`tier: "unknown"`, no rule/numeric on face) whose `metadata.gesix` carries the same `{plr_name, quintile_5, rang, total}` payload the YF composer produces via `_shape_gesix(index, lat, lon)` (rename or extract from the existing YF composer to a shared helper).
- `app/core/osm_local.py` — add three new categories to `OsmLocalCache`: `buergeramt`, `intl_food`, `coworking`, `english_clinic`. English-clinic is a filtered projection of the existing `pediatrician`-style doctors bucket.
- `scripts/refresh_osm_amenities.py` — extend `_TAG_RULES` with the new categories (see §Data sources for the exact tag combos).
- `app/routes/lookup.py` — call `newcomer_lens(...)` at the end of the handler; fold under `lens.newcomer` in the response. Mirror the existing YF fold.
- `app/routes/card_insight.py` — extend `_CARD_CONTEXT_BUILDERS` with rows for each new card key. Reuse `_ctx_features` for the four feature-list-driven cards; add `_ctx_buergeramt` if the buergeramt tile carries WFS attributes distinct from OSM. For `gesix_newcomer`, reuse the existing `_ctx_gesix` builder (context shape is identical); the newcomer angle lives entirely in the template's system prompt.
- `inference/main.py` — register six new templates in `TEMPLATES`.
- `inference/templates/{buergeramt_insight,transit_newcomer_insight,intl_food_insight,coworking_insight,english_clinic_insight,gesix_newcomer_insight}.py` — one file per template, each with `SAMPLER`, `_SYSTEM`, `build_messages`, `run(backend, ctx)`, and a `__main__` selfcheck block. Follow the shape established by `refuge_insight.py`.
- `web/static/app.js` — extend `LIFE_MODE_LENSES` registry with a `newcomer` entry (`label`, `desc`, `tiles`, `insightKeys`). Extend `_INSIGHT_VINTAGE` with vintages for the five new cards. Life Mode picker renders from the registry, so no toggle-code changes.
- `web/static/app.css` — no new tokens. Neumorphic `.cell` + tier colors already cover the visual. If a new icon is needed (e.g. Bürgeramt), inline SVG into the shared `ico = {...}` object per convention.

**No new routes.** The one aggregating endpoint (`/api/lookup`) grows its response by one `lens.newcomer` block. `/api/card_insight` is already generic.

## Data sources & thresholds

Each row is the locked tier logic for one tile. Distances are walking-radius (haversine, `Index.osm_local` haversine queries). Numeric evidence follows the Spec A pattern: shortest-distance-or-count + rule label.

### 1. Bürgeramt reach — `buergeramt`

**Question:** How fast can you register?

| Tier | Condition |
|------|-----------|
| Green | ≥1 Bürgeramt within 1.5 km |
| Amber | Nearest Bürgeramt 1.5 – 3.0 km |
| Red | Nearest Bürgeramt > 3.0 km |

**Numeric line:** "*<distance>*m to *<office name>*".
**Rule label:** "Bürgeramt within a 15-minute walk" (green) / "reachable but you'll need transit" (amber) / "cross-district trip required" (red).
**Data:** Berlin Geoportal WFS layer `wfs_bezirksservice` (fields: `bezirk`, `name`, `strasse`, `hausnummer`, `plz`, `telefon`, `homepage`, geometry). Fallback: OSM local snapshot filtered by `office=government` + `government=register_office`.
**Provenance key:** `buergeramt`.

### 2. Transit reach (newcomer framing) — `transit_newcomer`

Different framing from the YF `transit` tile: newcomers care about intercity/airport access, not stroller-friendly tram runs.

| Tier | Condition |
|------|-----------|
| Green | S-Bahn within 800 m OR U-Bahn within 500 m |
| Amber | Any DB/S/U station within 1.2 km, but not the green band |
| Red | No rail stop within 1.2 km |

**Numeric line:** "*<distance>*m to *<mode> <station>* · Hbf ≈ *<n>* stops".
**Rule label:** "rail door-to-door for arrivals and departures" (green) / "one bus/tram interchange for intercity" (amber) / "cabs or long transfers to leave the city" (red).
**Data:** VBB static coords already loaded via `scripts/refresh_vbb`. Reuse the same points source as the YF transit tile; different tier function.
**Provenance key:** `vbb`.

### 3. International food — `intl_food`

**Question:** Can you eat and shop without German-only labels every day?

| Tier | Condition |
|------|-----------|
| Green | ≥5 international shops or restaurants within 800 m |
| Amber | 2 – 4 within 800 m |
| Red | 0 – 1 within 800 m |

**Numeric line:** "*<count>* international spots within *<r>* m walk".
**Rule label:** "cluster of international food and grocery" (green) / "a few options, mostly one direction" (amber) / "mainstream Rewe/Edeka territory" (red).
**Data:** Geofabrik OSM local snapshot. Tag rules (added to `_TAG_RULES`):
- `shop=supermarket` **AND** `origin ∈ {asian, turkish, indian, african, russian, polish, arab, italian}` **OR** `name` matches a curated small-list of chains (Vinh Loi, Öz-Gida, etc. — keep as a versioned constant in the refresh script).
- `amenity=restaurant` **AND** `cuisine` is not empty **AND** `cuisine ∉ {german, regional, european}`.
- Deduped by centroid per the `_merge_bod_and_osm` pattern (§14.6).

**Provenance key:** `osm_geofabrik`.

### 4. Coworking + Wi-Fi cafés — `coworking`

**Question:** Where do you plug in during your first month before the desk arrives?

| Tier | Condition |
|------|-----------|
| Green | ≥3 within 1 km |
| Amber | 1 – 2 within 1 km |
| Red | 0 within 1 km |

**Numeric line:** "*<count>* remote-work spots within *<r>* m".
**Rule label:** "walkable coworking scene" (green) / "one or two anchors" (amber) / "no laptop-friendly options nearby" (red).
**Data:** Geofabrik OSM local. Tag rules:
- `office=coworking`.
- `amenity=cafe` **AND** `internet_access ∈ {wlan, yes}`.

**Provenance key:** `osm_geofabrik`.

### 5. English-speaking clinic — `english_clinic`

**Question:** Who do you see when you get sick and don't yet trust your German?

| Tier | Condition |
|------|-----------|
| Green | ≥1 doctor/clinic with `language:en=yes` within 1.2 km |
| Amber | Nearest such practice 1.2 – 3 km |
| Red | None within 3 km |

**Numeric line:** "*<distance>*m to *<practice name>* (English) · *<total>* practices nearby".
**Rule label:** "English-speaking medical care in walking distance" (green) / "reachable, will need a short transit ride" (amber) / "no English-tagged practice nearby — expect German or telemedicine" (red).
**Caveat (permanent):** "OSM community-tagged — inner-district coverage good, outer may under-report" (identical pattern to YF pediatrician).
**Data:** Geofabrik OSM local. Tag rules:
- `amenity ∈ {doctors, clinic, hospital}` **AND** `language:en=yes`.
- Secondary metadata line: total practices (any language) within 1 km, from the same OSM bucket — surfaces baseline density even where the English tag is missing.

**Provenance key:** `osm_geofabrik`.

### 6. Neighbourhood profile — `gesix_newcomer`

**Question:** What is the socioeconomic band of the Planungsraum this address sits in — and what does that mean for someone landing here fresh?

**Not a traffic light.** No tier badge, no numeric on the face, no rule label on the face. The face carries the label + a one-line hint ("socioeconomic band of this Planungsraum · tap for detail"). The modal renders the same 5-segment quintile bar the YF `gesix` tile uses today and highlights the Planungsraum's quintile.

**Face rendering:** `tier: "unknown"`; face shows label + hint only, matching the YF gesix pattern.

**Modal rendering:** identical quintile-bar component to YF gesix — reuse the JS render function.

**Data:** Berlin Geoportal WFS `gssa_gesix2022` (447 Planungsraum polygons), already loaded into `Index` at boot and queried via `Index.gesix_at(lon, lat) -> {plr_name, quintile_5, rang, total}`. No new data path.

**Insight framing (newcomer POV):** the `gesix_newcomer_insight` template reasons about:
- What quintile 1 vs quintile 5 means for an expat landing without a German network — quintile 5 (highest social burden) often has denser mutual-aid networks, cheaper rent, and a more diverse street mix; quintile 1 (lowest burden) is quieter and pricier but more monolingual-German.
- Affordability signal: lower quintiles often correlate with rent bands newcomers can plausibly land on the first lease.
- Integration signal: mid-quintiles (2–4) tend to have the most mixed international presence.
- Honest caveat: GESIx is a 2022 composite; individual streets vary; the reader should walk the block before signing.

**Anti-inversion invariant:** the template must never claim a quintile-1 profile is "worse for newcomers" than quintile-5 or vice versa — the frame is *tradeoffs*, not ranking. The `__main__` selfcheck asserts both a q1 and a q5 example produce balanced, non-ranking prose.

**Provenance key:** `gesix`.

## Response shape

`GET /api/lookup?address=…` grows one block:

```json
{
  "lens": {
    "young_family": { ... existing ... },
    "newcomer": {
      "version": 1,
      "tiles": [
        {
          "key": "buergeramt",
          "label": "Bürgeramt reach",
          "icon": "buergeramt",
          "tier": "green" | "amber" | "red" | "unknown",
          "rule": "…",
          "numeric": "…",
          "caveat": null | "…",
          "features": [ { "name": "…", "distance_m": 780, "lat": …, "lon": …, "meta": { … } } ],
          "metadata": { … optional, tile-specific … },
          "sources": ["buergeramt"] | ["osm_geofabrik"] | ["vbb"] | ["gesix"]
        }
        // …6 tiles total, in the fixed order above (5 traffic-light + gesix_newcomer last)
      ]
    }
  }
}
```

Order is fixed by `LensConfig.tile_order` — no client-side sort.

## LLM insight templates

Six new files under `v0.1/inference/templates/`. Each follows the shape of `refuge_insight.py`:

- `SAMPLER = {"temperature": 0.55, "max_tokens": 180, "top_p": 0.9}` — same as other insight templates.
- `_SYSTEM = "You write short paragraphs for someone new to Berlin. Address them in the second person, plural ('we'). Do not use German words the reader has not seen before without a one-line gloss. Never invert the meaning of a red tier into positive framing."` (adjust per card as needed).
- `build_messages(context)` — one-shot exemplar showing a red-tier response and a green-tier response so the model learns not to invert.
- `run(backend, ctx)` — pure pass-through, mirrors existing templates.
- `__main__` selfcheck — assert prompt shape and anti-inversion on a hand-crafted red-tier context.

**Register in `inference/main.py`:** one row per new template in `TEMPLATES`.

**Register in `v0.1/app/routes/card_insight.py`:** one row per card key in `_CARD_CONTEXT_BUILDERS`. Reuse `_ctx_features` for `intl_food`, `coworking`, `english_clinic`, `transit_newcomer`. Reuse the existing `_ctx_gesix` for `gesix_newcomer` — context shape is identical; the newcomer angle lives in the template's system prompt, not the context builder. Add `_ctx_buergeramt` if the buergeramt tile emits WFS-specific fields (opening hours, phone) that need shape distinct from generic features.

**`gesix_newcomer_insight` template — extra requirements:**
- System prompt frames GESIx as *tradeoffs* for a newcomer, not a ranking.
- One-shot exemplar shows a q1 (lowest social burden) prose and a q5 (highest social burden) prose, each surfacing tradeoffs.
- `__main__` selfcheck asserts: (a) neither q1 nor q5 outputs contain the words "better" / "worse" / "avoid" in a ranking sense; (b) both outputs contain some mention of language mix, rent band, and a "walk the block" caveat; (c) prompt shape mirrors `gesix_insight` (family variant) so a shared harness can validate both.

## Frontend

- `web/static/app.js` — extend the existing `LIFE_MODE_LENSES` registry:

```js
const LIFE_MODE_LENSES = {
  young_family: { label: 'Young Family', desc: '…', tiles: [...], insightKeys: {...} },
  newcomer:     { label: 'Newcomer',     desc: 'First 90 days in Berlin — registration, transit, English-friendly services.',
                  tiles: ['buergeramt','transit_newcomer','intl_food','coworking','english_clinic','gesix_newcomer'],
                  insightKeys: { buergeramt: 'buergeramt_insight', ..., gesix_newcomer: 'gesix_newcomer_insight' } }
};
```

- `renderLensPicker` already reads from the registry — no changes.
- `renderLensTile` already reads `{tier, rule, numeric}` — no branch needed unless a tile wants a bespoke face treatment. All five newcomer tiles use the standard label + rule face; no numeric on face (Spec A UI rule).
- `renderLensModalBody` — reuse the Spec D features-list + map-pin flow. For `gesix_newcomer` reuse the existing YF `gesix` modal branch that renders the 5-segment quintile bar — the block is identical because the metadata payload is identical; only the insight-button `card` key differs.
- `_INSIGHT_VINTAGE` — add vintages for the six new cards (`buergeramt`, `transit_newcomer`, `intl_food`, `coworking`, `english_clinic`, `gesix_newcomer`).
- The Get Insight button is generic — no wiring needed. Frontend POSTs `{card, tile, lens: 'newcomer'}` to `/api/card_insight`; the dispatcher already routes by `card`.

**Cache-buster:** bump `?v=` on `app.js` and `app.css` per the standing frontend-edit rule.

## Selfchecks

- `app.core.scorer.__main__` — extend to cover each of the five new `_tier_*` functions with green/amber/red/unknown branches. Also assert the `newcomer_lens` composer emits the `gesix_newcomer` shape-only tile (no tier badge, metadata carries `plr_name` / `quintile_5` / `rang` / `total`). Pure asserts, no network.
- `app.core.osm_local.__main__` — extend with a fixture-based assertion that the four new bucket categories load from a synthetic snapshot.
- `inference.templates.<name>.__main__` — one per new template; assert prompt shape and anti-inversion. `gesix_newcomer_insight.__main__` additionally asserts the non-ranking language rule described in §LLM insight templates.
- `app.selfcheck` orchestrator — include a live-run against one Berlin address in the inner districts (Bergmannstraße 27 is a good all-tiers-green baseline; Marzahn address is a red-tier stress test).

## Provenance

Every response must carry provenance strings from `cfg.attribution`:
- `buergeramt` → "Berlin Geoportal — Bezirks-Services WFS · Data licence Berlin (dl-de/by-2-0)".
- `osm_geofabrik` → "OSM contributors, Geofabrik weekly extract, ODbL".
- `vbb` → "VBB Verkehrsverbund Berlin-Brandenburg, open transit data".

`v0.1/app/cities/berlin.py` gets one new `attribution` key (`buergeramt`); the others already exist.

## Rollout order

1. **Refresh script:** extend `_TAG_RULES` in `scripts/refresh_osm_amenities.py` with `intl_food`, `coworking`, `english_clinic`, `buergeramt` (OSM fallback). Run one refresh cycle end-to-end and verify JSON payload sizes.
2. **Scorer + composer:** add the five `_tier_*` functions and `newcomer_lens` composer (including the shape-only `gesix_newcomer` tile) with pure selfchecks.
3. **CityConfig + lookup route:** wire the new lens into `/api/lookup`.
4. **Inference templates + card_insight dispatcher:** add the six new templates, register them in `TEMPLATES` and `_CARD_CONTEXT_BUILDERS`.
5. **Frontend registry:** extend `LIFE_MODE_LENSES` with the newcomer entry (6 tiles), add insight vintages, bump cache-buster.
6. **Live QA:** run through Bergmannstraße 27 (expected mostly-green baseline, mid-quintile) and Marzahn/Buch (expected red baseline, higher quintile). Screenshot each modal — including `gesix_newcomer` to spot-check the anti-ranking prose.
7. **Bürgeramt WFS upgrade:** replace OSM fallback with the Berlin Geoportal WFS layer once step 5 is stable; ship as a follow-up commit.

## Global constraints inherited from prior specs

- Stdlib + shapely + FastAPI + httpx only in `app/`. No new dependencies.
- `ponytail:` comments are load-bearing; do not remove.
- BOD first, OSM as fallback/supplement. Every feature carries `source`.
- Behavioural parity with YF composer where a helper is reused.
- Neumorphism UI: `.cell` shape, `--neumo-sh-*` tokens, Plus Jakarta Sans, inline SVG in `ico = {...}`, no build step, no bundler.
- Cache-buster bump on every frontend edit.
- CORS opt-in via env; no wildcards.

## Open questions

- (Q1) Should the buergeramt WFS layer land in the first commit, or is OSM-fallback acceptable to ship v1? — Default answer: OSM fallback ships v1; WFS is a fast-follow.
- (Q2) Do we want a "language schools within walk" bonus line inside the `english_clinic` insight modal, or leave language schools out entirely? — Default: leave out; it's a separate future tile.
- (Q3) Should the Newcomer lens be the default when Life Mode is first turned on, or does Young Family remain the default? — Default: Young Family stays the default; the picker exposes both.

## References

- `microservice-refactor-plan.md` §7.1, §7.3, §7.5, §14.6.
- `docs/superpowers/specs/2026-08-09-young-family-lens-design.md` — parent spec for lens abstraction, `LensConfig`, tier convention, UX shape.
- `docs/superpowers/specs/2026-08-10-clickable-lens-tiles-design.md` — mandates `features` array + modal / map integration.
- `v0.1/app/routes/card_insight.py` — single-endpoint insight dispatcher; extension point is `_CARD_CONTEXT_BUILDERS`.
- `v0.1/scripts/refresh_osm_amenities.py` — Geofabrik weekly refresh; extension point is `_TAG_RULES`.
- `v0.1/web/static/app.js` — `LIFE_MODE_LENSES` registry; extension point is one new entry.
