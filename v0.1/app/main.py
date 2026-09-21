"""FastAPI app entrypoint.

Ship B: CITY env-var selects a CityConfig at boot; the Index is built against
it and both are exposed on app.state for routes to pick up via app.deps.

Ship D-1: /ready returns 503 until Index is loaded so an orchestrator that
promotes the pod on /health won't send user traffic to a cold container.
"""
import base64
import hashlib
import os
import re as _jsonld_re
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
        environment=os.environ.get(
            "SENTRY_ENV",
            f"{os.environ.get('CITY', 'berlin').strip().lower()}-production"),
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
_CITY_ENV = os.environ.get("CITY", "berlin").strip().upper()
_UMAMI_WEBSITE_ID = (os.environ.get(f"UMAMI_WEBSITE_ID_{_CITY_ENV}")
                     or os.environ.get("UMAMI_WEBSITE_ID", "")).strip()
_UMAMI_SCRIPT_URL = (os.environ.get(f"UMAMI_SCRIPT_URL_{_CITY_ENV}")
                     or os.environ.get("UMAMI_SCRIPT_URL", "")).strip()


def _load_index_html() -> str:
    html = (WEB_DIR / "index.html").read_text(encoding="utf-8")

    # --- Umami analytics injection (existing) ---------------------------------
    if _UMAMI_WEBSITE_ID and _UMAMI_SCRIPT_URL:
        # Very small surface — a defer'd single-line script tag with the
        # website id data attribute. Umami's own docs recommend exactly
        # this shape; no async, no inline JS, no CSP conflicts.
        snippet = (
            f'  <script defer data-website-id="{_UMAMI_WEBSITE_ID}" '
            f'src="{_UMAMI_SCRIPT_URL}"></script>\n</head>'
        )
        html = html.replace("</head>", snippet, 1)

    # --- Per-city SSR swap ----------------------------------------------------
    # Load city config (reads CITY env var, defaults to 'berlin').
    cfg = load_city()
    outlines_dir = WEB_DIR / "static" / "img" / "city-outlines"

    # Always swap data-city attribute (no-op for Berlin since value matches).
    html = html.replace('data-city="berlin"', f'data-city="{cfg.slug}"', 1)

    # Always inject the city outline path into both SVG slots.
    outline_file = outlines_dir / f"{cfg.slug}.svg"
    outline_fragment = outline_file.read_text(encoding="utf-8")
    html = html.replace("<!-- CITY-OUTLINE-PATH -->", outline_fragment, 1)
    html = html.replace("<!-- CITY-CLIP-PATH -->", outline_fragment, 1)

    # Always inject the city pins.
    pins_file = outlines_dir / f"{cfg.slug}-pins.svg"
    pins_fragment = pins_file.read_text(encoding="utf-8")
    html = html.replace("<!-- CITY-PINS -->", pins_fragment, 1)

    # Always inject the city attribution fragment (h4 + <p id="footer-city-attr">
    # + 4 further h4 sections). Berlin fragment is byte-identical to the pre-T29
    # inline block; Hamburg fragment carries Hamburg data-source list, HVV/HADAG,
    # BSW Sozialmonitoring, standesamt-only admin, Hamburg Geofabrik extract.
    attribution_file = outlines_dir / f"{cfg.slug}-attribution.html"
    attribution_fragment = attribution_file.read_text(encoding="utf-8")
    html = html.replace("<!-- CITY-ATTRIBUTION-BLOCK -->", attribution_fragment, 1)

    # City-specific text/JSON-LD/hero swaps — only when not Berlin.
    if cfg.slug != "berlin":
        dn = cfg.display_name  # e.g. "Hamburg"

        # Title + meta content strings
        html = html.replace("Moving to Berlin?", f"Moving to {dn}?")
        html = html.replace(
            "People moving to or evaluating flats in Berlin",
            f"People moving to or evaluating flats in {dn}",
        )
        html = html.replace("AddrLens Berlin", f"AddrLens {dn}")
        html = html.replace(
            'aria-label="Berlin address"',
            f'aria-label="{dn} address"',
        )
        html = html.replace(
            "life around any Berlin address",
            f"life around any {dn} address",
        )
        html = html.replace(
            "AddrLens hero — Moving to Berlin?",
            f"AddrLens hero — Moving to {dn}?",
        )
        html = html.replace(
            "Search box for any Berlin address, Berlin map on the right",
            f"Search box for any {dn} address, {dn} map on the right",
        )
        html = html.replace("AddrLens scanning Berlin", f"AddrLens scanning {dn}")
        # aria-label on logo anchor
        html = html.replace(
            'aria-label="AddrLens Berlin — home"',
            f'aria-label="AddrLens {dn} — home"',
        )

        # JSON-LD structured data fields
        html = html.replace('"addressLocality": "Berlin"', f'"addressLocality": "{dn}"')
        html = html.replace('"name": "Berlin"', f'"name": "{dn}"')

        # Example address chip: swap Berlin example for Hamburg
        html = html.replace(
            "Sybelstrasse 59, Charlottenburg, 10629 Berlin",
            "Grindelallee 100, Rotherbaum, 20146 Hamburg",
        )

        # Footer attribution is now driven by the per-city <slug>-attribution.html
        # fragment injected above via <!-- CITY-ATTRIBUTION-BLOCK -->; no
        # regex-substitute needed here.

    return html


_INDEX_HTML = _load_index_html()


@app.get("/", include_in_schema=False)
def index():
    """Serve web/index.html (with Umami tracker injected in prod when
    UMAMI_WEBSITE_ID + UMAMI_SCRIPT_URL are set). Frontend calls
    /api/config on load for per-city strings."""
    return Response(_INDEX_HTML, media_type="text/html; charset=utf-8")


def _city_or_default(filename: str) -> Path:
    """Serve WEB_DIR / <slug> / <filename> if present, else WEB_DIR / <filename>.

    Defensive fallback keeps Berlin serving even if a per-city file is missing.
    slug is read from app.state.city which is set at lifespan startup.
    """
    p = WEB_DIR / app.state.city.slug / filename
    return p if p.exists() else WEB_DIR / filename


@app.get("/impressum", include_in_schema=False)
def impressum():
    """Serve the §5 DDG Imprint page — per-city variant when available."""
    return FileResponse(_city_or_default("impressum.html"), media_type="text/html; charset=utf-8")


@app.get("/datenschutzerklaerung", include_in_schema=False)
def datenschutzerklaerung():
    """Serve the DSGVO/GDPR privacy policy — per-city variant when available."""
    return FileResponse(_city_or_default("datenschutzerklaerung.html"), media_type="text/html; charset=utf-8")


@app.get("/robots.txt", include_in_schema=False)
def robots():
    """Serve robots.txt — per-city variant when available."""
    return FileResponse(_city_or_default("robots.txt"), media_type="text/plain; charset=utf-8")


@app.get("/sitemap.xml", include_in_schema=False)
def sitemap():
    """Serve sitemap.xml — per-city variant when available."""
    return FileResponse(_city_or_default("sitemap.xml"), media_type="application/xml; charset=utf-8")


# ES module files under /static/modules/ must revalidate on every load.
# Chromium's module registry keys on URL, so bumping ?v= on the app.js entry
# does NOT force a refetch of child module imports (which are unversioned
# relative paths). Without this header, users with a cached module from an
# older deploy would keep it even after the entry is refetched.
@app.middleware("http")
async def _module_cache_headers(request, call_next):
    response = await call_next(request)
    path = request.url.path
    if (path.startswith("/static/modules/") and path.endswith(".js")) \
       or path in ("/static/app.css", "/static/app.js"):
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
    return response


# -- Security headers -------------------------------------------------------
# CSP + baseline hardening on every response. HSTS is delegated to
# Cloudflare (which fronts every request via the Tunnel); adding it here
# would double-set the header at the edge.
#
# CSP allow-list rationale:
# - script-src         : own origin + unpkg (Leaflet JS) + Umami origin if
#                        UMAMI_SCRIPT_URL is set. Neither the SPA nor the
#                        injected Umami tag uses inline scripts; no
#                        `'unsafe-inline'`.
# - style-src          : own origin + Google Fonts + unpkg (Leaflet CSS).
#                        `'unsafe-inline'` is required by three surfaces
#                        that legitimately produce inline styles:
#                          (a) Leaflet writes `element.style.*` at runtime
#                              for tile / marker positioning.
#                          (b) v0.1/web/impressum.html + datenschutz-
#                              erklaerung.html each carry a small
#                              `<style>` block for legal-page layout.
#                          (c) The SPA generates `style="..."` attributes
#                              inside innerHTML strings in ~30 sites
#                              across modules/panels/**.
#                        CSP L3 `style-src-attr` alone would not cover
#                        (b) or Safari's older CSP L2; a single
#                        `'unsafe-inline'` on `style-src` is the
#                        pragmatic covering set.
# - font-src           : own origin + Google Fonts static (woff2).
# - img-src            : own origin + `data:` (belt-and-braces for future
#                        CSS `background-image: url(data:...)` or inline
#                        SVG — SPA currently uses divIcon markers so
#                        default Leaflet marker PNGs are not fetched)
#                        + OSM tile servers. CARTO / other basemaps not in
#                        use in v0.1.
# - connect-src        : own origin + Umami collect endpoint if set.
# - frame-ancestors    : `'none'` (anti-clickjack; supersedes
#                        X-Frame-Options but we still set XFO below for
#                        very old browsers).
# - base-uri, form-action, object-src : tightened to defaults per
#                        OWASP Secure Headers baseline.
from urllib.parse import urlparse

def _umami_origin() -> str:
    """Extract scheme://host[:port] from UMAMI_SCRIPT_URL for CSP.

    Preserves port because CSP source-list matching is port-sensitive:
    `https://host` only matches port 443, and Umami on a non-default
    port (e.g. self-hosted at :8443) would be blocked otherwise.
    IPv6 hostnames are bracketed per RFC 3986.
    """
    if not _UMAMI_SCRIPT_URL:
        return ""
    p = urlparse(_UMAMI_SCRIPT_URL)
    if not (p.scheme and p.hostname):
        return ""
    host = f"[{p.hostname}]" if ":" in p.hostname else p.hostname
    port = f":{p.port}" if p.port else ""
    return f"{p.scheme}://{host}{port}"

_UMAMI_ORIGIN = _umami_origin()

# SHA-256 hash of the JSON-LD structured-data block in the served HTML.
# (<script type="application/ld+json">…</script>). Per CSP L3 spec, JSON-LD
# data blocks are exempt from script-src, but some browsers (older Chrome,
# some Safari versions, CSP validators) still flag them as inline-script
# violations. Whitelisting the exact content hash silences the warning
# without opening the door to `'unsafe-inline'`.
#
# The hash is computed at boot from the actual _INDEX_HTML content — which
# already has per-city SSR applied (e.g. "Hamburg" substituted for "Berlin"
# in name/addressLocality/audience fields). This means each city gets its
# own correct hash without any manual recompute step.
#
# Berlin expected: 'sha256-lDQ6ebdG88cQn3rjZolSlpxIE1He/+rKXD+SwHIf18E='
def _compute_jsonld_hash(html: str) -> str:
    """Extract the JSON-LD block from html and return a CSP sha256- hash token.

    Returns an empty string if no JSON-LD block is found (which drops the
    hash from _SCRIPT_SRC silently — safe for pages that omit the block).
    """
    m = _jsonld_re.search(
        r'<script type="application/ld\+json">(.*?)</script>', html, _jsonld_re.DOTALL
    )
    if not m:
        return ""
    digest = hashlib.sha256(m.group(1).encode()).digest()
    return f"'sha256-{base64.b64encode(digest).decode()}'"


_JSONLD_HASH = _compute_jsonld_hash(_INDEX_HTML)
_SCRIPT_SRC  = " ".join(x for x in ["'self'", "https://unpkg.com", _UMAMI_ORIGIN, _JSONLD_HASH] if x)
_STYLE_SRC   = " ".join(["'self'", "'unsafe-inline'",
                         "https://fonts.googleapis.com", "https://unpkg.com"])
_FONT_SRC    = " ".join(["'self'", "https://fonts.gstatic.com"])
_IMG_SRC     = " ".join(["'self'", "data:", "https://*.tile.openstreetmap.org"])
_CONNECT_SRC = " ".join(x for x in ["'self'", _UMAMI_ORIGIN] if x)

_CSP = "; ".join([
    "default-src 'self'",
    f"script-src {_SCRIPT_SRC}",
    f"style-src {_STYLE_SRC}",
    f"font-src {_FONT_SRC}",
    f"img-src {_IMG_SRC}",
    f"connect-src {_CONNECT_SRC}",
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "object-src 'none'",
])

@app.middleware("http")
async def _security_headers(request, call_next):
    response = await call_next(request)
    # Content-agnostic headers on every response.
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["X-Frame-Options"] = "DENY"
    # CSP applies to browser-rendered HTML only. JSON API responses don't
    # need it (browsers don't render them as documents) and adding it just
    # bloats every /api/* response.
    content_type = response.headers.get("content-type", "")
    if content_type.startswith("text/html"):
        response.headers["Content-Security-Policy"] = _CSP
    return response

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
