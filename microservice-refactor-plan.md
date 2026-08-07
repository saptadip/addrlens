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
| LLM runtime | **`mlx-lm` on Apple Silicon dev; `llama-cpp-python` + GGUF for Linux production.** Runtime switch happens in Ship LLM-1 pre-prod. | `mlx-lm` is Apple-Silicon-only, so the current `phase3/` code will not run on Linux servers. `llama.cpp` (GGUF) is the most portable path: same 4-bit quantized weights, CPU or GPU, runs anywhere. Model artefact stays comparable (`Qwen2.5-1.5B-Instruct-Q4_K_M.gguf` ≈ 1.0 GB). Prompt templates and post-processing are runtime-agnostic — they live above the inference call. |
| LLM hardware target | **CPU-only for v1** (1.5B Q4 on a modest x86 core is ~1–3 s/response). Move to GPU only if user-facing latency SLO tightens. | Keeps ops surface small and cost predictable. Batch throughput on CPU is fine at v1 traffic; if SLO ever demands <500 ms, add one GPU replica of the inference service. |
| Primary audience | **English-speaking expats new to Germany.** | Informs prompt tone (English-first, German admin terms glossed inline via `CityConfig.bilingual_glossary`) and tolerance for mild city-culture leaks across cities (e.g., Berlin's "Kiez" appearing in Hamburg impression output). The audience doesn't parse local nuance and the glossary translates the German anyway — so we don't gate onboarding on per-city prompt customization. Revisit if native-German-speaker demand appears. |

Once any of these needs to change, update this file first, then the code.

---

## 1. Target file layout

The current `phase0/`, `phase1/`, `phase2/` directories stay untouched —
they are the history-as-artefact per product doc §14.1. The new `app/`
sits alongside them as the production tree.

```
addrlens/
├── app/                            # per-city app service (one image, N instances)
│   ├── main.py                    # FastAPI app + startup wiring
│   ├── config.py                  # env-var loading, CITY selection
│   ├── core/                      # city-agnostic building blocks
│   │   ├── geo.py                 # haversine, bbox_around
│   │   ├── wfs.py                 # generic WFS GetFeature helper
│   │   ├── overpass.py            # Overpass mirror-fallback + rate limit + response cache
│   │   ├── cache.py               # in-memory now, Redis adapter later
│   │   ├── scorer.py              # stroller_score, noise_tier — pure fns
│   │   ├── merge.py               # _merge_bod_and_osm dedupe
│   │   ├── gloss.py               # apply CityConfig.bilingual_glossary to LLM output
│   │   └── models.py              # Pydantic response schemas
│   ├── cities/
│   │   ├── base.py                # CityConfig dataclass
│   │   ├── berlin.py              # Berlin: WFS URLs, layer names, field maps, glossary, attribution
│   │   ├── hamburg.py             # (stub, filled in Ship C)
│   │   └── munich.py              # (stub, filled later)
│   ├── routes/
│   │   ├── lookup.py              # /api/lookup
│   │   ├── amenities.py           # /api/amenities
│   │   ├── noise.py               # /api/noise
│   │   ├── impression.py          # /api/impression → calls inference-service
│   │   ├── explain.py             # /api/explain     → calls inference-service
│   │   ├── config.py              # /api/config → city display name, attribution, defaults
│   │   └── health.py              # /health (liveness), /ready, /metrics
│   └── selfcheck.py               # runs the same assertions; `python -m app.selfcheck`
├── inference/                      # shared LLM service (one image, shared by all cities)
│   ├── main.py                    # FastAPI app; POST /summarize
│   ├── runtime/
│   │   ├── mlx_backend.py         # dev / Apple-Silicon backend (mlx-lm)
│   │   └── llama_backend.py       # prod / Linux backend (llama-cpp-python + GGUF)
│   ├── templates/                 # versioned prompt templates (impression.py, explain.py, ...)
│   ├── selfcheck.py
│   ├── pyproject.toml             # extras: [dev] mlx-lm ; [prod] llama-cpp-python
│   └── Dockerfile                 # prod image ships llama.cpp only (Linux)
├── web/
│   ├── index.html                 # phase3 UI (neumorphic, modals, drag, save-PNG); reads /api/config for city strings
│   └── static/                    # vendor html-to-image here in prod (see Ship D)
├── tests/
│   ├── test_scorer.py             # pure-function unit tests
│   ├── test_merge.py
│   ├── test_gloss.py              # per-city glossary regex coverage
│   └── test_selfcheck_live.py     # network-gated integration
├── ops/
│   ├── Dockerfile.app             # per-city app image
│   └── Dockerfile.inference       # shared inference image (Linux + llama.cpp)
├── docker-compose.yml             # dev: 1 app + 1 inference container, wired via INFERENCE_URL
├── pyproject.toml                 # fastapi, uvicorn[standard], shapely, httpx, prometheus-client, slowapi
├── .env.example                   # CITY=berlin, PORT=8000, INFERENCE_URL=http://inference:8080, REDIS_URL=, LOG_LEVEL=info
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

    # Hospitals (BOD-first; OSM only supplements contact info)
    hospital_wfs_url: Optional[str]
    hospital_layer: Optional[str]
    hospital_field_map: dict        # {"name": "bezeichnung", "beds": "betten", "operator": "traeger", ...}
    hospital_radius_m: int          # search radius (Berlin uses 2000)

    # Drinking fountains (BOD-only; walkable stroller amenity)
    fountains_wfs_url: Optional[str]
    fountains_layer: Optional[str]
    fountains_field_map: dict       # {"seasonal": "einschraenkungen", ...}

    # Parks + playgrounds
    green_wfs_url: Optional[str]
    parks_layer: Optional[str]
    playgrounds_layer: Optional[str]

    # Façade noise
    noise_wfs_url: Optional[str]
    noise_layer: Optional[str]
    noise_field_map: dict           # {"total_den": "ges_den", "road_night": "str_n", ...}
    noise_year: int                 # for provenance strings

    # Local-language glossary (post-processes LLM output; each city has its own
    # admin vocabulary — Berlin's "Kita/Träger/Situationsansatz" differs from
    # Hamburg's "Elbkinder/Kinderbetreuung"). Applied by core/gloss.py after
    # the inference service returns text. See phase3/server.py:GERMAN_GLOSS
    # for the Berlin seed set.
    bilingual_glossary: list        # [(compiled_regex, english_gloss), ...]

    # Bounds + attribution
    overpass_bbox: tuple            # sanity-check that input coord is in-city
    attribution: dict               # {"catchment": "...", "kitas": "...", "hospitals": "...", "fountains": "...", ...}
```

---

## 3. Migration ships

Ordered. Each ship ends with a runnable service and passes selfcheck.

### Ship A — FastAPI refactor, Berlin-only  (~3–4 days)

Goal: same behaviour, same UI, running under uvicorn. All hardcoded
Berlin values still live in code — but inside `app/cities/berlin.py`.
**Source of truth is `phase3/`**, not `phase2/` — phase3 is a strict
superset (adds hospitals, drinking fountains, votes, feedback, drag
reorder, reset, save-as-PNG). The LLM code carves out separately into
`inference/` (see Ship LLM-1); the app just POSTs to it.

Steps:
1. Scaffold `pyproject.toml`, `app/`, `web/`, `ops/Dockerfile.app`.
2. Move pure functions from `phase3/server.py` → `app/core/{geo,scorer,merge}.py` verbatim (haversine, noise tiers, stroller score, BOD/OSM dedupe).
3. Move WFS + Overpass helpers into `app/core/{wfs,overpass}.py`. Port the tiered mirror-rotation (`[25, 40, 75]s` per-mirror timeouts) from `phase3/server.py:overpass()`.
4. Port the `Index` class into startup wiring in `app/main.py` — load catchments, schools, kitas, **hospitals, drinking fountains** at boot.
5. Rewrite the routes as FastAPI endpoints in `app/routes/` returning the same JSON shapes: `/api/lookup`, `/api/amenities`, `/api/noise`, `/api/impression`, `/api/explain`. The two LLM routes delegate to the inference service via `httpx.AsyncClient` — see §7.
6. Port `app/core/gloss.py` from `phase3/server.py:GERMAN_GLOSS + _gloss_german()`. It reads `CityConfig.bilingual_glossary` and post-processes text returned from the inference service.
7. Serve `web/index.html` as a static file at `/`. Copy `phase3/index.html` verbatim — it includes the neumorphic hero/tabs/pills, impression modal, sad-feedback modal, explain modal, drag reorder (edu/amen/med/env), reset button, save-as-PNG.
8. Port `_selfcheck` into `app/selfcheck.py`, invoked with `python -m app.selfcheck`. Include the mirror-rotation self-test and the gloss regex asserts already living in `phase3/server.py`.
9. Write minimal `Dockerfile.app` (python:3.11-slim, install deps, `CMD ["uvicorn", "app.main:app", …]`). Model weights and `mlx-lm`/`llama.cpp` do **NOT** live here — they live in `inference/`.

Ship criterion: existing frontend + selfcheck both work against the new
service, byte-for-byte identical API responses to `phase3/`. `/api/impression`
and `/api/explain` return the same shape but delegate to the inference
service over HTTP (which is Ship LLM-1's responsibility to stand up).

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

### Ship C — Multi-city onboarding  (DEFERRED — see §Deferred)

Original goal: `CITY=hamburg` runs the same service against Hamburg data.

**Status (2026-08-07): deferred pending real demand.** Pre-flight investigation
against Hamburg + Munich surfaced that the `CityConfig` + `field_map`
abstraction handles NAME variation but not the MODEL variation every candidate
second city presents. Ship C as originally specified would require either
per-city `if slug == "hamburg"` branches leaking back into `core/` — undoing
Ship B — or a semantic "feature variant" primitive that we haven't designed.
Full pre-flight findings preserved in §Deferred so future-us doesn't repeat
the same investigation.

Re-entry path when demand arrives: **Path 3** (feature-variant primitive) →
per-city populate on top. Not the naive population attempt.

### Ship D — Production hardening  (~1–1.5 weeks)

Goal: safe to expose publicly.

Steps:
1. **Rate limiting** with `slowapi` (per-IP). Enforced at the app AND at the inference service (§7.5).
2. **Server-side Overpass response cache** keyed by `(rounded_lat, rounded_lon, category, radius)` — round lat/lon to ~200 m grid (3 decimals) so nearby addresses share cache hits. 24 h TTL (amenity data changes slowly). This is the real scalability win — turns "handles 1 rps" into "handles 100 rps" without hammering OSM. Uses the same cache adapter as (6). Mirror rotation from Ship A is the cold-cache path only.
3. **Structured logging** with `structlog` + request IDs; JSON output for log aggregators. Log inference `trace_id` alongside request ID for cross-service correlation (§7.3).
4. **Prometheus metrics** at `/metrics` (request count, latency histograms, cache hit/miss, WFS error rate, Overpass mirror-attempt distribution).
5. **Readiness probe** `/ready` returns 503 until the startup Index has loaded (catchments + schools + kitas + hospitals + fountains) so a slow-cold container doesn't take user traffic prematurely.
6. **Timeouts + retries** on every outbound WFS / Overpass call (already tiered per §Ship A step 3).
7. **Cache adapter** — abstract the in-memory dict behind an interface, add an optional Redis backend chosen by env-var `REDIS_URL`. Used by both the Overpass cache (step 2) and any future response caching.
8. **CORS** middleware with an allow-list from config.
9. **Turnstile / hCaptcha** on the front-end lookup form to keep the free path from being scraped.
10. **Vendor `html-to-image`** locally under `web/static/html-to-image.min.js` — the Save-as-PNG feature currently loads it from jsDelivr CDN, which adds a runtime dependency on an external network. Vendoring keeps prod deploys self-contained and works in air-gapped environments. Update the lazy loader in `index.html` to prefer the local copy with CDN as fallback.

Ship criterion: passes a basic load test (10 rps sustained, cache hit rate >80% after warm-up), rate-limits kick in above threshold, `/metrics` scrapes cleanly, WFS-timeout doesn't crash the process, Save-as-PNG works with no external network access.

### Ship E — Deployment infrastructure

Out of scope per project decision. Owner picks target platform (Cloud
Run / Fly.io / Hetzner + Docker / …) and wires up CI/CD separately.

---

## 4. What definitely does NOT change

- **Frontend UI = phase3 as shipped.** The neumorphic hero/tabs/pills, per-card vote buttons, sad-feedback chip modal, impression modal (with address chip, per-tab sections, Save-as-PNG, Regenerate), explain modal, per-tab drag reorder (edu/amen/med/env), Reset button in the hero — all copied verbatim into `web/index.html`. The only functional add on top of phase3 is reading city-name + attribution from `/api/config` so the same file serves Berlin/Hamburg/… without a rebuild.
- **Every algorithm** — `haversine`, `noise_tier`, `stroller_score`, `_merge_bod_and_osm`, tier thresholds, Overpass tiered mirror rotation, German-gloss regex post-processing. These are pure functions and port character-for-character into `core/`.
- **Selfcheck philosophy** — one runnable check per module, no framework required. `tests/` unit tests are additive, not replacement.
- **Ponytail conventions** (product doc §14). When Ship A lands, extend §14 with an §15 section covering microservice-specific conventions: FastAPI dependency-injection over global state, structlog for logging, `CityConfig` as the single source of city-specific truth, per-city glossary lives in `CityConfig.bilingual_glossary` not in the inference service, etc.
- **Attribution / provenance patterns** — every panel keeps its per-source stamp (BOD dl-de/by-2.0 or dl-de/zero-2.0 for city datasets, ODbL for OSM overlays, on-device model name for LLM output).
- **Client-side state model.** Votes, feedback chips, drag order, and compare list stay in `localStorage`. No server-side per-user storage in v1 (see §8).

---

## 5. Time estimate

| Ship | Effort |
|---|---|
| A. FastAPI refactor (Berlin-only, ports phase3) | 3–4 days |
| B. CityConfig extraction | 2 days |
| C. Hamburg onboarding | 1–2 weeks |
| D. Production hardening | 1–1.5 weeks |
| E. Deployment | out of scope |
| LLM-1 (parallel). Extract phase3 inference → shared service, switch to llama.cpp | 4–5 days |
| LLM-2 (parallel). Template library growth | on demand |
| LLM-3 (parallel). Inference metrics + possible GPU migration | 2–3 days |

**Total to "microservice + template + one additional city + shared inference on Linux live": ~4–5 weeks.**

Ship A is the biggest mental jump (routing rewrite + inference extraction).
Ship LLM-1's llama.cpp switch is the biggest risk — model-output parity
between mlx-lm and llama.cpp is asserted by re-running the phase3
selfchecks under both backends (see §7.1.1). Everything else is
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
  FastAPI + httpx). Model weights are ~1 GB (Qwen2.5-1.5B-Instruct Q4_K_M
  GGUF) and the `llama-cpp-python` runtime adds ~200 MB. Multiplying that
  across N city images is pure waste — every deploy pushes gigabytes to
  the registry.
- **Cold-start latency.** A city container that has to load a 1 GB model on
  boot is minutes to ready. A city container that just imports `httpx` and
  calls `http://inference:8080/summarize` is seconds to ready.
- **Model swap.** Switching from Qwen 1.5B → 3B, or trying a new prompt
  template, is one deploy of the inference service. No app-side rebuilds,
  no per-city coordination.
- **Cost.** RAM for the model (~1.5 GB resident with Q4_K_M) is paid once
  per node, not once per city instance per node.

### 7.1.1 Runtime: mlx-lm (dev) vs llama.cpp (prod)

Locked in §0 defaults; the mechanics live here.

- **Dev on Apple Silicon** uses `mlx-lm` because it is 5–10× faster than any
  CPU alternative on the same hardware and it is what `phase3/` already
  runs. It is **not** cross-platform — `mlx-lm` requires Apple's MLX
  framework and will not install on Linux.
- **Prod on Linux (x86_64 or ARM)** uses `llama-cpp-python` against a GGUF
  quantization of the same model. GGUF is the most portable Q4 format:
  same weights, runs on CPU or (optionally) GPU, no vendor lock-in. The
  model artefact for prod is `Qwen2.5-1.5B-Instruct-Q4_K_M.gguf`
  (~1.0 GB), obtainable from the model author's HF repo or built via
  `llama.cpp/convert-hf-to-gguf.py`.
- **Runtime abstraction.** `inference/runtime/` contains two backends
  behind a small interface (`generate(prompt, max_tokens, temp, ...)
  -> str`). The active backend is picked by env-var
  `INFERENCE_BACKEND=mlx|llama`, defaulting to `llama` in the prod image.
  Prompt templates, sampler settings, and post-processing are
  runtime-agnostic — they live above the `generate()` call.
- **Model file provisioning.** The GGUF file is baked into the prod
  inference image (immutable, reproducible builds). If image size becomes
  a pain, switch to mounting a shared read-only volume; keep the baked-in
  default until then.
- **Sampler parity check.** After the switch, the mlx-lm selfcheck for
  impression + explain output must be re-run under the llama.cpp backend
  and any regressions on the "anti-inversion" prompt (see phase3 few-shot)
  fixed before prod cutover. This is a required Ship LLM-1 exit criterion.

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

Single container, one endpoint. v1 supports two templates matching phase3
functionality; more get added as needed (see §7.5 for versioning policy).

```
POST /summarize
Body: {
  "template": "impression" | "explain",
  "context": { ... template-specific JSON grounded in rules-engine facts ... },
  "city":    "berlin" | "hamburg" | ...
}
Response: {
  "summary":  { <template-specific structured output> },
  "model":    "<model_id>",             // e.g. "Qwen2.5-1.5B-Instruct-Q4_K_M"
  "trace_id": "<uuid>"                  // for log correlation across services
}
```

**Prompt templates live in the inference service, not in the app**, so we
can iterate on wording without touching city code. The app sends *facts*;
the inference service composes the prompt from a template matched by
`template` name.

**Post-processing (glossary) lives in the app**, not in the inference
service — the app knows `CityConfig.bilingual_glossary` and applies it
via `core/gloss.py` after receiving text back. This keeps
inference-service pure (city-agnostic) and lets each city ship its own
admin vocabulary (Berlin's Kita/Träger/Situationsansatz vs Hamburg's
own set) without redeploying inference.

#### 7.3.1 `impression` template — context schema

Mirrors `phase3/server.py:summarize_impressions()`:

```json
{
  "address": "Kastanienallee 12, 10435 Prenzlauer Berg",
  "votes": {
    "<tab>": {
      "happy":       ["Playgrounds", "Parks"],
      "sad":         ["Supermarkets"],
      "sad_details": { "Supermarkets": "Too far, Discount-only, \"no Rewe nearby\"" }
    }
  }
}
```

Tabs are city-agnostic labels (`"amenities"`, `"medical"`, and any future
tab). `sad_details` is a per-category free-form string the app builds
from user chip + text feedback. The inference service branches on mode
(all-happy / all-sad / mixed) exactly as phase3 does, and MUST preserve
the anti-inversion behavior (a "no Kaufland nearby" complaint stays
"no Kaufland nearby", never becomes "one Kaufland nearby"). Response
`summary` is `{ "<tab>": "<one-paragraph read>" }`.

#### 7.3.2 `explain` template — context schema

Mirrors `phase3/server.py:explain_card()`:

```json
{
  "card_type": "edu-kita" | "amen-category" | "env-noise-den" | ...,
  "fields":    { <card-specific key/value pairs — see phase3 for exemplars> }
}
```

Response `summary` is `{ "explanation": "<two-or-three-sentence plain-English>" }`.
The app then runs `core/gloss.py` over `explanation` using the current
city's `bilingual_glossary` to inject English glosses for local admin
terms the model left untranslated.

### 7.4 Deployment shape

- **Sidecar in dev on Apple Silicon**: `docker compose up` runs one app +
  one inference container on the same host. Dev uses `INFERENCE_BACKEND=mlx`
  (Apple GPU acceleration). `INFERENCE_URL=http://inference:8080` in the app
  env. Zero-friction local dev.
  - Caveat: MLX inside Docker on macOS does not use the Apple GPU (Docker on
    Mac runs Linux). For fastest dev, run `python -m uvicorn inference.main:app`
    directly on the host and point compose's app at `host.docker.internal:8080`.
    Full-container mode falls back to CPU llama.cpp locally — still workable
    but 5–10× slower.
- **Prod on Linux (Kubernetes / Cloud Run / Fly / …)**: inference-service
  built from `ops/Dockerfile.inference` with `INFERENCE_BACKEND=llama` and
  the GGUF file baked in. Deployed as its own workload behind a
  ClusterIP / internal load balancer. City apps address it by DNS
  (`http://inference.default.svc.cluster.local` on k8s;
  private service URL elsewhere). Autoscale independently — inference is
  the CPU-hungry tier.
- **Hardware sizing (v1)**: CPU-only, ~1.5 GB RAM resident per inference
  replica for a 1.5B Q4 GGUF, 2 vCPU minimum for reasonable latency
  (~1–3 s/response). Scale horizontally (more replicas) before scaling
  vertically. Move to GPU only if the latency SLO tightens below 500 ms
  or throughput demands exceed CPU capacity — that's a Ship LLM-3 concern.
- **Model weights**: baked into the inference image (immutable, reproducible)
  in v1. If image push time becomes painful, switch to mounting a shared
  read-only volume. Keep baked-in until then.

### 7.5 Scaling knobs

| Concern | Knob |
|---|---|
| Latency under load | Horizontal replicas of inference-service (stateless once model is loaded). |
| Different model per city | Not supported by default. All cities share one model. If a city ever needs a bilingual variant, route by `city` param inside inference-service to a second model — but push back hard; per-city models kill the "one model, N cities" win. |
| Prompt experiments | v1 templates ship unversioned (`impression`, `explain`). When a breaking change lands, introduce a versioned sibling (`impression_v2`) and let city apps opt in when ready — old and new coexist until every city has migrated. YAGNI: don't add versioning suffixes on day one. |
| Rate limiting | At the inference service (per-city or per-IP), not at each app. One place to enforce. |

### 7.6 Failure modes

- **Inference service unreachable** → city app returns `503` on the LLM
  endpoint with a plain-English error. The rest of the app (lookup,
  amenities, noise) is completely unaffected — LLM is strictly additive.
- **Model timeout / OOM** → inference service returns a 504; city app
  surfaces a "summary unavailable, tap Retry" UX. Never block the map.
- **Cold model** → first request after boot pays the model-load cost
  (~5 s on MLX/dev, ~10–20 s on llama.cpp/prod CPU). Readiness probe
  (§Ship D) holds traffic until warm.
- **Un-glossed German terms in LLM output** → app-side `core/gloss.py`
  post-processing catches them via `CityConfig.bilingual_glossary`
  regex substitution. The glossary is the safety net; small models can't
  be relied on to translate consistently. Extend the glossary as new
  terms surface — this is a per-city ongoing maintenance job, not a
  code change.

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

1. **Ship LLM-1** — extract phase3 inference into a standalone service.
   - Move `phase3/server.py:summarize_impressions()`, `_build_impression_messages()`,
     `explain_card()`, and the sampler / logits-processor setup into
     `inference/main.py` and `inference/templates/{impression,explain}.py`.
     Prompt few-shots (including anti-inversion) come along verbatim.
   - `GERMAN_GLOSS` and `_gloss_german()` do **NOT** move here — they
     move into `app/core/gloss.py` and become per-city via
     `CityConfig.bilingual_glossary` (see §7.3, §7.6).
   - Stand up the two backends under `inference/runtime/` (§7.1.1):
     `mlx_backend.py` for dev, `llama_backend.py` for prod.
     `INFERENCE_BACKEND=mlx|llama` picks between them.
   - Publish `POST /summarize` per §7.3. `berlin-app` calls it via
     `INFERENCE_URL` env var.
   - **Exit criterion (required before prod cutover):** run the phase3
     selfcheck LLM asserts under both `INFERENCE_BACKEND=mlx` and
     `INFERENCE_BACKEND=llama`. Any regression on the anti-inversion
     prompt or the German-gloss safety net must be fixed before Ship D
     production launch.
2. **Ship LLM-2** — template library grows as product needs surface
   (`compare_verdict`, `viewing_checklist`, …). Each template is a small
   file in `inference/templates/`. Versioning added only when v2 exists
   (§7.5).
3. **Ship LLM-3** — Prometheus metrics on inference (tokens/s,
   time-to-first-token, backend in use, cache hit rate if prompt caching
   lands). Consider GPU migration here if CPU latency is the bottleneck.

---

## 8. Explicitly out of scope for v1

Locked "not going to build this in the initial deploy" list. Documenting
them here so a future implementer doesn't quietly reintroduce them.

- **Server-side vote / feedback storage ("Feature 2").** Aggregating
  user thumbs-down feedback across sessions to build sellable neighborhood
  insights was explored and dropped. Concerns: GDPR (address-linked
  opinions are personal data, need consent + DPA + retention policy),
  sample bias (opt-in feedback isn't defensible signal for buyers),
  buyer-fit uncertainty (Berlin's tenant-side market). Revisit only with
  a validated buyer conversation AND a legal review.
- **Compare-board sync across devices.** Compare list lives in
  `localStorage` per browser. Cross-device sync requires per-user identity
  (accounts, auth, DB). Out of scope for v1; note as a Ship E+ concern
  if user demand surfaces.
- **Per-user server-side impression cache.** Impression summary is cached
  in-memory on the client (`imprSummaryCache`), keyed by grouped-votes
  signature. Server-side cache would need per-user identity and adds no
  value at v1 traffic. Skip.
- **Third-party AI providers** (OpenAI, Anthropic, Groq, …). Locked out
  in §0. Revisit only with an explicit written GDPR / DPIA review.
- **Server-side scraping of listings.** Locked out in product doc §7.
  Never appears here as a shortcut.
- **Per-city LLM models.** §7.5 — all cities share one model; per-city
  glossary handles admin-vocabulary differences post-generation.
- **Progressive delivery of amenities (SSE / streaming).** Nice-to-have
  perceived-latency win, real scalability win is server-side Overpass
  caching (Ship D step 2). Defer until caching lands and metrics show
  it's still needed.
- **Turnstile / hCaptcha on any endpoint other than `/api/lookup`.**
  Only the lookup form is a scrape target for the free path. Amenity /
  noise / impression endpoints are downstream of a solved captcha.

---

## 9. Adding a new city — populate checklist

Use this once Ship B has landed and `berlin.py` exists as the worked
example. Sequenced so each step ends verifiable before the next depends
on it — do not stack unverified field groups.

§6's table shows the *effort estimate* per city; this section is the
actual step-by-step.

### 9.1 Pre-flight (before writing any code)

- [ ] Identify the city's open-data portal. Berlin: `daten.berlin.de` +
      `fbinter.stadt-berlin.de` (Geoportal WFS). Hamburg:
      `geoportal-hamburg.de/geo-online/`. Munich: `geoportal.bayern.de` +
      `opendata.muenchen.de`. Each Bundesland has its own Geoportal
      structure.
- [ ] Confirm the data licence is `dl-de/by-2.0`, `dl-de/zero-2.0`,
      `CC-BY-4.0`, or `CC0`. Anything more restrictive (custom licence,
      non-commercial only) — stop and consult product doc §Legal before
      proceeding.
- [ ] **Check catchment (Schul-Einzugsgebiet) availability first** —
      this is the flagship feature. Berlin publishes `schulen_esb`;
      Hamburg calls theirs `grundschul_einzugsgebiete`. Frankfurt / Hesse
      does NOT publish catchment polygons openly (see §6). If the target
      city doesn't publish catchments, decide upfront whether to onboard
      with a reduced feature set or drop the city — do not discover this
      halfway through.
- [ ] Locate WFS endpoint URLs for every dataset the city has. Typical
      pattern: `https://geodienste.<city>.de/services/wfs_<layer>?SERVICE=WFS`
      or `https://<geoportal-host>/wss/service/<layer_id>/guest`.
- [ ] Smoke-test each WFS endpoint with a raw `GetCapabilities`:
      ```
      curl 'https://<wfs-url>?SERVICE=WFS&REQUEST=GetCapabilities' | head -80
      ```
      Confirm HTTP 200 and the expected layer name appears in
      `<FeatureType><Name>`. If the endpoint requires auth or returns
      `AccessConstraints`, resolve before continuing.
- [ ] Estimate onboarding effort against §6's table. If the number
      surprises you (much longer, much shorter) — flag before starting.

### 9.2 Populate `app/cities/<slug>.py` — field-by-field

Copy `berlin.py` → `<slug>.py`. Work top-to-bottom through each group.
**After each group, run the corresponding §9.3 verification before
moving on.** Do not batch six unverified field groups and then debug
which is broken.

**Basic identity**
- [ ] `slug`, `display_name`, `default_center` (lat, lon of city hall
      or geographic centre — used for the map's initial view).

**Address geocoding**
- [ ] `geocoder`: `"wfs"` for cities with an address WFS,
      `"nominatim"` as fallback (rate-limited public service; not
      recommended for prod scale).
- [ ] `geocoder_wfs_url`, `geocoder_layer`.
- [ ] `geocoder_field_map`: fetch one feature (`GetFeature` with
      `count=1`) and map the real property names to canonical keys:
      ```
      curl '<wfs>?...&REQUEST=GetFeature&typeName=<layer>&outputFormat=application/json&count=1' | jq '.features[0].properties'
      ```
      Berlin uses `str_name`, `hnr`, `plz`. Hamburg uses different.

**Catchments (Schul-Einzugsgebiet)**
- [ ] `catchment_wfs_url`, `catchment_layer`.
- [ ] `catchment_field_map`: sample one feature. Expect a polygon-id
      field (`esb` in Berlin) and a district name field (`bezname`).
- [ ] Confirm geometry type is resolvable by shapely — inspect one
      feature's `geometry.type`; expect `MultiPolygon` or `Polygon`.
      GML-only WFS endpoints without GeoJSON output need an extra
      converter step; escalate if you hit that.

**Schools**
- [ ] `schools_wfs_url`, `schools_layer`, `schools_field_map`.
- [ ] `schools_public_value`: the exact string in the operator/carrier
      field that means "public school". Berlin: `"öffentlich"`.
      Hamburg: `"staatlich"`. Sample the field, don't guess.
- [ ] `schools_primary_types`: `frozenset` of school-type values that
      count as Grundschule (primary). Berlin: `frozenset({"Grundschule"})`.
      Some Bundesländer lump primary + lower-secondary as
      "Gemeinschaftsschule" — read the state's school-type taxonomy.

**Bilingual programme**
- [ ] Berlin's SESB (Staatliche Europa-Schule Berlin) is a curated
      substring list because the WFS doesn't carry an SESB attribute
      (see `phase3/server.py:SESB_GRUNDSCHULEN`). Every city needs its
      equivalent, typically from the state education ministry's
      bilingual-schools page.
- [ ] Populate `bilingual_schools: {name_substring_lower: strand_label}`.
      Substring match is intentional — school names in WFS often
      contain typos or additional descriptors vs. the ministry list.

**Kitas**
- [ ] `kita_wfs_url`, `kita_layer`, `kita_field_map`.
- [ ] Sample one Kita feature to translate operator-type
      (`t_art` in Berlin), pedagogical approach (`ang_1`), capacity
      (`e_platz`). Field names vary wildly.
- [ ] Sanity check: city-wide count should be close to the publicly
      reported number of registered daycares (Berlin: ~2900).

**Hospitals**
- [ ] `hospital_wfs_url`, `hospital_layer`, `hospital_field_map`.
- [ ] `hospital_radius_m`: Berlin uses 2000 m (walkable/short transit).
      Adjust for city density — a spread-out city may need 3000+.

**Drinking fountains**
- [ ] Optional. Not every city runs a public-fountain programme; some
      publish under the water utility, some under parks-and-recreation.
      If none exists, leave `fountains_wfs_url = None`; the app hides
      the card automatically.

**Parks + playgrounds**
- [ ] `green_wfs_url`, `parks_layer`, `playgrounds_layer`.
- [ ] Some cities combine parks + playgrounds under one dataset with a
      type field; some split them into two layers. Sample first.

**Façade noise (Strategische Lärmkarten)**
- [ ] EU Environmental Noise Directive requires every EU city > 100k
      population to publish strategic noise maps on a 5-year cycle.
      Latest round: 2022. Confirm the city's data is from that round.
- [ ] `noise_field_map` varies wildly across cities. Berlin's
      `L_DEN_TOTAL` might be `ges_den`, `laerm_gesamt`, `dblden`
      elsewhere. Sample.
- [ ] `noise_year`: reference year for provenance string.

**Bilingual glossary** (rationale in §7.6)
- [ ] Seed with terms that appear in the city's own datasets: Kita
      operator types (`Träger`, `Eigenbetrieb`), pedagogical approaches
      (`Situationsansatz`), school-type abbreviations, transit-system
      names, common Behörde names.
- [ ] Berlin seed is `phase3/server.py:GERMAN_GLOSS`. Copy the
      universally-German entries (`Kita`, `Grundschule`, `Träger`,
      `Eigenbetrieb`) into every city; add city-specific ones on top
      (Berlin: `SESB`, `Situationsansatz`; Hamburg: `Elbkinder`,
      `HmbSchulG`; Munich: `Kinderhaus`, `Hort`).
- [ ] Extend the glossary over time as new terms surface in LLM output.
      Ongoing maintenance job — treat like a dictionary, not a one-shot
      config.

**Overpass bbox**
- [ ] `(south, west, north, east)` covering the whole city plus a
      small margin (~0.02°). Used to reject out-of-city coords before
      hitting Overpass. Berlin: roughly `(52.33, 13.08, 52.68, 13.76)`.
      Get from the city's WFS boundary layer or OSM `relation` for the
      city.

**Attribution**
- [ ] One entry per dataset, per licence terms. `dl-de/by-2.0`
      REQUIRES attribution; `dl-de/zero-2.0` and CC0 do not, but
      include one anyway for user-facing provenance clarity.
- [ ] Format: `"<Portal name> / <Layer human name> (<licence>)"` —
      matches phase3 pattern. Example: `"Geoportal Hamburg /
      Grundschul-Einzugsgebiete (dl-de/by-2.0)"`.

### 9.3 Per-group verification

Before moving to the next field group, prove the current group works
end-to-end via the selfcheck harness:

```
CITY=<slug> python -m app.selfcheck --only <group>
```

Where `<group>` is one of `geocoder | catchment | schools | kitas |
hospitals | fountains | green | noise | glossary`. Each check queries
the WFS, parses a known feature, and asserts the field map produces the
expected canonical shape. Failure = fix `<slug>.py` before continuing.

For manual sanity, pick three real addresses in the city (inner-city,
suburb, near-boundary) and run:

```
CITY=<slug> curl 'http://localhost:8000/api/lookup?address=<addr>' | jq .
```

Confirm catchment, assigned school, kita count all look plausible.
Repeat for `/api/amenities` and `/api/noise`.

### 9.4 Frontend + inference wiring

- [ ] Add the city to the landing-page selector OR set up the
      subdomain (`<slug>.addrlens.de` → app instance with `CITY=<slug>`).
      Per §0, one-instance-per-city is the locked deployment shape.
- [ ] Load `http://localhost:8000/api/config` and confirm
      `display_name`, `default_center`, and every attribution string
      appear correctly in the UI footer + panel provenance stamps.
- [ ] Test one `/api/impression` and one `/api/explain` call end-to-end
      with a city address and faked votes. Confirm:
      - Inference-service reachable (no timeout / 503).
      - Glossary post-processing catches any un-glossed local terms —
        if you see raw German in the output, extend `bilingual_glossary`
        and re-test.
      - Berlin-culture leaks (Kiez, S-Bahn) in output for non-Berlin
        cities are ACCEPTABLE per §0 (English-expat audience). Do not
        gate onboarding on prompt customization.

### 9.5 Selfcheck matrix + CI

- [ ] Add `<slug>` to the CI selfcheck matrix so every PR runs
      assertions under every configured city, not just Berlin.
- [ ] Add one known-good address per city to `tests/test_selfcheck_live.py`.
      Use a well-known address (city hall, main station) that's unlikely
      to disappear.

### 9.6 Go-live gate

Do not point real traffic at a new city until every one of these is
green. Miss one, wait — this is the cost of getting production wrong.

- [ ] All §9.3 group checks pass under `CITY=<slug>`.
- [ ] `/health` returns 200 and `/ready` returns 200 within 30 s of
      cold start (Index loaded).
- [ ] `/api/impression` and `/api/explain` return without
      inference-service errors on a test address with faked votes.
      Retry after a cold-model reload (~10–20 s on prod llama.cpp) to
      confirm the readiness probe works.
- [ ] Attribution strings render on the frontend for every panel that
      uses the new city's data. Legal requirement for `dl-de/by-2.0`
      datasets.
- [ ] A native-language spot-check: 5 impression outputs for the new
      city, read by a native speaker, no factual howlers. The
      **anti-inversion guarantee is per-city** — verify that a "no X
      nearby" complaint stays "no X nearby" and doesn't get flipped to
      "one X nearby" in this city's output. Regression here means the
      Ship LLM-1 few-shots need city-specific reinforcement.
- [ ] Rate-limit + `/metrics` scrape verified on the new city instance
      (all Ship D concerns apply per-city).

---

*How to use this file:* when starting Ship A, work top-down through §3.
Update §0 (confirmed defaults) if any is changed mid-flight. Move any
ship into a `Shipped` section at the bottom when it lands, with commit
hash + date. Keep this document alive.

---

## Shipped

- **Ship A** (FastAPI refactor, Berlin-only) — landed **2026-08-07**, `da412f9`.
  Same behaviour as `phase3/` under uvicorn; every algorithm ported
  character-for-character; frontend copied verbatim.
- **Ship LLM-1** (inference-service extraction) — landed **2026-08-07**, `da412f9`.
  `POST /summarize` per §7.3; `mlx_backend` + `llama_backend` behind runtime
  interface; impression + explain templates carry phase3 anti-inversion
  few-shots verbatim.
- **Ship B** (CityConfig extraction) — landed **2026-08-07**, `da412f9`.
  No Berlin constants remain in `core/`; `CITY=berlin` reproduces Ship A
  behaviour byte-for-byte; `/api/config` powers the frontend's per-city
  strings. Follow-up (`wfs_output_format` on CityConfig + `run_cities_isolation`
  selfcheck) landed in a hardening commit alongside the Path 1 decision.

## Deferred

### Ship C — Multi-city onboarding (deferred **2026-08-07**)

**Decision: Path 1 (single-city v1).** Ship Berlin publicly; defer multi-city
work until real demand ("waitlist for city X" signal from users) surfaces.

Rationale: Berlin's Geoportal is the exception among German open-data
publishers, not the rule. Every candidate second city investigated (Hamburg,
Munich) surfaced not just field-NAME variation — which `CityConfig.field_map`
handles cleanly — but semantic MODEL variation that the current abstraction
cannot express without either bleeding `if slug == "X"` branches back into
`core/` (undoing Ship B) or growing an unplanned "feature variant" primitive
under time pressure. The right sequence when demand arrives is Path 3
(design the feature-variant primitive first, then onboard cities on top),
not the naive Path 2 (Hamburg first, refactor under fire later).

**Investigation findings preserved so future-us doesn't repeat this work:**

#### Hamburg (`geodienste.hamburg.de`)

- **Licence:** dl-de/by-2.0 across every dataset probed. Consistent.
- **Output format quirk:** server accepts only `application/geo+json`
  (Berlin's `application/json` is rejected). Handled by `wfs_output_format`
  on `CityConfig` (added 2026-08-07).
- **Catchment (flagship): DATA-MODEL MISMATCH.**
  `HH_WFS_Regionaler_Bildungsatlas_Einzugsgebiete_Schulwahl`, layer
  `de.hh.up:einzug_einzugsgebiete_primarstufe` — geometry is `null` on
  every feature. Layer publishes a tabular enrollment table
  `(school_id, statgeb_id, count, %)`, not polygons. Berlin's
  point-in-catchment-polygon lookup is not reproducible; the honest
  Hamburg feature is "schools kids in your statistical area actually
  attend" (via `HH_WFS_Statistische_Gebiete` polygons + join), which is
  a semantically different card requiring per-city prompt + UI variance.
- **Schools:** `HH_WFS_Schulen`, layers `de.hh.up:staatliche_schulen`
  (public — `rechtsform=staatlich`) + `de.hh.up:nicht_staatliche_schulen`
  (private). Two-layer split (vs Berlin's one layer + `traeger` field).
  Address fields are pre-combined (`adresse_strasse_hausnr`,
  `adresse_ort`), not split.
- **Kitas:** `HH_WFS_KitaEinrichtung`, layer `app:KitaEinrichtungen`.
  Split address (`Strasse`/`Hausnr`/`PLZ`/`Ort`), no capacity field
  (Berlin's `e_platz` has no analogue). `Traeger` is verbose free-text
  (e.g. "Kirchengemeindeverband…") — use `Spitzenverband` (short umbrella
  org) if a category label is needed for `_kita_info`.
- **Addresses / geocoder: DATA-MODEL MISMATCH.**
  Only `HH_WFS_INSPIRE_Adressen` (INSPIRE model, GML only) and
  `HH_WFS_DOG` (Hamburg gazetteer, also GML only) — neither supports
  GeoJSON. `Index.geocode()`'s CQL-filter-on-flat-fields approach doesn't
  work. Options are (a) implement GML XML parser (~50 LOC), (b) fall back
  to Nominatim (rate-limited public service).
- **Noise: DATA-MODEL MISMATCH.**
  Per-source raster grids only (road / rail / air × Tag-Abend-Nacht /
  Nacht) — no façade-total-dB layer analogous to Berlin's
  `aa_fp_gesamt2022`. WFS is not live — only downloadable 140 MB GML or
  WMS `HH_WMS_Strassenverkehr`. Options are (a) road-only from an
  archived GML preload, (b) WMS `GetFeatureInfo` per request (brittle
  HTML), (c) skip.

#### Munich / Bavaria

- **Sprengel (flagship): OPENLY UNAVAILABLE.**
  Only exposed via `risby.bayern.de/RisGate/servlet/Schulsprengel` — a
  proprietary Bavarian RIS WMS servlet that does not answer standard
  OGC `GetCapabilities` (returns `ServiceException` regardless of
  version). Viewable only inside BayernAtlas. No WFS. No bulk file
  download openly published on `geodaten.bayern.de/opengeodata/`.
  Ruled out by the project's "no scraping" architectural rule.
- **Munich GeoServer** (`geoportal.muenchen.de/geoserver/gsm_wfs`)
  publishes 22 layers total — all administrative boundaries, waste
  management, and category-lookup layers. None education, Kita,
  hospital, noise, or park.
- **opendata.muenchen.de:** schools data is CSV only, tabular; no
  geometry, no WFS.
- **Verdict:** Munich is worse than Hamburg for our architecture.
  Do not attempt as a second city without a fundamental strategy shift.

#### Köln (NRW) — partial

- Not fully investigated. Initial signal from `offenedaten-koeln.de`
  suggests Address WFS exists and the municipal-area classification
  publishes polygon services. Schulbezirk polygon availability was not
  verified — flag as "worth a full pre-flight when NRW cities move up
  the demand queue."

### Re-entry path when demand arrives

**Path 3, then onboard.** Design and land the "feature-variant primitive"
on top of `CityConfig` before adding a city:

- `catchment_strategy: PolygonAssignedSchool | StatAreaAttendanceShare | Unsupported`
- `noise_strategy: FassadenpegelGesamt | PerSourceRoadOnly | Unsupported`
- `geocoder_strategy: WfsFlatGeoJson | WfsInspireGml | Nominatim`

Berlin picks its trio and behaves identically to today. Hamburg picks a
different trio. Munich picks `Unsupported / Unsupported / Nominatim` — the
UI already handles "not available in this city" panels cleanly, and users
still get amenities + inference-service impression + the map. Each
strategy is a small implementation in `core/` behind an interface.

Estimate: ~1–2 weeks for the primitive + Berlin migration, then ~3 days
per city onboarding.
