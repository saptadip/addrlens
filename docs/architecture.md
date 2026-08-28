# AddrLens — architecture

This document explains how AddrLens is put together at the level a reviewer, contributor, or new operator needs to onboard in twenty minutes. It's paired with the [Hetzner deploy playbook](../v0.1/docs/hetzner-deploy.md) — one reads at the *what/why* level, the other at the *what commands do I run* level.

The active tree is [`v0.1/`](../v0.1/). Historical prototypes at the repo root (`phase0/`–`phase3/`, `micro-service/`) are preserved as-shipped; nothing new lands in them.

## Design philosophy

Three constraints shape almost every architectural choice:

1. **Free to run at Berlin-scale traffic.** ~350k Berliner addresses × ~1000 queries/day fits inside €12/month of Hetzner + a Cloudflare Free plan + a Cloudflare Workers AI free-tier quota. Nothing depends on a paid API.
2. **Every user-visible fact must carry its licence.** Berlin Senate, VBB, BVG, OpenStreetMap — each has its own attribution rules. Provenance is not an afterthought; it's a first-class field on every JSON response.
3. **Degrade gracefully, never crash.** Berlin Senate WFS had multi-day maintenance in August 2026; Cloudflare Workers AI throttles free-tier accounts; OSM Geofabrik is one download away from a bad Sunday. Every external dependency has an in-app fallback.

## Two-service split

The runtime is two containers on one Docker bridge, plus a `cloudflared` sidecar that provides the only ingress path.

```
                                    ┌────────────────────────────────┐
                                    │  Cloudflare Edge (Frankfurt)   │
                                    │  · TLS termination             │
                                    │  · WAF Custom Rules (5, free)  │
                                    │  · 1 Rate Limiting Rule (free) │
                                    └────────────────┬───────────────┘
                                                     │  QUIC tunnel (outbound-only)
                                    ┌────────────────▼───────────────┐
                                    │   cloudflared   (128 MB)       │
                                    │   sidecar container            │
                                    └────────────────┬───────────────┘
                                                     │  addrlens_net (docker bridge)
                     ┌───────────────────────────────┼───────────────────────────────┐
                     │                               │                               │
             ┌───────▼───────┐               ┌───────▼───────┐               ┌───────▼───────┐
             │    app        │               │  inference    │               │  umami-db     │
             │  FastAPI      │◄──────────────┤  FastAPI      │               │  Postgres 16  │
             │  Python 3.11  │  /summarize   │  Python 3.11  │               │  (analytics)  │
             │  700 MB limit │               │  2.8 GB limit │               │  200 MB       │
             └───┬───────────┘               └───────┬───────┘               └───────▲───────┘
                 │                                   │                               │
                 │                                   │                               │
       ┌─────────▼─────────┐                 ┌───────▼───────────┐               ┌───▼───────┐
       │ In-process state  │                 │  llama.cpp        │               │  umami    │
       │  · Index (WFS)    │                 │  local Qwen 1.5B  │               │  (UI)     │
       │  · address_index  │                 │  (fallback path)  │               │  350 MB   │
       │  · osm_local      │                 │                   │               └───────────┘
       │  · history TTL    │                 └───────┬───────────┘
       └───────────────────┘                         │                                    ▲
                                                     │ HTTPS                              │
                                                     ▼                                    │
                                          Cloudflare Workers AI                           │
                                          (@cf/meta/llama-3.1-8b-instruct-fast)           │
                                                                                          │
       Weekly systemd timer ────► scripts/refresh_osm_amenities  ────► berlin-amenities.json
                                                                 └───► berlin-addresses.json
                                                                                          │
                                                             visitor's browser ───────────┘
                                                             (tracker script from
                                                              umami.addrlens.de)
```

**Why two services, not one?**

- The LLM occupies ~1.4 GB of RAM whether the app needs it in the current request or not. Isolating it in `inference` means the app container can crash-restart in 5 s without warming the model again.
- The LLM is single-threaded (llama.cpp is not thread-safe). Isolating it lets us serialise generation under a process-wide lock without slowing every other endpoint.
- The `inference` service is city-agnostic; the `app` service picks a `CityConfig` at boot via `CITY=<slug>`. This is the multi-city seam: to add Hamburg, we spin up a second `app` container against the same shared `inference`.

## Request flow: `/api/lookup?address=…`

The core endpoint. What happens on the hot path:

```
1. Browser  ── GET  /api/lookup?address=Bergmannstraße+27,+10961
                     │
2. Cloudflare edge   │  · TLS terminate
                     │  · WAF Custom Rules (empty-UA block, country friction, health skip)
                     │  · Rate Limiting Rule if the path matches (/api/history only currently)
                     │  · X-Real-IP + CF-Connecting-IP headers appended
                     ▼
3. cloudflared       │  · QUIC tunnel from CF edge → sidecar
                     ▼
4. app: uvicorn      │  · Route match: routes/lookup.py
                     │
5. slowapi decorator │  · key_func reads CF-Connecting-IP (not request.client.host, which
                     │    would be the cloudflared container's docker-bridge IP)
                     │  · 60/min per IP; 429 with a JSON body on breach
                     ▼
6. Index.geocode()   │  · Live WFS call to gdi.berlin.de/services/wfs/adressen_berlin
                     │    (only WFS call still made per request; everything else is preloaded)
                     ▼
7. Index queries     │  · catchment polygon (preloaded shapely tree)
                     │  · schools, kitas, hospitals, fire, quiet zone, protection zone,
                     │    pools, trees, air, heat, GESIx (all preloaded / bbox-cached)
                     │  · S/U/Tram nearest (preloaded VBB coords)
                     │  · OSM local buckets (intl_food, coworking, library, etc.)
                     ▼
8. scorer.compose    │  · young_family_lens(cfg, index, lon, lat, ...)
                     │  · newcomer_lens(cfg, index, lon, lat, amenities=…)
                     │  · admin_offices_others(cfg, index, lon, lat)  ← Bureaucracy bundle
                     ▼
9. Response builder  │  · Address + catchment + schools + kitas + connectivity + all lenses
                     │    + others + provenance map (one entry per dataset used)
                     ▼
10. Browser SPA      │  · render() populates the raw view + both Life Mode lens tabs
                     │  · Umami tracker fires "lookup" event via /api/send
```

All eight preloaded layers plus the LLM live in-process. Boot cost: ~5-15 s (dominated by cold WFS calls to `gdi.berlin.de`). `/ready` returns 503 during that window so an orchestrator won't send traffic to a cold container.

## Request flow: `/api/history` — the LLM path

`/api/history` is the only endpoint that routes to Cloudflare Workers AI. Every other LLM call (`/api/card_insight`, `/api/explain`, `/api/impression`) stays on the local llama.cpp inference.

```
1. GET /api/history?lat=…&lon=…&street=…&hnr=…&plz=…
                              │
2. slowapi 10/min per IP      │
                              ▼
3. Cache lookup                Key = (city_slug, round(lat,3), round(lon,3))
   (7 days TTL, 1000 entries)  ≈ 100 m × 67 m grid cells at Berlin's latitude
                              │
             ┌────────────────┼────────────────┐
             │ hit                             │ miss
             ▼                                 ▼
      Return {..., cached: true}      OSM historic query (in-process,
      < 5 ms                          bbox from osm_local cache)
                                                │
                                                ▼
                                       Address-agnostic prompt:
                                       street/hnr/plz stripped;
                                       borough + Ortsteil only
                                                │
                                                ▼
                                     POST /summarize (inference svc)
                                                │
                              ┌─────────────────┴─────────────────┐
                              │ if template ∈ REMOTE_TEMPLATES     │
                              ▼                                    ▼
                    Cloudflare Workers AI                   Local llama.cpp
                    @cf/meta/llama-3.1-8b-instruct-fast     Qwen 2.5 1.5B Q4_K_M
                    ~0.7 s wall time                        ~35 s wall time
                              │                                    ▲
                              │  on 4xx / 5xx / timeout             │
                              └─────► fallback ─────────────────────┘
                                                │
                                                ▼
                                     Response cached, {cached: false} returned
```

Address-agnostic prompts are essential: the cache key rounds coordinates to ~100 m, so many addresses share the same entry. If the LLM had written "As you enter Buschallee 3…" the cached paragraph would show up on Buschallee 5 too. The prompt is scoped to borough + Ortsteil only; verified against a live test with two neighbouring addresses.

## Request flow: `/api/suggest?q=…` — address autocomplete

```
Browser types "berg"
    │  debounce 130 ms
    ▼
GET /api/suggest?q=berg&limit=8
    │  slowapi 5/second per IP
    ▼
AddressIndex.search(q, limit=8)      ← in-memory binary search
    │  · normalise: lowercase, ß→ss, umlaut strip
    │  · fold street suffix: "str." / "straße" / "strasse" → "strasse"
    │  · sorted prefix range via bisect_left/bisect_right
    ▼
Return { hits: [{label, street, hnr, plz, lat, lon}, ...] }
< 1 ms per query, 414k addresses in ~30 MB of RAM
```

Data source is `berlin-addresses.json` produced by the weekly OSM refresh timer — extracted from `berlin-latest.osm.pbf` in the same osmium pass that produces `berlin-amenities.json`. Nodes with `addr:street + addr:housenumber` and ways carrying the same tags (centroid computed) are collected; ~414k unique addresses in Berlin OSM as of August 2026.

## Data-plane summary

| Layer | Where it lives | Refresh cadence | What happens on outage |
|---|---|---|---|
| `Index.esbs`, `Index.schools`, `Index.kitas`, etc. | in-process, built at boot from `gdi.berlin.de` WFS | app restart | app `/ready` stays 503 until Senate WFS returns |
| `Index.osm_local` (amenity buckets) | in-process, loaded from `berlin-amenities.json` | weekly systemd timer at 03:00 Sunday | stale-but-usable — up to 6 days out of date |
| `Index.address_index` (autocomplete prefix trie) | in-process, loaded from `berlin-addresses.json` | same weekly timer | dropdown empty; typed lookups still work |
| History TTL cache | in-memory `cachetools.TTLCache` | 7-day TTL; cleared on process restart | first hit re-generates; no persistence loss beyond that |
| Umami session data | Postgres in `umami-db` container, bind-mounted to `/srv/addrlens/umami-db` | never (append-only) | analytics missing for the outage window; app itself unaffected |
| Sentry events | Sentry EU region SaaS | n/a | errors miss the dashboard; app + user experience unaffected |

## Multi-city seam

Adding a city is meant to be one file plus one deploy:

1. Create `v0.1/app/cities/hamburg.py` with a `HAMBURG: CityConfig` constant. `CityConfig` is a `frozen dataclass` — every field is required, missing ones fail loudly at import.
2. Spin up a second `app` container with `CITY=hamburg` and its own domain (`hamburg.addrlens.de`).
3. Share the same `inference` service — it's already city-agnostic (accepts `city` in the `/summarize` payload but does not route on it today).

Nothing in `app/core/` reads city-specific constants directly; every helper takes a `CityConfig` argument. `app.selfcheck.run_cities_isolation` boots each city module in a fresh subprocess to guard this promise.

## Rate-limiting layers

Belt-and-suspenders — three enforcement points:

1. **Cloudflare WAF Custom Rules (free tier, 5 slots).** Static conditions: empty-UA block on `/api/*`, country-of-origin friction, `/health` + `/ready` skip. Runs before the origin ever sees the request.
2. **Cloudflare Rate Limiting Rule (free tier, 1 rule).** Currently on `/api/history` — 5 requests per 10 seconds per IP, action = Block. Free tier's mitigation timeout is 10 s; Managed Challenge is a paid-tier action.
3. **`app/core/rate_limit.py` in-process (`slowapi`).** Per-IP + per-endpoint. Key function reads `CF-Connecting-IP` (never `request.client.host`, which is always the cloudflared bridge IP in prod). Current limits:
   - `/api/lookup` 60/min
   - `/api/history` 10/min
   - `/api/card_insight` 30/min
   - `/api/suggest` 5/second

`/health` and `/ready` are intentionally unlimited so uptime probes never trip.

## Observability

- **Sentry** for unhandled exceptions. EU region ingest (`de.sentry.io`, Frankfurt). `send_default_pii=False` plus a `before_send` scrubber that redacts address / IP query parameters and the entire request body of the inference service. See [`v0.1/app/main.py`](../v0.1/app/main.py) for the exact scrubber.
- **Umami** for engagement analytics. Self-hosted alongside the app on the same box. Cookieless, no cross-site tracking. Custom events wired at 8 touchpoints — see [Umami setup section in the deploy playbook](../v0.1/docs/hetzner-deploy.md).
- **`docker compose logs`** for runtime traces. Inference service logs `remote inference fell back to local (history): <error>` when the Cloudflare Workers AI path fails and the local fallback picks up.

## What's intentionally NOT here

- **No ORM.** Data reads are direct `httpx.get()` against WFS with an internal in-process cache (Shapely trees for point layers, bbox-keyed dicts for large layers). Introducing SQL would triple boot complexity for no query-shape benefit.
- **No frontend framework.** Vanilla JS + CSS + Leaflet. Cache-busting via query string. Every asset is inline-servable from `web/static/`. Zero build step; a deploy is `git pull && update.sh`.
- **No CI in-tree today.** `python -m app.selfcheck` and per-module `__main__` blocks are the current QA gate; a GitHub Actions workflow that runs them on PR is one of the roadmap items called out in the [README](../README.md#roadmap).
- **No user accounts.** No login, no sessions, no cookies. `localStorage` holds a lens preference and a small compare list; nothing leaves the browser.

## Failure modes and how they degrade

| Failure | User-visible impact |
|---|---|
| `gdi.berlin.de` WFS returns HTML `Wartungsarbeiten` page | New app containers fail to boot; existing containers keep serving from the in-process `Index` until they restart. **Snapshot fallback is a roadmap item — this remains the single largest availability risk today.** |
| Cloudflare Workers AI returns 5xx or a deprecated-model error | Inference service logs the error, falls through to local llama.cpp on the same box (~35 s wall time for history). No user-visible failure. |
| Local llama.cpp fails to load | `/api/card_insight`, `/api/explain`, `/api/impression` return 503 with a "warming up" message. `/api/history` still works via Cloudflare Workers AI. `/api/lookup` unaffected. |
| Cloudflare Tunnel disconnects | Every visitor sees CF's edge error page ("Origin is unreachable"). Restart `cloudflared` container — 5 s recovery. |
| Umami container crashes | Analytics missing for the outage window; app itself unaffected. Errors reach Sentry as usual. |
| OSM refresh timer fails to run | Amenity data goes stale (up to 7 days by design, longer if the failure is silent). `/api/suggest` still returns hits from the last snapshot. |
| Hetzner box loses network | Full outage. UptimeRobot / equivalent will detect it via `/health` probe if configured (roadmap). |

## References

- [Product doc §14 (engineering conventions)](../berlin-family-address-intelligence-product-doc.md) — coding standards
- [Hetzner deploy playbook](../v0.1/docs/hetzner-deploy.md) — operator runbook
- [Cloudflare WAF setup](../micro-service/docs/cloudflare-waf-setup.md) — free-tier edge rules
- [Social embed image playbook](../v0.1/docs/social-embed-og-image.md) — post-launch polish
- [Datenschutzerklärung](../legal/datenschutzerklaerung.md) — every third-party processor named + legal basis
