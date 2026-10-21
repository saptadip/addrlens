"""Apex landing page for addrlens.de — city hub.

DELIBERATELY MINIMAL: only imports fastapi + stdlib. Do NOT reach for
app.core / app.cities / app.config / app.deps helpers here — landing
must cold-start fast and must survive city-code refactors without
redeploy. Enforced by tests/landing/test_import_isolation.py.
"""
import html
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

WEB_DIR = Path(__file__).resolve().parent.parent.parent / "web" / "landing"

app = FastAPI(title="addrlens.de — landing", docs_url=None, redoc_url=None)

# check_dir=False: dir arrives via Docker COPY in prod (ops/Dockerfile.landing)
# and via test fixtures in CI. Skipping the boot-time check keeps pytest
# collection working when the dir hasn't been materialized yet.
app.mount("/static", StaticFiles(directory=WEB_DIR / "static", check_dir=False), name="static")


def _load_index() -> bytes:
    """Load web/landing/index.html once at boot. Inject Umami tracker
    only when the LANDING-suffixed env vars are set.

    No fallback for the ID (prevents cross-contamination with Berlin/Hamburg
    website IDs). The SCRIPT_URL DOES fall back to the flat
    `UMAMI_SCRIPT_URL` because all three sites share one self-hosted
    Umami server.
    """
    content = (WEB_DIR / "index.html").read_text(encoding="utf-8")
    umami_id = os.environ.get("UMAMI_WEBSITE_ID_LANDING", "").strip()
    umami_src = (os.environ.get("UMAMI_SCRIPT_URL_LANDING")
                 or os.environ.get("UMAMI_SCRIPT_URL", "")).strip()
    if umami_id and umami_src:
        tag = (
            f'<script defer '
            f'src="{html.escape(umami_src, quote=True)}" '
            f'data-website-id="{html.escape(umami_id, quote=True)}"></script>'
        )
        content = content.replace("<!-- UMAMI-INJECT -->", tag)
    return content.encode("utf-8")


# Loaded once at boot. Editing web/landing/index.html requires
# `docker compose restart app-landing` to take effect.
_INDEX_HTML = _load_index()


@app.get("/", include_in_schema=False)
def index():
    return Response(_INDEX_HTML, media_type="text/html; charset=utf-8")


@app.get("/impressum", include_in_schema=False)
def impressum():
    return FileResponse(WEB_DIR / "impressum.html", media_type="text/html; charset=utf-8")


@app.get("/datenschutzerklaerung", include_in_schema=False)
def datenschutz():
    return FileResponse(WEB_DIR / "datenschutzerklaerung.html", media_type="text/html; charset=utf-8")


@app.get("/robots.txt", include_in_schema=False)
def robots():
    return FileResponse(WEB_DIR / "robots.txt", media_type="text/plain; charset=utf-8")


@app.get("/sitemap.xml", include_in_schema=False)
def sitemap():
    return FileResponse(WEB_DIR / "sitemap.xml", media_type="application/xml; charset=utf-8")


@app.get("/health", include_in_schema=False)
def health():
    # Match app/main.py /health shape. ROLE=landing env is diagnostic-
    # only (docker inspect / log correlation), not returned here.
    return JSONResponse({"status": "ok"})
