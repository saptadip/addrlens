"""Shared LLM inference service (Ship LLM-1). One image, all cities.

Plan §7.3 contract:
  POST /summarize
    { "template": "impression" | "explain", "context": {...}, "city": "berlin" }
  ->
    { "summary": {...}, "model": "<model_id>", "trace_id": "<uuid>" }

Backend picked by env-var INFERENCE_BACKEND (mlx | llama). MLX loads on
Apple Silicon dev; llama.cpp loads on Linux prod (GGUF file baked into
ops/Dockerfile.inference).

Loading is async — the model boots in a background thread so the HTTP
server binds fast and `/health` responds immediately. `/summarize` returns
503 until the model is warm (plan §7.6). Ship D's `/ready` in the app
service polls this.

Concurrency: both backends are single-threaded (mlx/llama are not
thread-safe), so a process-wide lock serialises calls. If throughput
becomes an issue, run multiple replicas — batching would be a much bigger
rewrite (plan §7.5).

Event loop safety (Ship D stability pass):
- Both branches of /summarize dispatch the blocking `run(...)` call into
  `asyncio.to_thread` so uvicorn's event loop never blocks on a slow
  generation. Previously a wedged local decode would pin /health,
  /ready, and every other endpoint until the model finished.
- Every dispatch is wrapped in
  `asyncio.wait_for(..., INFERENCE_GENERATION_TIMEOUT_S)`. On local we
  return 504; on remote we log + fall through to local so a wedged
  Cloudflare edge doesn't take down /summarize.
- Remote backend init moved out of the loader thread into `lifespan` so
  remote-eligible templates are servable at t=0 without waiting for the
  (5–15 s) local model load.

Env vars this file reads:
- `INFERENCE_BACKEND`               local backend selector (mlx | llama)
- `INFERENCE_MODEL_ID`              optional model-id override
- `INFERENCE_REMOTE_TEMPLATES`      comma-separated allow-list for the
                                    Cloudflare Workers AI backend
- `INFERENCE_GENERATION_TIMEOUT_S`  server-side wall-clock cap on one
                                    /summarize dispatch (default 120.0,
                                    floor 1.0). Distinct from the app
                                    service's `INFERENCE_TIMEOUT_S`
                                    which is the client-side HTTP
                                    timeout — these two knobs are
                                    deliberately separate names.
- `CF_ACCOUNT_ID`, `CF_WORKERS_AI_TOKEN`, `CF_MODEL_ID`
                                    Cloudflare Workers AI wiring (read
                                    by `cloudflare_backend.backend_from_env`)
- `SENTRY_DSN_INFERENCE`, `SENTRY_ENV`, `GIT_SHA`
                                    optional error tracking
"""
from __future__ import annotations

import asyncio
import os
import sys
import threading
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request

from inference.templates import air_insight as air_insight_tpl
from inference.templates import buergeramt_insight as buergeramt_insight_tpl
from inference.templates import coworking_insight as coworking_insight_tpl
from inference.templates import english_clinic_insight as english_clinic_insight_tpl
from inference.templates import explain as explain_tpl
from inference.templates import gesix_insight as gesix_insight_tpl
from inference.templates import gesix_newcomer_insight as gesix_newcomer_insight_tpl
from inference.templates import heat_insight as heat_insight_tpl
from inference.templates import history as history_tpl
from inference.templates import impression as impression_tpl
from inference.templates import intl_food_insight as intl_food_insight_tpl
from inference.templates import kita_insight as kita_insight_tpl
from inference.templates import language_school_insight as language_school_insight_tpl
from inference.templates import lens_newcomer_insight as lens_newcomer_insight_tpl
from inference.templates import library_insight as library_insight_tpl
from inference.templates import noise_insight as noise_insight_tpl
from inference.templates import packstation_insight as packstation_insight_tpl
from inference.templates import pediatrician_insight as pediatrician_insight_tpl
from inference.templates import playground_insight as playground_insight_tpl
from inference.templates import refuge_insight as refuge_insight_tpl
from inference.templates import supermarket_insight as supermarket_insight_tpl
from inference.templates import transit_insight as transit_insight_tpl
from inference.templates import rail_transit_insight as rail_transit_insight_tpl
from inference.templates import tram_transit_insight as tram_transit_insight_tpl
from inference.templates import bus_transit_insight  as bus_transit_insight_tpl
from inference.templates import wochenmarkt_insight as wochenmarkt_insight_tpl
# Quiet Living lens templates
from inference.templates import quiet_zone_insight as quiet_zone_insight_tpl
from inference.templates import street_trees_insight as street_trees_insight_tpl
from inference.templates import tempo30_insight as tempo30_insight_tpl
from inference.templates import arterial_road_insight as arterial_road_insight_tpl
from inference.templates import rail_noise_insight as rail_noise_insight_tpl
from inference.templates import nightlife_inverted_insight as nightlife_inverted_insight_tpl
from inference.templates import gesix_quiet_insight as gesix_quiet_insight_tpl
# Commuter lens templates
from inference.templates import commuter_rail_transit_insight as commuter_rail_transit_insight_tpl
from inference.templates import commuter_tram_transit_insight as commuter_tram_transit_insight_tpl
from inference.templates import commuter_bus_transit_insight as commuter_bus_transit_insight_tpl
from inference.templates import regional_rail_reach_insight as regional_rail_reach_insight_tpl
from inference.templates import cycling_network_insight as cycling_network_insight_tpl
from inference.templates import car_sharing_reach_insight as car_sharing_reach_insight_tpl
from inference.templates import ev_charging_reach_insight as ev_charging_reach_insight_tpl
from inference.templates import airport_reach_insight as airport_reach_insight_tpl
from inference.templates import gesix_commuter_insight as gesix_commuter_insight_tpl

# ---------- Sentry (production error tracking) ----------
# Env-guarded. Local dev (Apple Silicon, INFERENCE_BACKEND=mlx) leaves the DSN
# unset, so this is a no-op and sentry_sdk is never imported.
#
# GDPR notes: same posture as the app service. send_default_pii=False by
# choice, and the before_send scrubber redacts any prompt/context payload
# that could carry a user's searched address into an exception event. The
# inference service should be provisioned in Sentry's EU region so data
# stays in Frankfurt.
if os.environ.get("SENTRY_DSN_INFERENCE"):
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.starlette import StarletteIntegration

    def _sentry_scrub(event, _hint):
        req = event.get("request") or {}
        # /summarize is a POST — the entire request body could carry the
        # user's address inside the `context` field. Redact wholesale rather
        # than trying to walk arbitrary template payloads.
        if "data" in req:
            req["data"] = "[REDACTED]"
        return event

    sentry_sdk.init(
        dsn=os.environ["SENTRY_DSN_INFERENCE"],
        integrations=[StarletteIntegration(), FastApiIntegration()],
        traces_sample_rate=0.1,
        environment=os.environ.get("SENTRY_ENV", "production"),
        release=os.environ.get("GIT_SHA") or None,
        send_default_pii=False,
        before_send=_sentry_scrub,
    )

# ---------------------------------------------------------------------- config

BACKEND_NAME = os.environ.get("INFERENCE_BACKEND", "mlx")   # mlx | llama
MODEL_ID     = os.environ.get("INFERENCE_MODEL_ID")         # optional override


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


# Wall-clock cap on a single /summarize call. Wraps the (blocking) local
# generation AND the (blocking, but shorter) remote call. If exceeded on
# local we return 504; on remote we log + fall through to local.
#
# Named distinctly from the app service's `INFERENCE_TIMEOUT_S` (which is
# the client-side httpx timeout, default 45 s). Sharing one env-var name
# across two processes led to silent cross-talk in shared compose files —
# setting one meaning would change the other unexpectedly.
INFERENCE_GENERATION_TIMEOUT_S = max(1.0, _env_float(
    "INFERENCE_GENERATION_TIMEOUT_S", 120.0))

# Remote-inference routing.
# `INFERENCE_REMOTE_TEMPLATES` is a comma-separated allow-list of template
# names that will be served by the remote backend (Cloudflare Workers AI)
# when CF_ACCOUNT_ID and CF_WORKERS_AI_TOKEN are set. Any other template
# stays on the local backend. Any remote failure falls through to local.
REMOTE_TEMPLATES = {
    t.strip()
    for t in os.environ.get("INFERENCE_REMOTE_TEMPLATES", "history,lens_newcomer_insight").split(",")
    if t.strip()
}

TEMPLATES = {
    "impression":     impression_tpl.run,
    "explain":        explain_tpl.run,
    "history":        history_tpl.run,
    # Per-card AI-insight templates. Naming convention: <card_key>_insight.
    # Adding a new insight card = new template file + one row here.
    # Young Family lens templates:
    "gesix_insight":        gesix_insight_tpl.run,
    "noise_insight":        noise_insight_tpl.run,
    "refuge_insight":       refuge_insight_tpl.run,
    "kita_insight":         kita_insight_tpl.run,
    "playground_insight":   playground_insight_tpl.run,
    "pediatrician_insight": pediatrician_insight_tpl.run,
    "transit_insight":      transit_insight_tpl.run,
    "supermarket_insight":  supermarket_insight_tpl.run,
    "heat_insight":         heat_insight_tpl.run,
    "air_insight":          air_insight_tpl.run,
    # Newcomer lens templates (Spec E):
    "buergeramt_insight":        buergeramt_insight_tpl.run,
    "coworking_insight":         coworking_insight_tpl.run,
    "english_clinic_insight":    english_clinic_insight_tpl.run,
    "gesix_newcomer_insight":    gesix_newcomer_insight_tpl.run,
    "intl_food_insight":         intl_food_insight_tpl.run,
    "rail_transit_insight":      rail_transit_insight_tpl.run,
    "tram_transit_insight":      tram_transit_insight_tpl.run,
    "bus_transit_insight":       bus_transit_insight_tpl.run,
    "language_school_insight":   language_school_insight_tpl.run,
    "library_insight":           library_insight_tpl.run,
    "packstation_insight":       packstation_insight_tpl.run,
    "wochenmarkt_insight":       wochenmarkt_insight_tpl.run,
    # Per-lens executive-summary templates (one call replaces per-tile
    # insight fan-out; remote-only in practice — local Qwen 1.5B does
    # not reliably produce the strict JSON schema this template requires).
    "lens_newcomer_insight":     lens_newcomer_insight_tpl.run,
    # Quiet Living lens templates:
    "quiet_zone_insight":         quiet_zone_insight_tpl.run,
    "street_trees_insight":       street_trees_insight_tpl.run,
    "tempo30_insight":            tempo30_insight_tpl.run,
    "arterial_road_insight":      arterial_road_insight_tpl.run,
    "rail_noise_insight":         rail_noise_insight_tpl.run,
    "nightlife_inverted_insight": nightlife_inverted_insight_tpl.run,
    "gesix_quiet_insight":         gesix_quiet_insight_tpl.run,
    # Commuter lens templates:
    "commuter_rail_transit_insight": commuter_rail_transit_insight_tpl.run,
    "commuter_tram_transit_insight": commuter_tram_transit_insight_tpl.run,
    "commuter_bus_transit_insight":  commuter_bus_transit_insight_tpl.run,
    "regional_rail_reach_insight":   regional_rail_reach_insight_tpl.run,
    "cycling_network_insight":       cycling_network_insight_tpl.run,
    "car_sharing_reach_insight":     car_sharing_reach_insight_tpl.run,
    "ev_charging_reach_insight":     ev_charging_reach_insight_tpl.run,
    "airport_reach_insight":         airport_reach_insight_tpl.run,
    "gesix_commuter_insight":        gesix_commuter_insight_tpl.run,
}

# ---------------------------------------------------------------------- state

_state: dict = {"backend": None, "remote": None, "error": None}
_lock = threading.Lock()   # models are not thread-safe; serialize generation


def _init_remote_backend() -> None:
    """Instantiate the optional Cloudflare Workers AI backend synchronously.

    Remote is stateless — just an env-var read + `httpx.Client` alloc —
    so there's no reason to wait for the (slow, 5–15 s) local model load
    before it's callable. Called from `lifespan` before the local loader
    thread is spawned so remote-eligible templates are servable at t=0.
    """
    try:
        from inference.runtime.cloudflare_backend import backend_from_env
        _state["remote"] = backend_from_env()
        if _state["remote"] is not None and REMOTE_TEMPLATES:
            print(f"remote backend enabled: model={_state['remote'].model_id} "
                  f"templates={sorted(REMOTE_TEMPLATES)}", flush=True)
    except Exception as e:
        # Not fatal — local backend still handles everything.
        print(f"remote backend init failed (fallback to local only): "
              f"{type(e).__name__}: {e}", file=sys.stderr, flush=True)


def _load_local_backend() -> None:
    """Background-thread local-model loader. Populates `_state["backend"]`
    on success, `_state["error"]` on failure. Never touches `_state["remote"]`
    — that's initialised synchronously in `lifespan` before this thread
    starts, so /summarize can serve remote-eligible templates without
    waiting on the local model."""
    try:
        if BACKEND_NAME == "mlx":
            from inference.runtime.mlx_backend import DEFAULT_MODEL_ID, MlxBackend
            _state["backend"] = MlxBackend(MODEL_ID or DEFAULT_MODEL_ID)
        elif BACKEND_NAME == "llama":
            from inference.runtime.llama_backend import LlamaBackend
            _state["backend"] = LlamaBackend()
        else:
            raise ValueError(f"unknown INFERENCE_BACKEND={BACKEND_NAME!r}; expected mlx|llama")
        print(f"llm ready: backend={BACKEND_NAME} model={_state['backend'].model_id}", flush=True)
    except Exception as e:
        _state["error"] = f"{type(e).__name__}: {e}"
        print(f"llm load failed: {_state['error']}", file=sys.stderr, flush=True)


def _generate_locked(run, backend, context):
    """Run a template's synchronous generator under `_lock`.

    Called via `asyncio.to_thread` from the async handler so a slow
    generation cannot wedge the uvicorn event loop (which would freeze
    `/health`, `/ready`, and every other endpoint until the model
    finished).
    """
    with _lock:
        return run(backend, context)


def _generate_remote(run, backend, context):
    """Run a template's synchronous generator against the stateless
    remote backend. Not lock-guarded — remote is safe to call
    concurrently. Wrapped for symmetry with `_generate_locked` so both
    branches enter the same `asyncio.to_thread` shape."""
    return run(backend, context)


# ---------------------------------------------------------------------- app

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Remote backend is cheap to construct and independent of the local
    # model — initialise it synchronously so remote-eligible templates
    # can serve traffic at t=0 without waiting for the local loader.
    _init_remote_backend()
    # Load the local model in a daemon thread so uvicorn binds fast —
    # first /summarize on a local-only template pays the wait if the
    # model isn't ready yet.
    threading.Thread(target=_load_local_backend, daemon=True, name="llm-loader").start()
    yield


app = FastAPI(title="addrlens-inference", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    """Liveness — always 200 once the process is up."""
    return {"status": "ok"}


@app.get("/ready")
def ready():
    """Readiness — 200 once the local backend is loaded, 503 while warming.

    The `remote` field reports whether the Cloudflare Workers AI backend
    initialised successfully in `lifespan`. It is informational: `/ready`
    still gates only on the local backend (which every non-allow-listed
    template needs). Ops uses `remote` to distinguish "remote
    unconfigured" from "remote failed to init" without grepping stderr.
    """
    if _state["backend"] is not None:
        return {"ready":   True,
                "backend": BACKEND_NAME,
                "model":   _state["backend"].model_id,
                "remote":  _state["remote"] is not None}
    if _state["error"]:
        raise HTTPException(503, f"backend load failed: {_state['error']}")
    raise HTTPException(503, "backend still loading")


@app.post("/summarize")
async def summarize(request: Request):
    try:
        d = await request.json()
    except Exception as e:
        raise HTTPException(400, f"bad body: {e}")

    template = (d.get("template") or "").strip()
    context  = d.get("context") or {}
    # `city` accepted per §7.3 contract; not used yet — inference service is
    # city-agnostic (glossary lives in the app). Kept in the request shape
    # so future per-city routing (§7.5) doesn't require a version bump.
    _city    = (d.get("city") or "").strip()

    run = TEMPLATES.get(template)
    if run is None:
        raise HTTPException(400, f"unknown template {template!r}; "
                                 f"expected one of {sorted(TEMPLATES)}")

    # Remote-first path for allow-listed templates. Any failure — network,
    # HTTP, empty response, CF-reported error, or wall-clock timeout —
    # falls through to local. No lock: the remote backend is stateless
    # per-request and safe to call concurrently. Generation runs inside
    # `asyncio.to_thread` so uvicorn's event loop stays free during the
    # blocking `httpx.post`.
    remote = _state["remote"]
    if remote is not None and template in REMOTE_TEMPLATES:
        try:
            summary = await asyncio.wait_for(
                asyncio.to_thread(_generate_remote, run, remote, context),
                timeout=INFERENCE_GENERATION_TIMEOUT_S,
            )
            return {
                "summary":  summary,
                "model":    remote.model_id,
                "trace_id": str(uuid.uuid4()),
            }
        except ValueError as e:
            # Template contract violation (bad context). Real bug — surface.
            raise HTTPException(400, str(e))
        except asyncio.TimeoutError:
            print(f"remote inference timed out template={template} "
                  f"after {INFERENCE_GENERATION_TIMEOUT_S}s "
                  f"— falling back to local",
                  file=sys.stderr, flush=True)
        except Exception as e:
            # Remote flake — log and fall through to local. `flush=True` so
            # the message hits Docker logs even if uvicorn's buffer is deep.
            print(f"remote inference fell back to local ({template}): "
                  f"{type(e).__name__}: {e}", file=sys.stderr, flush=True)

    if _state["backend"] is None:
        msg = _state["error"] or "AI model still warming up, try again in a moment."
        raise HTTPException(503, msg)

    # Local generation: run under `_lock` inside a worker thread so the
    # event loop stays free (a wedged generation would otherwise pin
    # /health, /ready, and every other endpoint). Wall-clock capped at
    # INFERENCE_GENERATION_TIMEOUT_S; on timeout we return 504 rather
    # than let the request hang indefinitely.
    try:
        summary = await asyncio.wait_for(
            asyncio.to_thread(_generate_locked, run, _state["backend"], context),
            timeout=INFERENCE_GENERATION_TIMEOUT_S,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except asyncio.TimeoutError:
        raise HTTPException(
            504,
            f"generation timed out template={template} "
            f"after {INFERENCE_GENERATION_TIMEOUT_S}s")
    except Exception as e:
        raise HTTPException(500, f"generation failed: {type(e).__name__}: {e}")

    return {
        "summary":  summary,
        "model":    _state["backend"].model_id,
        "trace_id": str(uuid.uuid4()),
    }
