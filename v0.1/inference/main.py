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
"""
from __future__ import annotations

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
from inference.templates import library_insight as library_insight_tpl
from inference.templates import noise_insight as noise_insight_tpl
from inference.templates import packstation_insight as packstation_insight_tpl
from inference.templates import pediatrician_insight as pediatrician_insight_tpl
from inference.templates import playground_insight as playground_insight_tpl
from inference.templates import refuge_insight as refuge_insight_tpl
from inference.templates import supermarket_insight as supermarket_insight_tpl
from inference.templates import transit_insight as transit_insight_tpl
from inference.templates import transit_newcomer_insight as transit_newcomer_insight_tpl
from inference.templates import wochenmarkt_insight as wochenmarkt_insight_tpl

# ---------- Sentry (production error tracking) ----------
# Env-guarded. Local dev (Apple Silicon, INFERENCE_BACKEND=mlx) leaves the DSN
# unset, so this is a no-op and sentry_sdk is never imported.
if os.environ.get("SENTRY_DSN_INFERENCE"):
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.starlette import StarletteIntegration

    sentry_sdk.init(
        dsn=os.environ["SENTRY_DSN_INFERENCE"],
        integrations=[StarletteIntegration(), FastApiIntegration()],
        traces_sample_rate=0.1,
        environment=os.environ.get("SENTRY_ENV", "production"),
        release=os.environ.get("GIT_SHA") or None,
    )

# ---------------------------------------------------------------------- config

BACKEND_NAME = os.environ.get("INFERENCE_BACKEND", "mlx")   # mlx | llama
MODEL_ID     = os.environ.get("INFERENCE_MODEL_ID")         # optional override

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
    "transit_newcomer_insight":  transit_newcomer_insight_tpl.run,
    "language_school_insight":   language_school_insight_tpl.run,
    "library_insight":           library_insight_tpl.run,
    "packstation_insight":       packstation_insight_tpl.run,
    "wochenmarkt_insight":       wochenmarkt_insight_tpl.run,
}

# ---------------------------------------------------------------------- state

_state: dict = {"backend": None, "error": None}
_lock = threading.Lock()   # models are not thread-safe; serialize generation


def _load_backend() -> None:
    """Background-thread model loader. Populates _state on success/failure."""
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


# ---------------------------------------------------------------------- app

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load in a daemon thread so uvicorn binds fast — first /summarize pays
    # the wait if the model isn't ready yet.
    threading.Thread(target=_load_backend, daemon=True, name="llm-loader").start()
    yield


app = FastAPI(title="addrlens-inference", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    """Liveness — always 200 once the process is up."""
    return {"status": "ok"}


@app.get("/ready")
def ready():
    """Readiness — 200 once backend is loaded, 503 while warming."""
    if _state["backend"] is not None:
        return {"ready": True, "backend": BACKEND_NAME,
                "model": _state["backend"].model_id}
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

    if _state["backend"] is None:
        msg = _state["error"] or "AI model still warming up, try again in a moment."
        raise HTTPException(503, msg)

    try:
        with _lock:
            summary = run(_state["backend"], context)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"generation failed: {type(e).__name__}: {e}")

    return {
        "summary":  summary,
        "model":    _state["backend"].model_id,
        "trace_id": str(uuid.uuid4()),
    }
