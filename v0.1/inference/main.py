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

from inference.templates import explain as explain_tpl
from inference.templates import gesix_insight as gesix_insight_tpl
from inference.templates import history as history_tpl
from inference.templates import impression as impression_tpl
from inference.templates import refuge_insight as refuge_insight_tpl

# ---------------------------------------------------------------------- config

BACKEND_NAME = os.environ.get("INFERENCE_BACKEND", "mlx")   # mlx | llama
MODEL_ID     = os.environ.get("INFERENCE_MODEL_ID")         # optional override

TEMPLATES = {
    "impression":     impression_tpl.run,
    "explain":        explain_tpl.run,
    "history":        history_tpl.run,
    # Per-card AI-insight templates. Naming convention: <card_key>_insight.
    # Adding a new insight card = new template file + one row here.
    "gesix_insight":  gesix_insight_tpl.run,
    "refuge_insight": refuge_insight_tpl.run,
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
