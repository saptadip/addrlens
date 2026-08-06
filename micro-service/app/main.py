"""FastAPI app entrypoint.

Ship B: CITY env-var selects a CityConfig at boot; the Index is built against
it and both are exposed on app.state for routes to pick up via app.deps.

`/ready` returning 503 until Index is loaded lands in Ship D step 5.
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app.config import load_city
from app.core.index import Index
from app.routes.amenities import router as amenities_router
from app.routes.config import router as config_router
from app.routes.explain import router as explain_router
from app.routes.impression import router as impression_router
from app.routes.lookup import router as lookup_router
from app.routes.noise import router as noise_router


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

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


@app.get("/", include_in_schema=False)
def index():
    """Serve web/index.html verbatim (copied from phase3). Frontend calls
    /api/config on load for per-city strings."""
    return FileResponse(WEB_DIR / "index.html", media_type="text/html; charset=utf-8")


app.include_router(config_router)
app.include_router(lookup_router)
app.include_router(amenities_router)
app.include_router(noise_router)
app.include_router(impression_router)
app.include_router(explain_router)


@app.get("/health")
def health() -> dict:
    """Liveness — no dependencies. `/ready` (Ship D) will gate on Index load."""
    return {"status": "ok"}
