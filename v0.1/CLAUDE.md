# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

Production tree for the Berlin Family Address Intelligence product. Two FastAPI services:

- **`app/`** — per-city web service. One image, one instance per city, selected by `CITY` env var at boot. Serves the static SPA in `web/` and JSON endpoints under `/api/*`.
- **`inference/`** — shared LLM service. One image, all cities. `POST /summarize` with a template name and structured context; returns paraphrased prose over rules-engine facts.

Historical prototypes (`phase0/`, `phase1/`, `phase2/`, `phase3/`) live in the parent repo alongside this tree; they are frozen reference artefacts. `phase3/` is the direct behavioural ancestor of `app/` — many core modules are byte-for-byte ports and their selfchecks preserve that parity.

Governing plan: `../microservice-refactor-plan.md` (Ship A, LLM-1, B are shipped; Ship C deferred; Ship D in progress). Engineering conventions: §14 of `../berlin-family-address-intelligence-product-doc.md` — read those before adding features.

## Commands

Environment (root of this dir, `micro-service/`):

```bash
uv pip install --system -r pyproject.toml            # app deps
uv pip install --system -e "inference[dev]"          # inference on Apple Silicon (mlx-lm)
uv pip install --system -e "inference[prod]"         # inference on Linux (llama-cpp-python + GGUF)
```

Run locally (two processes; the inference process is slow to boot, do not restart it needlessly — see memory `feedback_leave_dev_server_running`):

```bash
CITY=berlin INFERENCE_URL=http://localhost:8080 uvicorn app.main:app --port 8001
INFERENCE_BACKEND=mlx uvicorn inference.main:app --port 8080
```

Docker compose brings up both, but on macOS MLX inside Docker does **not** use the Apple GPU — for fast dev, run `inference` on the host and `app` however you like.

**Restart discipline (cold start is 5–15 s — don't kill needlessly):**

- **Backend Python edits (`app/**/*.py`)** — the running uvicorn holds stale bytecode until restart. Kill and re-run:
  ```bash
  pkill -f "uvicorn app.main"
  CITY=berlin INFERENCE_URL=http://localhost:8080 .venv/bin/uvicorn app.main:app --port 8000
  ```
  If a curl against `/api/lookup` returns errors that don't match the current code (or a `lens.young_family.error` you already removed), that's the stale-bytecode symptom — restart.
- **Frontend edits (`web/index.html`, `web/static/*.css|*.js`)** — no restart needed; `StaticFiles` serves them from disk each request. Hard-refresh the browser (⌘⇧R).
- **Selfchecks (`python -m app.selfcheck`, `python -m app.core.<module>`)** — always fresh; they run as subprocesses and don't touch the live server.
- **Docs, plans, git ops** — never restart.

For heavy backend-refactor sessions where the ~10 s Index rebuild per save is worth it, launch with `--reload`:
```bash
CITY=berlin uvicorn app.main:app --port 8000 --reload
```
Otherwise leave `--reload` off — memory `feedback_leave_dev_server_running` captures the "cold start is slow, don't churn it" rule.

Selfchecks (there is no pytest suite — every module has a `__main__` pure-assert block and each service has a `selfcheck.py` orchestrator):

```bash
python -m app.selfcheck            # cities isolation + pure module blocks + live WFS asserts (needs network)
python -m inference.selfcheck      # pure prompt-shape asserts + live model load + one gen per template
python -m app.core.<module>        # run a single module's pure selfcheck (fast, no network)
```

Refresh vendored VBB S/U-Bahn coords (annual):

```bash
python -m scripts.refresh_vbb
python -m scripts.refresh_vbb --find "<station name>"     # look up coords for regional-rail curation
```

## Architecture

**City selection is at boot, not at request time.** `CITY=<slug>` selects `app/cities/<slug>.py`, whose module-level `<SLUG>` constant is a `CityConfig` dataclass instance. Nothing in `app/core/` reads city-specific constants; every function takes a `CityConfig` argument. The dataclass is `frozen` with no defaults — a missing field fails fast at import. Adding a city = adding one file in `app/cities/`. Cross-city bugs are impossible by construction (per-process deployment); `app.selfcheck.run_cities_isolation` boots each city module in a fresh subprocess to guard the promise.

**`Index` is the in-memory data plane.** Built once at boot (`app.main.lifespan`) via blocking WFS calls (~5–15 s cold start, dominated by the city Geoportal). All read paths are pure lookups against shapely trees and lists — only address geocoding stays live-WFS. Small point layers (schools, kitas, hospitals, fountains, fire stations, S/U/Tram, quiet zones, protection zones, pools) are preloaded; large layers (street trees ~435k, façade noise, Umweltatlas air/heat) are per-request bbox queries cached by rounded `(lon, lat, radius)` in module-level dicts under a threading lock. See `app/core/wfs.py` and the caching rules in product-doc §14.6.

**Routes → `Index` via FastAPI Depends.** `app/deps.py` exposes `get_index` / `get_city` reading `request.app.state`. Do not introduce module-level globals for these. Routes:

- `/api/lookup` — the big one: geocode → catchment → assigned schools → intl school → kitas → connectivity → fire, quiet, protection, swim, trees, air, heat. Aggregating endpoint; per-category failure is tolerated behind the `_error` pattern.
- `/api/amenities`, `/api/noise`, `/api/config` — supporting reads.
- `/api/history` — proxy to inference `history` template; renders one-paragraph OSM Stolperstein narrative for the ~100 m grid cell.
- `/api/card_insight` — dispatcher for per-tile Get Insight (Life Lens tile modals). Shapes tile context per card_key and forwards to inference `<card_key>_insight` template. Applies `CityConfig.bilingual_glossary` via `app/core/gloss.py` after the model returns.
- `/api/lens_insight` — per-lens executive-summary AI panel (`?ai=lens` pilot). Fan-in reduce: one Cloudflare call per lens per address, replaces the per-tile fan-out. Cache-versioned so template edits invalidate stale entries.

**Inference service is city-agnostic.** `POST /summarize` takes `{template, context, city}`; `city` is accepted but not routed on today. Backend picked by `INFERENCE_BACKEND=mlx|llama`; model loads in a background thread so uvicorn binds fast; `/ready` returns 503 until warm; `_lock` serialises generation because mlx/llama are not thread-safe. Never bake the model into per-city app images (plan §7.1). Templates in `inference/templates/` are versioned prompt builders whose pure selfchecks assert prompt shape and anti-inversion behaviour on negative-mode inputs — do not weaken those asserts.

**Provenance is not optional.** Every JSON response includes a top-level `provenance` map keyed by dataset; every `CityConfig.attribution` entry carries the full open-data licence tag. The frontend footer concatenates from that map.

**Two health signals, not one.** `/health` is pure liveness (process up = 200). `/ready` is readiness — 200 only after `Index` is loaded; 503 otherwise. In the inference service, `/ready` is 503 until the backend thread finishes. Any orchestrator should gate user traffic on `/ready`, not `/health`.

## Conventions particular to this tree

- **Stdlib + shapely + FastAPI + httpx only in `app/`.** No ORM, no build step, no bundler. The SPA is `web/index.html` + `web/static/` served by `StaticFiles`; `html-to-image.min.js` is vendored on purpose.
- **`ponytail:` comments mark deliberate simplifications** with a named ceiling and upgrade path. Do not strip them; address one only with a real reason (a bug, a metric, a user complaint).
- **BOD first, OSM as fallback/supplement.** Every feature carries `source: "bod" | "osm"`. Dedupe follows the `_merge_bod_and_osm` centroid pattern from phase2.
- **Behavioural parity with `phase3/server.py` is a hard constraint** for modules ported in Ships A/B. If you touch `app/core/*` or a route, check the corresponding phase3 function and preserve response shape unless the plan explicitly authorises a change.
- **Live-browser QA before shipping a UI change.** Type checks + selfchecks verify code correctness, not feature correctness.
- **CORS is opt-in via `CORS_ORIGINS` env** (comma-separated, no wildcards). Empty = same-origin only, which is what the packaged SPA needs.
