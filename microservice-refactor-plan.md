# Microservice refactor + multi-city template — plan

Living plan for turning the current `phase2/` prototype into a
production-shape microservice that also acts as a template for other
German cities (Hamburg first, Munich / Köln / Frankfurt after).

Nothing has been implemented yet. Ships are sequenced so each is
independently deployable.

---

## 0. Confirmed defaults

| Decision | Locked value | Why |
|---|---|---|
| Web framework | **FastAPI** (uvicorn) | Pydantic validation + OpenAPI docs for free; small dep cost; well-supported Prometheus + rate-limit ecosystems. |
| Multi-city routing | **One instance per city** (`berlin.addrlens.de`, `hamburg.addrlens.de`, …). CITY env-var picks the config. | Cleaner blast radius (Hamburg WFS outage can't hurt Berlin); each city scales independently; per-instance startup memory stays small. |
| Cache strategy | **In-memory only for Ships A–C.** Redis adapter added in Ship D behind the same interface. | Simplest thing that works. Don't reach for Redis before metrics justify it. |
| LLM inference topology | **Shared inference service.** One inference cluster serves every city instance over HTTP. The model is NEVER baked into the per-city app image. | Keeps per-city app images lean (~200 MB) instead of multi-GB. Load a model once, serve N cities. Adding a city doesn't require pushing 2 GB of weights. See §7. |
| LLM provider | **Own infrastructure, own model. No third-party AI provider.** | GDPR: no cross-border transfer, no sub-processor to list, no DPA to negotiate. Matches the "open data only, no scraping" ethos. |

Once any of these needs to change, update this file first, then the code.

---

## 1. Target file layout

The current `phase0/`, `phase1/`, `phase2/` directories stay untouched —
they are the history-as-artefact per product doc §14.1. The new `app/`
sits alongside them as the production tree.

```
addrlens/
├── app/
│   ├── main.py                    # FastAPI app + startup wiring
│   ├── config.py                  # env-var loading, CITY selection
│   ├── core/                      # city-agnostic building blocks
│   │   ├── geo.py                 # haversine, bbox_around
│   │   ├── wfs.py                 # generic WFS GetFeature helper
│   │   ├── overpass.py            # Overpass mirror-fallback + rate limit
│   │   ├── cache.py               # in-memory now, Redis adapter later
│   │   ├── scorer.py              # stroller_score, noise_tier — pure fns
│   │   ├── merge.py               # _merge_bod_and_osm dedupe
│   │   └── models.py              # Pydantic response schemas
│   ├── cities/
│   │   ├── base.py                # CityConfig dataclass
│   │   ├── berlin.py              # Berlin: WFS URLs, layer names, field maps, attribution
│   │   ├── hamburg.py             # (stub, filled in Ship C)
│   │   └── munich.py              # (stub, filled later)
│   ├── routes/
│   │   ├── lookup.py              # /api/lookup
│   │   ├── amenities.py           # /api/amenities
│   │   ├── noise.py               # /api/noise
│   │   ├── config.py              # /api/config → city display name, attribution, defaults
│   │   └── health.py              # /health (liveness), /ready, /metrics
│   └── selfcheck.py               # runs the same assertions; `python -m app.selfcheck`
├── web/
│   ├── index.html                 # unchanged UI; hits /api/config for city-aware text
│   └── static/                    # only if CSS/JS is ever split out
├── tests/
│   ├── test_scorer.py             # pure-function unit tests
│   ├── test_merge.py
│   └── test_selfcheck_live.py     # network-gated integration
├── ops/
│   └── Dockerfile
├── pyproject.toml                 # fastapi, uvicorn[standard], shapely, httpx, prometheus-client, slowapi
├── .env.example                   # CITY=berlin, PORT=8000, REDIS_URL=, LOG_LEVEL=info
└── README.md
```

---

## 2. `CityConfig` shape

Every `core/` function takes a `CityConfig` instead of reading hard-coded
constants. This is the single change that unlocks per-city reuse.

```python
# app/cities/base.py
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class CityConfig:
    slug: str                       # "berlin"
    display_name: str               # "Berlin"
    default_center: tuple           # (lat, lon) for map init

    # Address geocoding
    geocoder: str                   # "wfs" | "nominatim"
    geocoder_wfs_url: Optional[str]
    geocoder_layer: Optional[str]
    geocoder_field_map: dict        # {"street": "str_name", "hnr": "hnr", "plz": "plz"}

    # Catchments
    catchment_wfs_url: str
    catchment_layer: str
    catchment_field_map: dict       # {"id": "esb", "district": "bezname"}

    # Schools
    schools_wfs_url: str
    schools_layer: str
    schools_field_map: dict         # {"name": "schulname", "type": "schulart", "public_flag": "traeger", "id": "bsn"}
    schools_public_value: str       # "öffentlich"
    schools_primary_types: frozenset

    # Bilingual programme (SESB for Berlin; each city has its own equivalent)
    bilingual_schools: dict         # {name_substring_lower: strand_label}

    # Kitas
    kita_wfs_url: str
    kita_layer: str
    kita_field_map: dict            # canonical → city-specific field names

    # Parks + playgrounds
    green_wfs_url: Optional[str]
    parks_layer: Optional[str]
    playgrounds_layer: Optional[str]

    # Façade noise
    noise_wfs_url: Optional[str]
    noise_layer: Optional[str]
    noise_field_map: dict           # {"total_den": "ges_den", "road_night": "str_n", ...}
    noise_year: int                 # for provenance strings

    # Bounds + attribution
    overpass_bbox: tuple            # sanity-check that input coord is in-city
    attribution: dict               # {"catchment": "...", "kitas": "...", ...}
```

---

## 3. Migration ships

Ordered. Each ship ends with a runnable service and passes selfcheck.

### Ship A — FastAPI refactor, Berlin-only  (~3 days)

Goal: same behaviour, same UI, running under uvicorn. All hardcoded
Berlin values still live in code — but inside `app/cities/berlin.py`.

Steps:
1. Scaffold `pyproject.toml`, `app/`, `web/`, `ops/Dockerfile`.
2. Move pure functions from `phase2/server.py` → `app/core/{geo,scorer,merge}.py` verbatim.
3. Move WFS + Overpass helpers into `app/core/{wfs,overpass}.py`.
4. Port the `Index` class into a startup wiring in `app/main.py` — load catchments, schools, kitas at boot.
5. Rewrite the four routes as FastAPI endpoints in `app/routes/` returning the same JSON shapes.
6. Serve `web/index.html` as a static file at `/`.
7. Port `_selfcheck` into `app/selfcheck.py`, invoked with `python -m app.selfcheck`.
8. Write minimal Dockerfile (python:3.11-slim, install deps, `CMD ["uvicorn", "app.main:app", …]`).

Ship criterion: existing frontend + selfcheck both work against the new
service, byte-for-byte identical API responses.

### Ship B — CityConfig extraction  (~2 days)

Goal: every `core/` function takes a `CityConfig`. Berlin behaviour unchanged.

Steps:
1. Write `app/cities/base.py` with the `CityConfig` dataclass.
2. Create `app/cities/berlin.py` populated with the values currently hardcoded in Ship A.
3. Refactor `core/` functions to accept a `CityConfig` parameter.
4. `app/config.py` picks the config by env-var `CITY=berlin` at startup.
5. Add `/api/config` returning `{display_name, default_center, attribution, …}`.
6. Update frontend to fetch `/api/config` once at load and inject city-aware strings (title, footer attribution).

Ship criterion: setting `CITY=berlin` reproduces exactly the Ship-A
behaviour; nothing Berlin-specific remains in `core/`.

### Ship C — Hamburg onboarding  (~1–2 weeks)

Goal: `CITY=hamburg` runs the same service against Hamburg data.

Steps:
1. Research Hamburg Geoportal (`geoportal-hamburg.de/geo-online/`) — catch WFS URLs for addresses, schools, Grundschul-Einzugsgebiete, Kitas, Grünflächen, strategische Lärmkarten.
2. Sample each layer to build the `field_map` translations.
3. Populate `app/cities/hamburg.py`.
4. Verify with a real Hamburg address end-to-end.
5. Add city selector on landing page (or set up subdomain routing).
6. Extend selfcheck to run under both `CITY=berlin` and `CITY=hamburg`.

Ship criterion: both cities served by the same codebase, switched by env var; a known Hamburg address returns catchment + kitas + noise correctly.

### Ship D — Production hardening  (~1 week)

Goal: safe to expose publicly.

Steps:
1. **Rate limiting** with `slowapi` (per-IP), plus a longer Overpass cache TTL.
2. **Structured logging** with `structlog` + request IDs; JSON output for log aggregators.
3. **Prometheus metrics** at `/metrics` (request count, latency histograms, cache hit/miss, WFS error rate).
4. **Readiness probe** `/ready` returns 503 until the startup Index has loaded (so a slow-cold container doesn't take user traffic prematurely).
5. **Timeouts + retries** on every outbound WFS / Overpass call.
6. **Cache adapter** — abstract the current in-memory dict behind an interface, add an optional Redis backend chosen by env-var `REDIS_URL`.
7. **CORS** middleware with an allow-list from config.
8. **Turnstile / hCaptcha** on the front-end lookup form to keep the free path from being scraped.

Ship criterion: passes a basic load test (10 rps sustained), rate-limits kick in above threshold, `/metrics` scrapes cleanly, WFS-timeout doesn't crash the process.

### Ship E — Deployment infrastructure

Out of scope per project decision. Owner picks target platform (Cloud
Run / Fly.io / Hetzner + Docker / …) and wires up CI/CD separately.

---

## 4. What definitely does NOT change

- **Frontend HTML.** Only difference is reading city-name + attribution from `/api/config`. Zero visual redesign.
- **Every algorithm** — `haversine`, `noise_tier`, `stroller_score`, `_merge_bod_and_osm`, tier thresholds. These are pure functions and port character-for-character into `core/`.
- **Selfcheck philosophy** — one runnable check per module, no framework required. `tests/` unit tests are additive, not replacement.
- **Ponytail conventions** (product doc §14). When Ship A lands, extend §14 with an §15 section covering microservice-specific conventions: FastAPI dependency-injection over global state, structlog for logging, `CityConfig` as the single source of city-specific truth, etc.
- **Attribution / provenance patterns** — every panel keeps its per-source stamp.

---

## 5. Time estimate

| Ship | Effort |
|---|---|
| A. FastAPI refactor (Berlin-only) | 3 days |
| B. CityConfig extraction | 2 days |
| C. Hamburg onboarding | 1–2 weeks |
| D. Production hardening | 1 week |
| E. Deployment | out of scope |

**Total to "microservice + template + one additional city live": ~3–4 weeks.**

Ship A is the biggest mental jump (routing rewrite). Everything after is
mostly moving code between files or filling per-city configs.

---

## 6. Per-city onboarding expectations (post-Ship-B)

| City | Expected effort | Blockers to check first |
|---|---|---|
| Hamburg | 1–2 weeks | Catchments confirmed open via Geoportal. |
| Munich (Bayern) | 2–3 weeks | "Sprengel" reconciliation across Landkreis boundaries. |
| Köln (NRW) | 2–3 weeks | Per-city variance within NRW — check Köln specifically. |
| Frankfurt (Hesse) | ⚠️ 4+ weeks or drop the flagship school feature | Hesse does NOT openly publish catchment polygons as of last check. Data-access request or scrape from district PDFs — outside the "no scraping" architectural rule, so may need to accept a reduced feature set for Frankfurt. |

Product doc §Phase 5 already orders replication by open-data maturity:
Hamburg → Munich → Köln → Frankfurt. This plan follows that order.

---

## 7. Shared inference service architecture (LLM)

Locked decision (§0): **the LLM runs as its own service, shared by every city
instance.** Per-city app containers stay lean and call the inference service
over HTTP. This section pins the shape so we don't accidentally bake a model
into a city image the first time it feels convenient.

### 7.1 Why shared, not embedded

- **Image size.** Per-city app image stays ~200 MB (Python + shapely +
  FastAPI). Model weights are ~900 MB (Qwen2.5-1.5B-Instruct-4bit) and the
  MLX/llama-cpp runtime adds ~500 MB. Multiplying that across N city images
  is pure waste — every deploy pushes gigabytes to the registry.
- **Cold-start latency.** A city container that has to load a 900 MB model on
  boot is minutes to ready. A city container that just imports `httpx` and
  calls `http://inference:8080/summarize` is seconds to ready.
- **Model swap.** Switching from Qwen 1.5B → 3B, or trying a new prompt
  template, is one deploy of the inference service. No app-side rebuilds,
  no per-city coordination.
- **Cost.** RAM for the model (~2 GB resident) is paid once per node, not
  once per city instance per node.

### 7.2 Component shape

```
  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
  │  berlin-app  │   │ hamburg-app  │   │  munich-app  │  … per-city app
  └──────┬───────┘   └──────┬───────┘   └──────┬───────┘     containers
         │                  │                  │             (~200 MB each)
         └──────────────────┼──────────────────┘
                            │  HTTP / JSON (private network)
                            ▼
                    ┌───────────────────┐
                    │ inference-service │              shared inference
                    │  - Qwen 1.5B      │              cluster (~2 GB
                    │  - prompt library │              resident, one or
                    │  - /summarize     │              more replicas)
                    └───────────────────┘
```

### 7.3 Inference service contract

Single container, one endpoint:

```
POST /summarize
Body: {
  "template": "impression" | "kita_translator" | "compare_verdict" | ...,
  "context": { ... arbitrary JSON grounded in rules-engine facts ... },
  "city":    "berlin" | "hamburg" | ...
}
Response: {
  "summary":  { <template-specific structured output> },
  "model":    "<model_id>",
  "trace_id": "<uuid>"      // for log correlation across services
}
```

**Prompt templates live in the inference service, not in the app**, so we
can iterate on wording without touching city code. The app sends *facts*;
the inference service composes the prompt from a versioned template
matched by `template` name.

### 7.4 Deployment shape

- **Sidecar in dev**: `docker compose up` runs one app + one inference
  container on the same host. `INFERENCE_URL=http://inference:8080` in the
  app env. Zero-friction local dev.
- **Kubernetes**: inference-service as its own `Deployment` behind a
  `ClusterIP` service. City apps address it by DNS
  (`http://inference.default.svc.cluster.local`). Autoscale independently.
- **Model weights**: baked into the inference image (immutable, reproducible)
  OR mounted from a shared volume (faster deploys, but bigger ops surface).
  Start with baked-in until a real reason to change.

### 7.5 Scaling knobs

| Concern | Knob |
|---|---|
| Latency under load | Horizontal replicas of inference-service (stateless once model is loaded). |
| Different model per city | Not supported by default. All cities share one model. If a city ever needs a bilingual variant, route by `city` param inside inference-service to a second model — but push back hard; per-city models kill the "one model, N cities" win. |
| Prompt experiments | Ship a new template with a versioned name (`impression_v2`); city apps opt in when ready. |
| Rate limiting | At the inference service (per-city or per-IP), not at each app. One place to enforce. |

### 7.6 Failure modes

- **Inference service unreachable** → city app returns `503` on the LLM
  endpoint with a plain-English error. The rest of the app (lookup,
  amenities, noise) is completely unaffected — LLM is strictly additive.
- **Model timeout / OOM** → inference service returns a 504; city app
  surfaces a "summary unavailable, tap Retry" UX. Never block the map.
- **Cold model** → first request after boot pays the ~5 s load cost;
  readiness probe (§Ship D) holds traffic until warm.

### 7.7 What this rules out

- **No LLM in the app image.** If a future ship proposes embedding a model
  into `berlin-app` for latency reasons, revisit §7.1 first — the answer is
  almost always "run more inference-service replicas closer to the app,"
  not "duplicate the model per city."
- **No third-party inference APIs** (OpenAI, Anthropic, Groq, …). Decision
  locked in §0: own infrastructure, own model. Revisit only with an
  explicit written GDPR / DPIA review.

### 7.8 Where the LLM work lands in the ship sequence

Not a numbered Ship — LLM integration is a **parallel workstream** that
proceeds independently of Ships A–D. Recommended order once Ship A is
green:

1. **Ship LLM-1**: extract the current `phase3/` inference logic into
   `inference/` at repo root (its own `Dockerfile`, `pyproject.toml`,
   `venv`). Publish the `/summarize` endpoint. Wire `berlin-app` to call
   it via `INFERENCE_URL`.
2. **Ship LLM-2**: template library grows (impression, kita_translator,
   compare_verdict, viewing_checklist, …). Each template is a small,
   versioned file.
3. **Ship LLM-3**: Prometheus metrics on the inference service (tokens/s,
   time-to-first-token, cache hit rate if we add prompt caching).

---

*How to use this file:* when starting Ship A, work top-down through §3.
Update §0 (confirmed defaults) if any is changed mid-flight. Move any
ship into a `Shipped` section at the bottom when it lands, with commit
hash + date. Keep this document alive.
