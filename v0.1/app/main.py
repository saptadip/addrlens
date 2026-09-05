"""FastAPI app entrypoint.

Ship B: CITY env-var selects a CityConfig at boot; the Index is built against
it and both are exposed on app.state for routes to pick up via app.deps.

Ship D-1: /ready returns 503 until Index is loaded so an orchestrator that
promotes the pod on /health won't send user traffic to a cold container.
"""
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from app.config import CORS_ORIGINS, load_city
from app.core.index import Index
from app.core.rate_limit import limiter, RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
from slowapi.middleware import SlowAPIMiddleware
from app.routes.amenities import router as amenities_router
from app.routes.config import router as config_router
from app.routes.card_insight import router as card_insight_router
from app.routes.history import router as history_router
from app.routes.lens_insight import router as lens_insight_router
from app.routes.lookup import router as lookup_router
from app.routes.noise import router as noise_router
from app.routes.suggest import router as suggest_router

# ---------- Sentry (production error tracking) ----------
# Env-guarded: local dev leaves SENTRY_DSN_APP unset, so this block is a no-op
# and sentry_sdk is never imported. Prod-only sentry-sdk dep is installed at
# the Dockerfile layer (see ops/Dockerfile.app), not in pyproject.toml.
#
# GDPR notes for a Berlin-hosted public site:
#   - send_default_pii is explicitly False — no client IP, no headers containing
#     addresses, no request body captured by default.
#   - The `before_send` scrubber redacts the `address` / `street` query string
#     parameters and the CF-Connecting-IP header the rate-limiter reads, so an
#     exception traceback attached to a lookup never carries the user's search
#     to Sentry's servers.
#   - Provision the Sentry project in the EU region (de.sentry.io) so data
#     stays in Frankfurt — matches the Hetzner box's region.
if os.environ.get("SENTRY_DSN_APP"):
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.starlette import StarletteIntegration

    def _sentry_scrub(event, _hint):
        req = event.get("request") or {}
        # Redact address-bearing query-string params. Sentry stores this as
        # either a raw string or a list of (k, v) pairs depending on version.
        qs = req.get("query_string")
        if isinstance(qs, str) and qs:
            req["query_string"] = "[REDACTED]" if any(
                k in qs for k in ("address=", "street=", "hnr=", "plz=")
            ) else qs
        elif isinstance(qs, list):
            req["query_string"] = [
                (k, "[REDACTED]") if k in {"address", "street", "hnr", "plz"} else (k, v)
                for k, v in qs
            ]
        # Sentry lowercases header names before storage.
        hdrs = req.get("headers") or {}
        for k in ("cf-connecting-ip", "x-forwarded-for", "x-real-ip"):
            if k in hdrs:
                hdrs[k] = "[REDACTED]"
        return event

    sentry_sdk.init(
        dsn=os.environ["SENTRY_DSN_APP"],
        integrations=[StarletteIntegration(), FastApiIntegration()],
        traces_sample_rate=0.1,
        environment=os.environ.get("SENTRY_ENV", "production"),
        release=os.environ.get("GIT_SHA") or None,
        send_default_pii=False,
        before_send=_sentry_scrub,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Blocking WFS calls at boot — same behaviour as phase3/server.py:main().
    # Cold-start cost is ~5–15 s depending on the city Geoportal's responsiveness.
    app.state.city = load_city()
    app.state.index = Index(app.state.city)
    yield
    # No teardown: Index is read-only in-memory data, and the module-level
    # caches in app.core.wfs / app.core.amenities get reaped with the process.


app = FastAPI(title="addrlens-app", version="0.2.0", lifespan=lifespan)

# CORS is opt-in via env — CORS_ORIGINS="https://addrlens.de,https://staging..."
# Empty list = middleware not installed = same-origin only, which is what the
# packaged SPA needs. Deliberately no wildcard support; if you need a wildcard,
# you're doing something the plan didn't envision.
if CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


# --- Umami analytics injection ---------------------------------------------
# Both env vars must be set for the tracker to render. Umami serves the
# tracker script itself; the app just injects a one-line <script> tag into
# the index.html <head>. Read at import time and cached — zero per-request
# cost, no template engine required. Local dev leaves the vars unset and
# ships a tracker-free page.
_UMAMI_WEBSITE_ID = os.environ.get("UMAMI_WEBSITE_ID", "").strip()
_UMAMI_SCRIPT_URL = os.environ.get("UMAMI_SCRIPT_URL", "").strip()


def _load_index_html() -> str:
    html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
    if _UMAMI_WEBSITE_ID and _UMAMI_SCRIPT_URL:
        # Very small surface — a defer'd single-line script tag with the
        # website id data attribute. Umami's own docs recommend exactly
        # this shape; no async, no inline JS, no CSP conflicts.
        snippet = (
            f'  <script defer data-website-id="{_UMAMI_WEBSITE_ID}" '
            f'src="{_UMAMI_SCRIPT_URL}"></script>\n</head>'
        )
        html = html.replace("</head>", snippet, 1)
    return html


_INDEX_HTML = _load_index_html()


@app.get("/", include_in_schema=False)
def index():
    """Serve web/index.html (with Umami tracker injected in prod when
    UMAMI_WEBSITE_ID + UMAMI_SCRIPT_URL are set). Frontend calls
    /api/config on load for per-city strings."""
    return Response(_INDEX_HTML, media_type="text/html; charset=utf-8")


@app.get("/impressum", include_in_schema=False)
def impressum():
    """Serve the §5 DDG Imprint page (bilingual DE + EN)."""
    return FileResponse(WEB_DIR / "impressum.html", media_type="text/html; charset=utf-8")


@app.get("/datenschutzerklaerung", include_in_schema=False)
def datenschutzerklaerung():
    """Serve the DSGVO/GDPR privacy policy (bilingual DE + EN)."""
    return FileResponse(WEB_DIR / "datenschutzerklaerung.html", media_type="text/html; charset=utf-8")


# Static assets (app.css, app.js, future vendored bundles). Kept as a plain
# StaticFiles mount — zero build step, browser caches these once per revision.
app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")

# Rate limiting — see app/core/rate_limit.py. Per-IP + per-route. Requires
# reading CF-Connecting-IP behind the tunnel. The middleware attaches the
# request/limiter binding; the exception handler translates over-limit into
# HTTP 429 with a plain JSON body.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.include_router(config_router)
app.include_router(lookup_router)
app.include_router(suggest_router)
app.include_router(amenities_router)
app.include_router(noise_router)
app.include_router(history_router)
app.include_router(card_insight_router)
app.include_router(lens_insight_router)


@app.get("/health")
def health() -> dict:
    """Liveness — no dependencies. Process up = 200."""
    return {"status": "ok"}


@app.get("/api/_sentry_boom", include_in_schema=False)
def _sentry_boom():
    """One-off Sentry wiring probe. Env-guarded so it is a 404 unless the
    operator explicitly enables it. Raises a deliberate ValueError so the
    FastAPI Sentry integration captures it as an unhandled exception,
    proving the running uvicorn process talks to Sentry the same way real
    errors would. Delete this route once verified — or leave it in place,
    the env gate makes it inert in normal operation."""
    if os.environ.get("SENTRY_BOOM_ENABLED") != "1":
        raise HTTPException(404, "not found")
    raise ValueError(
        "addrlens sentry wiring probe — this exception is intentional")


@app.get("/ready")
def ready():
    """Readiness — 200 once the boot-time Index is loaded, 503 otherwise.
    Kept deliberately dumb: the current lifespan blocks the port until Index
    is built, so in practice this only ever fires 503 if we later move Index
    construction off the boot path — which is exactly when this probe earns
    its keep."""
    idx = getattr(app.state, "index", None)
    if idx is None:
        return JSONResponse({"status": "loading"}, status_code=503)
    return {"status": "ready", "city": app.state.city.slug}
