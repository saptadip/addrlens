# Public JSON API — feature proposal

**Status:** Proposal · not scheduled · easy build (~3-4 weeks); bundle with `berlin-open-data-adapter` grant application
**Author:** Saptadip
**Last updated:** 2026-09-09

## What

Turn AddrLens's internal `/api/*` endpoints into a versioned, documented, key-guarded **public JSON API** at `/api/v1/*`. Third-party developers (journalists, urban planners, other civic apps) call it to get the same address-aggregate data the AddrLens SPA shows.

Companion to [`berlin-open-data-adapter.md`](berlin-open-data-adapter.md) — the API is the *hosted* form of the library. Two-tier public infrastructure: `pip install` the library or `curl` the API, same data, same provenance guarantees.

## Why

- **On the existing roadmap already** ([README → Roadmap](../../README.md#roadmap)): "Public JSON API with a documented schema, so other Berlin civic-tech projects can reuse the aggregated address data without re-implementing 20 WFS clients."
- **FastAPI already generates OpenAPI** — 80 % of the work is done by the framework; the remainder is versioning, schema stability, and access control.
- **Grant signal:** Reviewers respond to "hosted reference implementation" language. Library alone reads as academic; library + hosted API reads as production infrastructure.
- **Ecosystem catalyst:** Journalism (Tagesspiegel, taz, RBB), research (TU Berlin, HU Berlin urban studies), municipal tools — all currently blocked from address-scale open data by the cost of building 20 WFS clients.

## Current state

Every route the API would expose already exists internally, just not versioned or documented as public:

| Endpoint | Current path | Notes |
|---|---|---|
| Full address aggregate | `/api/lookup` | Aggregating; catchment + schools + kitas + amenities + noise + air + heat + provenance |
| Per-lens tiles | (embedded in `/api/lookup`'s `lens` envelope) | Would extract to `/api/v1/lens/{slug}/lookup` |
| Per-lens AI insight | `/api/lens_insight` | POST-based currently; would become GET-friendly |
| Historic markers | `/api/history` | Existing |
| Amenity fetch | `/api/amenities` | Existing |
| Noise-only fetch | `/api/noise` | Existing |
| Address autocomplete | `/api/suggest` | Existing |

## Scope

### Phase 1 — cheap wins (3-4 days)

- Add `/api/v1/` prefix without breaking existing paths (mount both).
- Polish FastAPI-auto-generated OpenAPI (tags, descriptions, examples).
- Publish Swagger UI at `/api/v1/docs` and Redoc at `/api/v1/redoc`.
- Add API description page at `docs.addrlens.de` (or `/api/v1/`).

### Phase 2 — production-grade contract (2-3 weeks on top)

- Freeze response shapes with typed Pydantic response models (currently loosely-typed dicts).
- Deprecation policy + versioning strategy (docs page).
- API-key allowlist: simple form-based request → email-issued keys → header-based auth (`Authorization: Bearer <key>`).
- Per-key slowapi rate limits (10 req/min free tier; higher for verified journalists / research groups).
- CORS opt-in for cross-origin browser calls (allowlist known consumers).
- Terms of use + attribution requirements (per-dataset provenance is already baked in; consumers must display it).
- SDK generation via `openapi-generator` → Python, JS, Ruby clients (published to PyPI + npm + RubyGems).

### Phase 3 — polish (opportunistic)

- Usage dashboard for API-key holders.
- Bulk endpoints (multiple addresses in one call).
- Multi-region CDN caching via Cloudflare (already fronts the site).
- Async webhook subscriptions ("notify me when noise data for this address updates").

## Endpoint shape (design sketch)

```
GET  /api/v1/address/lookup?street=Kastanienallee&hnr=12&plz=10435
     → Full envelope (address + catchment + schools + kitas + amenities +
       noise + air + heat + provenance)

GET  /api/v1/address/lookup?address=Kastanienallee%2012%2C%2010435
     → Convenience — free-text form of the above

GET  /api/v1/lens/{lens_slug}/lookup?address=...
     → Only the tiles for one lens (young_family | newcomer |
       quiet_living | commuter). Cheaper response, faster.

GET  /api/v1/lens/{lens_slug}/insight?address=...
     → AI Insight summary (Cloudflare Workers AI). Cache-headers respected.

GET  /api/v1/dataset/{dataset_id}/near?lat=...&lon=...&radius_m=...
     → Raw per-dataset queries — kitas, schools, hospitals, etc. Bypasses
       the aggregation entirely. Powers the "raw open data" story.

GET  /api/v1/openapi.json    (auto-generated)
GET  /api/v1/docs            (Swagger UI)
GET  /api/v1/redoc           (Redoc UI)
```

## Grant angles

**Standalone weak.** "Public API" reads as service, not infrastructure. SovTech Fund likely rejects.

**Companion strong.** Bundled with `berlin-open-data-adapter`, the pitch becomes: *"Two-tier public infrastructure — install as a library or call as an API — same provenance + normalisation layer underneath."* Same funding line, higher reviewer signal.

## Risks

1. **Traffic cost.** Hetzner CX22 (2 vCPU / 4 GB) will feel a popular journalist article. Mitigation: aggressive Cloudflare edge caching (24 h TTL on lookup — Berlin datasets change slowly). Post-launch, monitor and scale up to CX32 if needed (~€10/mo more).
2. **Schema stability.** Once versioned + advertised, breaking changes cost social capital. Discipline required.
3. **Abuse.** Scrapers, bots, LLM training harvesters. Rate-limit + API-key + robots.txt + Cloudflare WAF mitigate but don't eliminate. Acceptable for a public-good API.
4. **Attribution enforcement.** Terms of use require attribution — hard to enforce, honour-code. Acceptable for open-data spirit.
5. **Support burden.** Once public, developers file issues / ask questions. Budget ~2 hrs/week for support in the first year.

## Decision points that need user input

1. **Prefix strategy.** Add `/api/v1/` alongside existing `/api/*` (dual-serve) OR retrofit existing paths to `/api/v1/` (redirect from `/api/*`)?
2. **API-key tier.** Free public tier only, or free + pro? Introducing a paid tier means invoicing, VAT, etc. — likely defer to year 2.
3. **Docs domain.** `/api/v1/docs` on the same origin, or dedicated `docs.addrlens.de`?
4. **Journalism relationship.** Reach out to Tagesspiegel data-desk / taz data-desk / RBB proactively for early adopter feedback, or wait for organic adoption?
5. **Endpoint scope.** Ship only `/address/lookup` initially or the full endpoint list from day one?

## Bundling with `berlin-open-data-adapter`

If both features ship, the sensible sequence is:
1. Weeks 1-4: adapter v0.5 (pip package extracted from `v0.1/app/core/`).
2. Weeks 5-7: `/api/v1/*` (thin FastAPI wrappers over the adapter — dogfooding).
3. Week 8: grant applications (NLnet first, SovTech next round).

The API alone is 3-4 weeks. The adapter alone is 6-8. Together — with the API implemented as a thin layer over the library — total is ~10-12 weeks. The API "for free" costs about 2-3 extra weeks over adapter-only.
