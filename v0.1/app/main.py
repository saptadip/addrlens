"""FastAPI app entrypoint.

Ship B: CITY env-var selects a CityConfig at boot; the Index is built against
it and both are exposed on app.state for routes to pick up via app.deps.

Ship D-1: /ready returns 503 until Index is loaded so an orchestrator that
promotes the pod on /health won't send user traffic to a cold container.
"""
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import CORS_ORIGINS, load_city
from app.core.index import Index
from app.routes.amenities import router as amenities_router
from app.routes.config import router as config_router
from app.routes.card_insight import router as card_insight_router
from app.routes.explain import router as explain_router
from app.routes.history import router as history_router
from app.routes.impression import router as impression_router
from app.routes.lookup import router as lookup_router
from app.routes.noise import router as noise_router

# ---------- Sentry (production error tracking) ----------
# Env-guarded: local dev leaves SENTRY_DSN_APP unset, so this block is a no-op
# and sentry_sdk is never imported. Prod-only sentry-sdk dep is installed at
# the Dockerfile layer (see ops/Dockerfile.app), not in pyproject.toml.
if os.environ.get("SENTRY_DSN_APP"):
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.starlette import StarletteIntegration

    sentry_sdk.init(
        dsn=os.environ["SENTRY_DSN_APP"],
        integrations=[StarletteIntegration(), FastApiIntegration()],
        traces_sample_rate=0.1,
        environment=os.environ.get("SENTRY_ENV", "production"),
        release=os.environ.get("GIT_SHA") or None,
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


@app.get("/", include_in_schema=False)
def index():
    """Serve web/index.html verbatim (copied from phase3). Frontend calls
    /api/config on load for per-city strings."""
    return FileResponse(WEB_DIR / "index.html", media_type="text/html; charset=utf-8")


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

app.include_router(config_router)
app.include_router(lookup_router)
app.include_router(amenities_router)
app.include_router(noise_router)
app.include_router(impression_router)
app.include_router(explain_router)
app.include_router(history_router)
app.include_router(card_insight_router)


@app.get("/health")
def health() -> dict:
    """Liveness — no dependencies. Process up = 200."""
    return {"status": "ok"}


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
