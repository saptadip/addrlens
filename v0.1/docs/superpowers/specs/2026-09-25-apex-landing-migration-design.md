# Apex Landing Migration — `addrlens.de` → `berlin.addrlens.de`

**Status:** Design approved (approach B + minimum-viable scope).
**Date:** 2026-09-25.
**Author:** sapta.

---

## 1. Problem

`addrlens.de` (apex) currently serves the Berlin app. Hamburg lives on `hamburg.addrlens.de`. As more cities land (Munich, Cologne, …) the apex should be a city-agnostic hub, not one city's app. Users typing the bare brand should see all cities, not Berlin by accident.

## 2. Goals

1. Apex `addrlens.de` serves a **static landing page** listing available cities.
2. Berlin app moves to **`berlin.addrlens.de`** — same code, same container, new hostname.
3. Hamburg (`hamburg.addrlens.de`) unchanged.
4. Old inbound links to `addrlens.de/<path>` (non-landing paths) **301 to `berlin.addrlens.de/<path>`** so bookmarks and backlinks survive.
5. Landing page visually indistinguishable in tone from the city apps — same fonts, palette, effect language.
6. Single deploy pipeline (all containers via `docker compose … up -d`).

## 3. Non-goals

- No CMS, blog, testimonials, contact form, or animated hero on landing.
- No refactor of city-init model (`CITY` env at boot stays).
- No new brand identity work — reuse existing tokens.
- No Cloudflare Pages / second deploy pipeline.
- No SEO change-of-address ceremony beyond GSC property add + sitemap resubmit (Google's tool doesn't support subdomain moves anyway).

## 4. Approach — Recap

**B: New `app-landing` FastAPI container behind same tunnel — dedicated minimal image.**

- New container `app-landing` on port `8000` (Berlin=8001, Hamburg=8002).
- **New dedicated `ops/Dockerfile.landing`** — minimal Python base, only `fastapi` + `uvicorn[standard]` installed (no shapely, no pandas, no city loaders, no scoring). Target image size **~90-120 MB** vs ~200 MB for `Dockerfile.app`.
- New FastAPI app at `app/landing/main.py` with **ruthlessly minimal imports** (fastapi + fastapi.responses + pathlib only — no `app.core`, no `app.cities`).
- Serves `web/landing/*` static assets.
- Same tunnel adds `addrlens.de` → `app-landing:8000`, adds `berlin.addrlens.de` → `app:8001`, removes old apex → `app:8001`.

## 5. Architecture — Target State

```
                 Cloudflare Tunnel (addrlens-prod)
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
  addrlens.de/         berlin.addrlens.de/    hamburg.addrlens.de/
        │                     │                     │
  app-landing:8000       app:8001              app-hh:8002
  (FastAPI, landing)     (FastAPI, CITY=       (FastAPI, CITY=
                          berlin)                hamburg)
```

Redirect Rule at CF edge:
```
addrlens.de/<path> → 301 https://berlin.addrlens.de/<path>
   EXCEPT path in { /, /impressum, /datenschutzerklaerung, /robots.txt, /sitemap.xml, /health, /static/* }
```

## 6. New Code

### 6.1 `app/landing/main.py`

Minimal FastAPI app. Full source ≤ 70 lines. Structure:

```python
"""Apex landing page for addrlens.de — city hub.

DELIBERATELY MINIMAL: only imports fastapi + stdlib. Do NOT reach for
app.core / app.cities helpers here — landing must cold-start fast and
must survive city-code refactors without redeploy.
"""
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse, Response, JSONResponse
from fastapi.staticfiles import StaticFiles
import os

WEB_DIR = Path(__file__).resolve().parent.parent.parent / "web" / "landing"

app = FastAPI(title="addrlens.de — landing", docs_url=None, redoc_url=None)

app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")

# Load once at boot — inject Umami tracker if env set.
# LANDING ONLY reads the LANDING-suffixed env vars — no fallback to
# the flat UMAMI_WEBSITE_ID. Rationale: prevents accidental
# cross-contamination if an operator forgets to migrate the flat name
# during cutover. Landing gets no tracker unless explicitly configured.
def _load_index() -> bytes:
    html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
    umami_id = os.environ.get("UMAMI_WEBSITE_ID_LANDING", "").strip()
    umami_src = (os.environ.get("UMAMI_SCRIPT_URL_LANDING")
                 or os.environ.get("UMAMI_SCRIPT_URL", "")).strip()
    if umami_id and umami_src:
        tag = f'<script defer src="{umami_src}" data-website-id="{umami_id}"></script>'
        html = html.replace("<!-- UMAMI-INJECT -->", tag)
    return html.encode("utf-8")

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
    # Match app/main.py /health shape. The container's `ROLE=landing`
    # env is diagnostic-only (docker inspect / log correlation); not
    # returned here to keep the response identical across containers.
    return JSONResponse({"status": "ok"})
```

### 6.2 Import guard test — `tests/landing/test_import_isolation.py`

Enforce the "minimal imports" rule so future edits don't silently couple landing to any part of the `app` namespace beyond `app.landing` itself. **Whitelist, not blacklist** — a blacklist misses `app.config`, `app.deps`, or any future `app.<newmodule>` that reaches for city helpers.

`app.landing.main._load_index()` reads `web/landing/index.html` at import time, which would `FileNotFoundError` if the file isn't present in CI's checkout. The test provides a fixture file (or monkeypatches `Path.read_text`) so import succeeds even in a minimal test environment.

```python
import sys
import importlib
from pathlib import Path
import pytest

# Allowed imports under the app.* namespace.
_ALLOWED_APP_MODULES = {"app", "app.landing", "app.landing.main"}

@pytest.fixture
def _landing_fixture(tmp_path, monkeypatch):
    """Create a minimal web/landing/ tree so app.landing.main._load_index() succeeds."""
    web = tmp_path / "web" / "landing"
    web.mkdir(parents=True)
    (web / "index.html").write_text("<!doctype html><html></html>", encoding="utf-8")
    (web / "static").mkdir()
    monkeypatch.setenv("PYTHONPATH", str(tmp_path))
    # Point WEB_DIR by chdir; app.landing.main resolves WEB_DIR relative to itself.
    monkeypatch.chdir(tmp_path)
    return web

def test_landing_imports_only_whitelisted_app_modules(_landing_fixture):
    # Fresh import to detect coupling introduced later.
    for mod in list(sys.modules):
        if mod.startswith("app."):
            del sys.modules[mod]
    if "app" in sys.modules:
        del sys.modules["app"]

    importlib.import_module("app.landing.main")

    imported_app_modules = {m for m in sys.modules if m == "app" or m.startswith("app.")}
    unexpected = imported_app_modules - _ALLOWED_APP_MODULES
    assert not unexpected, (
        f"app.landing must stay minimal. Unexpected app.* imports: {sorted(unexpected)}. "
        "Landing exists to be snappy — do not reach for app.core / app.cities / "
        "app.config / app.deps / app.routes here."
    )
```

**Fixture note:** the fixture approach is slightly awkward because `WEB_DIR` in `app/landing/main.py` uses a static `Path(__file__).resolve().parent.parent.parent / "web" / "landing"` at module-import time. Options: (a) pass `chdir` + set `PYTHONPATH` as above so a shadow `web/landing/` is discoverable; (b) monkeypatch `pathlib.Path.read_text` for the test; (c) make `WEB_DIR` overridable via env var (`LANDING_WEB_DIR`) and set it in the fixture — clean but adds a knob. Recommend (b) for simplicity.

## 7. Web Assets — `web/landing/`

```
web/landing/
├── index.html                     # hero + city cards + legal + i18n toggle
├── impressum.html                 # apex-scoped (canonical https://addrlens.de/impressum)
├── datenschutzerklaerung.html     # apex-scoped (canonical https://addrlens.de/datenschutzerklaerung)
├── robots.txt                     # allow all, sitemap: https://addrlens.de/sitemap.xml
├── sitemap.xml                    # apex URLs + optional cross-refs to berlin./hamburg.
└── static/
    ├── landing.css                # minimal CSS, reuses existing tokens
    ├── img/
    │   ├── logo.png               # copy from web/static/img/logo.png (identical)
    │   ├── og-image.jpg           # copy from web/static/img/og-image.jpg (reused, per §19)
    │   ├── favicon.png            # copy from web/static/img/logo.png
    │   ├── berlin-card.png        # copy from web/static/img/hero/berlin.png
    │   └── hamburg-card.png       # copy from web/static/img/hero/hamburg.png
    └── fonts/                     # symlink or copy of web/static/fonts/*
```

**Asset reuse rule:** landing static assets are **copies** of the city-app assets, not symlinks — Docker COPY into container image doesn't follow symlinks reliably across build contexts. Duplication is 4 files × ~50KB = trivial disk cost; alternative (shared volume mount) adds infra complexity for zero user benefit.

## 8. Landing Page Design

### 8.1 Design tokens — **reuse existing verbatim**

From `web/static/app.css`:
- **Fonts:** Inter (400/500/600/700/800) — body + city card titles. Space Grotesk (500/600/700) — H1 hero only. Skip Playfair/Merriweather (editorial-only, not needed here).
- **Palette:**
  - `--hero-bg: #DCE7F3` — landing background (matches city hero surface)
  - `--hero-accent: #0284C7` — link/CTA color
  - `--brand: #4F46E5` — "Live" badge accent
  - `--ink: #111827` — primary text
  - `--muted: #6B7280` — secondary text
  - `--result-bg: #EEF2FF`, `--result-bg-hover: #DDE7FF` — city card surfaces
  - `--border: #E5E7EB`
- **Shadow:** neumorphic `--sh-2` (0 4px 8px + 0 12px 24px, both rgba(17,24,39,.06)) on city cards.
- **Radius:** 16px on cards (matches app hero surface).
- **Type scale:** clamp-based responsive, hero H1 `clamp(2.5rem, 5vw, 4.5rem)`; H2 `clamp(1.5rem, 2.5vw, 2rem)`; body 15px (matches app).

### 8.2 Page structure

```
┌────────────────────────────────────────────────────────────┐
│  [logo.png] AddrLens                             [EN | DE] │  <- header, sticky (h=64px)
├────────────────────────────────────────────────────────────┤
│                                                            │
│       Street intelligence for German cities                │  <- hero H1 (Space Grotesk)
│                                                            │
│       Open data, cleanly connected.                        │  <- tagline (Inter 400, muted)
│       Pick your city.                                      │
│                                                            │
├────────────────────────────────────────────────────────────┤
│                                                            │
│   ┌──────────────────────┐    ┌──────────────────────┐   │
│   │ [berlin-card.png]    │    │ [hamburg-card.png]   │   │  <- city cards (2-col ≥768px,
│   │                      │    │                      │   │     1-col <768px)
│   │  Berlin       ● Live │    │  Hamburg      ● Live │   │
│   │  Address compare ·   │    │  Address compare ·   │   │  <- subline (Inter 500)
│   │  Life-situation lens │    │  Life-situation lens │   │
│   │  → berlin.addrlens.de│    │  → hamburg.addrlens.de│  │  <- CTA link
│   └──────────────────────┘    └──────────────────────┘   │
│                                                            │
├────────────────────────────────────────────────────────────┤
│  Imprint · Privacy                          © 2026 sapta   │  <- footer
└────────────────────────────────────────────────────────────┘
```

**Notes:**
- **Primary language: English.** Landing targets expats — English default, DE toggle. Reverses the city-app convention (which is DE-default) intentionally: the apex is the discovery surface for non-German speakers arriving via search/social; once inside a city they're already committed and can switch to DE if wanted.
- Footer links: **Imprint** + **Privacy** only. No GitHub link (removed per §19).
- German footer variant: "Impressum · Datenschutz". Same two links, translated.
- City card image = the existing `web/static/img/hero/{city}.png` hero illustration — same visual users see when they land inside each city app. Zero visual break on click-through.
- "Live" badge = `--brand` filled dot + `● Live` in Inter 500, 12px.
- Subline uses soft copy for MVP (EN: "Address compare · Life-situation lens" / DE: "Adressvergleich · Lebenslagen-Linsen") — no dynamic numbers, no build-time coupling to `CityConfig`. Address counts removed from scope (see §19).
- **No roadmap teaser line** — landing shows only cities that are live today (see §19). New cities are added by editing the city-cards grid, not by promising future work.

### 8.3 i18n toggle

**English is the default** on landing (expat-focused audience — reverses city-app convention where DE is default). Two independent HTML fragments in one file, JS toggles `hidden` attribute on `[data-lang]` wrappers. State persists in `localStorage['addrlens.lang']`. No i18n framework.

Detection: default to English; only auto-switch to DE if the user has previously chosen DE (stored in localStorage). Do **not** sniff `navigator.language` — a German-locale browser reaching the apex may still be an English-preferring expat, and the whole point of the apex is to be welcoming to that audience.

```html
<div data-lang="en">…English copy…</div>
<div data-lang="de" hidden>…German copy…</div>
<button id="lang-toggle" type="button">DE</button>
<script>
  const KEY = 'addrlens.lang';
  const stored = localStorage.getItem(KEY) || 'en';   // EN default
  document.documentElement.lang = stored;
  document.querySelectorAll('[data-lang]').forEach(el => {
    el.hidden = el.dataset.lang !== stored;
  });
  document.getElementById('lang-toggle').textContent = stored === 'en' ? 'DE' : 'EN';
  document.getElementById('lang-toggle').addEventListener('click', () => {
    const next = document.documentElement.lang === 'en' ? 'de' : 'en';
    document.documentElement.lang = next;
    localStorage.setItem(KEY, next);
    document.querySelectorAll('[data-lang]').forEach(el => {
      el.hidden = el.dataset.lang !== next;
    });
    document.getElementById('lang-toggle').textContent = next === 'en' ? 'DE' : 'EN';
  });
</script>
```

Inline `<script>` — no external JS file, no framework. ~30 lines total.

### 8.4 Motion + interaction

- **City card hover:** background `--result-bg` → `--result-bg-hover`, transform `translateY(-2px)`, 200ms ease. Matches app's lens-tile pattern.
- **Focus states:** 2px outline `--hero-accent` at 2px offset — mandatory for keyboard nav.
- **Cursor:** `cursor-pointer` on every clickable.
- **Reduced motion:** wrap transitions in `@media (prefers-reduced-motion: no-preference) { … }`.
- **No scroll animations, no GSAP, no JS motion.** Landing is a menu, not a story.

### 8.5 SEO tags

```html
<link rel="canonical" href="https://addrlens.de/">
<meta property="og:url" content="https://addrlens.de/">
<meta property="og:title" content="AddrLens — Street intelligence for German cities">
<meta property="og:description" content="Open data, cleanly connected. Berlin and Hamburg live.">
<meta property="og:image" content="https://addrlens.de/static/img/og-image.jpg">
<meta name="twitter:card" content="summary_large_image">
<link rel="alternate" hreflang="en-GB" href="https://addrlens.de/">
<link rel="alternate" hreflang="de-DE" href="https://addrlens.de/">
<link rel="alternate" hreflang="x-default" href="https://addrlens.de/">
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "WebSite",
  "name": "AddrLens",
  "url": "https://addrlens.de/",
  "hasPart": [
    { "@type": "WebSite", "name": "AddrLens Berlin", "url": "https://berlin.addrlens.de/" },
    { "@type": "WebSite", "name": "AddrLens Hamburg", "url": "https://hamburg.addrlens.de/" }
  ]
}
</script>
```

### 8.6 Pre-delivery checklist (from ui-ux-pro-max)

- [ ] No emojis as icons (dot for "Live" via CSS `::before` circle or inline SVG)
- [ ] `cursor-pointer` on every city card + language toggle
- [ ] Hover transitions 150-300ms
- [ ] Text contrast ≥ 4.5:1 (`--ink` on `--hero-bg` = 15.8:1 ✓)
- [ ] Focus states visible for keyboard nav
- [ ] `prefers-reduced-motion` respected
- [ ] Responsive: 375 / 768 / 1024 / 1440 tested
- [ ] `<html lang="en">` set as default (EN-primary landing) + updates on toggle
- [ ] Alt text on all imgs (`alt="Berlin Skyline"`, `alt="Hamburg Skyline"`, `alt=""` on decorative logo when text follows)

## 9. Berlin App Changes (`web/*` — non-hamburg)

Text/URL surgery, no logic changes:

| File | Change |
|---|---|
| `web/index.html` | `og:url`, `canonical`, both `hreflang`, JSON-LD `url`, `og:image`, `twitter:image` → `https://berlin.addrlens.de/…` |
| `web/impressum.html` | All URL/href refs to `https://addrlens.de` → `berlin.addrlens.de` (both DE + EN sections). Email `sapta@addrlens.de` unchanged (apex email routing preserved). Verify with: `grep -cE 'https?://addrlens\.de' web/impressum.html` before/after. |
| `web/datenschutzerklaerung.html` | Same shape as impressum: website URL refs → `berlin.addrlens.de`, email unchanged. Verify with same grep on this file. |
| `web/sitemap.xml` | All 3 `<loc>` entries → `https://berlin.addrlens.de/…` |
| `web/robots.txt` | Sitemap line → `https://berlin.addrlens.de/sitemap.xml` |
| `web/static/modules/compare.js` | `print-header-site` string `addrlens.de` → `berlin.addrlens.de` (or keep as brand — see decision below) |

**`compare.js` print-header decision:** print header appears on lens-comparison PDF exports. Users read this offline; the brand string helps them find the site again. **Change to `berlin.addrlens.de`** — that's where the app that made the PDF actually lives. Matches truth-in-labelling.

### 9.1 Hamburg Legal Page Fixes (NOT already correct)

Hamburg's canonical / og:url tags are already correct (they point at `hamburg.addrlens.de`), but the **operator "Website:" contact line inside both imprint and privacy pages still shows `https://addrlens.de`** — 4 occurrences across 2 files, both DE and EN sections. Post-cutover, that URL will serve the landing (not the Hamburg app being imprinted), which is (a) semantically wrong, and (b) risks a §5 DDG abmahnung for an imprint that names a website URL that isn't the site being imprinted.

| File | Line | Change |
|---|---|---|
| `web/hamburg/impressum.html` | 46 | `Website: https://addrlens.de` → `https://hamburg.addrlens.de` (DE section) |
| `web/hamburg/impressum.html` | 159 | Same (EN section) |
| `web/hamburg/datenschutzerklaerung.html` | 46 | Same (DE section) |
| `web/hamburg/datenschutzerklaerung.html` | 385 | Same (EN section) |

Emails (`sapta@addrlens.de`) stay unchanged — apex mail routing survives the migration.

## 10. Docker Changes

### 10.1 New `ops/Dockerfile.landing` — dedicated minimal image

Rationale: reusing `Dockerfile.app` would ship ~200 MB of unused deps (shapely, pandas, sentry, osmium, all city loaders) into a container that serves 5 static endpoints. Separate Dockerfile keeps landing snappy, small (~90-120 MB), and independent of app-side dep churn.

```dockerfile
# ops/Dockerfile.landing
# Apex landing container. Serves web/landing/* on port 8000.
# ~90-120 MB target. Zero coupling to app.core / app.cities / scoring.
#
# Build context = v0.1/. From repo root:
#   docker build -f v0.1/ops/Dockerfile.landing -t addrlens-landing v0.1

FROM python:3.11-slim AS base

# ca-certificates: outbound HTTPS if ever needed. tzdata: log timestamps.
# Deliberately no libexpat1 (shapely-adjacent) — landing has no XML parsing.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /srv

# Pin fastapi + uvicorn directly — NOT from pyproject.toml (which pulls
# the full app dep tree). Version-align with pyproject.toml to avoid
# skew.
# Sync with pyproject.toml [project.dependencies] — landing tracks the
# same fastapi/uvicorn versions the app image resolves to.
RUN uv pip install --system --no-cache \
        "fastapi>=0.115" "uvicorn[standard]>=0.32"

# Copy ONLY what landing needs. Do NOT copy the full app/ package.
COPY app/__init__.py ./app/__init__.py
COPY app/landing ./app/landing
COPY web/landing ./web/landing

RUN useradd -u 10001 -m -s /sbin/nologin addrlens \
    && chown -R addrlens:addrlens /srv
USER addrlens

ENV PORT=8000 \
    ROLE=landing \
    PYTHONUNBUFFERED=1

EXPOSE 8000
# Healthcheck is declared in docker-compose.prod.yml (matches app-hh
# convention — see docker-compose.prod.yml `app-hh` block). Omitted
# here to prevent Dockerfile vs compose drift.

CMD ["uvicorn", "app.landing.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Version-alignment discipline:** the `fastapi` + `uvicorn` pins in this Dockerfile must be kept in sync with the versions in `pyproject.toml` for the app image. Drift = same code running against two versions in prod. The `# Sync with pyproject.toml` comment above the `uv pip install` line makes the obligation explicit. Optional CI check: `diff <(grep -oE '(fastapi|uvicorn[^"]+)[^"]*' pyproject.toml) <(grep -oE '(fastapi|uvicorn[^"]+)[^"]*' ops/Dockerfile.landing)` — nice-to-have, not blocking.

### 10.2 `docker-compose.prod.yml` — add `app-landing` service

Mirror `app-hh` block, port 8000, **distinct image + dockerfile**:

```yaml
  app-landing:
    build:
      context: .
      dockerfile: ops/Dockerfile.landing
    image: addrlens-landing:latest
    container_name: addrlens-app-landing
    restart: unless-stopped
    env_file: /srv/addrlens/.env.production
    environment:
      PORT: 8000
      ROLE: landing
    healthcheck:
      test: ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)\" || exit 1"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 15s
    networks:
      - addrlens_net

  cloudflared:
    …
    depends_on:
      app: { condition: service_healthy }
      app-hh: { condition: service_healthy }
      app-landing: { condition: service_healthy }   # new line
```

Notes:
- No `command:` override — Dockerfile CMD does the right thing.
- No `depends_on: inference` — landing has no lens-insight endpoint, no scorer.
- `image: addrlens-landing:latest` (distinct from `addrlens-app:latest`) — separate image tag prevents accidental container reuse across roles.
- `env_file:` still points at the shared `/srv/addrlens/.env.production` — landing reads only `UMAMI_*` from it; other vars are ignored (fastapi doesn't care about unset env).

## 11. Deploy Script Changes

### 11.1 `ops/deploy/update.sh`

```diff
- "${COMPOSE[@]}" build --pull app app-hh inference
+ "${COMPOSE[@]}" build --pull app app-hh app-landing inference

- for svc_port in "app:8001" "app-hh:8002"; do
+ for svc_port in "app:8001" "app-hh:8002" "app-landing:8000"; do
    svc="${svc_port%%:*}"
    port="${svc_port##*:}"
    …
+   # Landing has no lookup — health-only smoke via compose exec, since
+   # app-landing has `ports: !reset []` and is not published to host.
+   if [ "$svc" = "app-landing" ]; then
+     "${COMPOSE[@]}" exec -T "$svc" python -c \
+       "import urllib.request; urllib.request.urlopen('http://127.0.0.1:${port}/health', timeout=3)"
+     continue
+   fi
    case "$svc" in
      app)    ADDR=$("${COMPOSE[@]}" exec -T "$svc" python -c "from app.cities.berlin import BERLIN; print(BERLIN.smoke_address)") ;;
      app-hh) ADDR=$("${COMPOSE[@]}" exec -T "$svc" python -c "from app.cities.hamburg import HAMBURG; print(HAMBURG.smoke_address)") ;;
    esac
    …
  done
```

**Why `compose exec`, not host `curl`:** `docker-compose.prod.yml:18` uses `ports: !reset []`, meaning `app-landing` (like `app` and `app-hh`) has no host-published port. A host-side `curl http://127.0.0.1:8000` would either hit nothing or a stale port from another process. The smoke must run inside the container network, matching the pattern the existing script uses for `/api/lookup` on `app`/`app-hh` at lines 58 + 75.

Landing smoke = `/health` only, no address lookup. `if $svc = app-landing → run health check + continue` before the address-based smoke block.

### 11.2 `ops/deploy/rollback.sh`

**Two edits, not one** — the script has both a `build` line (l.39) and a `up -d --force-recreate` line (l.40) with explicit service lists. Both must include `app-landing`; missing either leaves rollback partial (either landing image is stale, or landing runs on new-code image while Berlin rolls back). Exactly the Hamburg-omission footgun class.

```diff
- "${COMPOSE[@]}" build app app-hh inference
+ "${COMPOSE[@]}" build app app-hh app-landing inference
- "${COMPOSE[@]}" up -d --force-recreate app app-hh inference
+ "${COMPOSE[@]}" up -d --force-recreate app app-hh app-landing inference
```

### 11.3 `ops/deploy/README.md`

Update curl examples:
```
curl -sSf https://addrlens.de/health         # {"status":"ok","role":"landing"}
curl -sSf https://berlin.addrlens.de/health  # {"status":"ok"}
curl -sSf https://berlin.addrlens.de/ready   # {"status":"ready","city":"berlin"}
curl -sSf https://hamburg.addrlens.de/health # (unchanged)
```

### 11.4 `ops/cloudflared/README.md`

New section "Landing subdomain (apex)" — mirrors the Hamburg section, documents `addrlens.de` → `app-landing:8000` with `HTTP Host Header: addrlens.de`.

Reorder: the doc currently shows apex as Berlin. **Rewrite apex block to point at `app-landing:8000`; add new "Berlin subdomain" section pointing at `app:8001`.**

## 12. Cloudflare Tunnel + Redirect Rule

### 12.1 Tunnel public hostnames (final state)

| Hostname | Service |
|---|---|
| `addrlens.de` | `http://app-landing:8000` |
| `berlin.addrlens.de` | `http://app:8001` |
| `hamburg.addrlens.de` | `http://app-hh:8002` |

Each with matching `HTTP Host Header` in CF Additional Application Settings.

### 12.2 Redirect Rule (Cloudflare dashboard → Rules → Redirect Rules)

**Rule name:** `apex → berlin for legacy paths`

**Expression:**
```
(http.host eq "addrlens.de"
 and not http.request.uri.path in {"/" "/impressum" "/datenschutzerklaerung" "/robots.txt" "/sitemap.xml" "/health"}
 and not http.request.uri.path in {"/static/img/logo.png" "/static/img/og-image.jpg"
                                    "/static/img/berlin-card.png"
                                    "/static/img/hamburg-card.png"
                                    "/static/landing.css"}
 and not starts_with(http.request.uri.path, "/static/fonts/")
 and not http.request.uri.path eq "/static/landing.css")
```

**Action:** Dynamic redirect
- **Expression:** `concat("https://berlin.addrlens.de", http.request.uri.path)`
- **Status:** `301`
- **Preserve query string:** ✓

**Why the tightened `/static/*` handling:** legacy inbound links + social crawlers may still point at `https://addrlens.de/static/img/hero/berlin.png`, `/static/app.js`, `/static/modules/compare.js`, `/static/img/city-outlines/*` etc. — Berlin's assets served from the old apex. A blanket `not starts_with(/static/)` allow would 404 those (landing's `/static/` mount only has 5 files). Explicit landing allow-list + fallthrough for other `/static/*` → 301 to `berlin.addrlens.de/static/*` keeps every legacy asset URL working.

This catches `/api/lookup`, `/api/suggest`, `/api/amenities`, `/api/noise`, `/api/history`, `/api/config`, `/api/lens_insight`, `/ready`, and everything else the app defines — without needing to enumerate them. Fail-safe: new app paths auto-redirect.

**Coupling warning:** the deny-list here is coupled to §7's landing static-asset filenames. If a filename is added or renamed in `web/landing/static/`, this rule must be updated in the same PR. Mitigation: `web/landing/README.md` (see §21 recommendations) names both surfaces.

## 13. SEO Migration

1. **Google Search Console:**
   - Add new property `https://berlin.addrlens.de/` (DNS or HTML-tag verification).
   - Submit new sitemap `https://berlin.addrlens.de/sitemap.xml`.
   - Old property `https://addrlens.de/` stays — landing sitemap will re-verify it.
   - **GSC "Change of Address" tool: skip.** The tool requires the old property to fully 301-redirect to the new. Not the case here — apex keeps serving landing + legal pages. 301s on non-landing paths + separate GSC properties do the same job the tool would attempt.
2. **Umami (analytics):** create **three separate Umami websites** (`addrlens.de`, `berlin.addrlens.de`, `hamburg.addrlens.de`), each with its own website ID. The app already supports per-city env suffix (`app/main.py:122` reads `UMAMI_WEBSITE_ID_<CITY>` with fallback to `UMAMI_WEBSITE_ID`). Landing follows the same pattern with `_LANDING` suffix. Prod `.env.production` gains:
   ```
   UMAMI_WEBSITE_ID_BERLIN=<existing-id>     # if not already using suffix form, migrate
   UMAMI_WEBSITE_ID_HAMBURG=<new-id>         # if not already set
   UMAMI_WEBSITE_ID_LANDING=<new-id>         # new
   ```
   No docker-compose `environment:` overrides needed — each container reads its own suffix. **Cutover step:** create the two new Umami websites (landing + hamburg if missing) before flipping CF Tunnel; add the new env vars to `.env.production`. If prod still uses the flat `UMAMI_WEBSITE_ID` (fallback), rename to `UMAMI_WEBSITE_ID_BERLIN` in the same edit so the fallback doesn't accidentally serve Berlin's ID to landing.
3. **Expected timeline:** 2-4 weeks for Google to catch up on canonicals + reallocate authority. Traffic dip 5-15% during transition is normal for subdomain moves.

## 14. Testing

1. **Import guard test** — `tests/landing/test_import_isolation.py` (see §6.2). Runs in CI.
2. **Landing route smoke** — new `tests/landing/test_routes.py`: 200 on `/`, `/impressum`, `/datenschutzerklaerung`, `/robots.txt`, `/sitemap.xml`, `/health`. Also asserts landing HTML contains the Berlin + Hamburg city-card links (guards against accidental copy deletion).
3. **HTML validity** — `web/landing/index.html` passes `tidy -e` (add to existing HTML lint job if one exists; else run manually pre-merge).
4. **Local prod-shape smoke** — `docker compose -f docker-compose.yml -f docker-compose.prod.yml up app-landing`, then via `docker compose exec app-landing python -c "..."` on each of `/{,impressum,datenschutzerklaerung,robots.txt,sitemap.xml,health}` (no host-published port, so host-side curl is not an option — see §11.1).
5. **CF Redirect Rule post-cutover smoke** — the scripted loop in §15 step 4. Should also be run once/day for the first week via a manual cron or as a supplementary section of `update.sh`, to catch dashboard-only rule drift.
6. **Cross-browser visual check** — Chrome + Firefox + Safari at 375/768/1024/1440. Playwright optional; manual for MVP.
7. **Reduced-motion check** — DevTools → Rendering → Emulate CSS `prefers-reduced-motion: reduce`; verify no motion.
8. **Contrast audit** — Chrome DevTools Lighthouse or manual axe run.
9. **Umami-injection smoke** — set `UMAMI_WEBSITE_ID_LANDING=test-id` + `UMAMI_SCRIPT_URL=http://example/x.js` in a local run; grep the served `/` HTML for both strings. Guards the `_load_index()` injection path.

## 15. Rollout Plan (prod cutover)

**Sequence — non-atomic but low-risk. Total downtime: 0. Total wall-clock: ~15 min.**

1. **Prep (any time):**
   - Merge PR to main. `update.sh` on prod builds all 3 containers.
   - `app-landing` boots on port 8000, healthcheck green. **Not yet public** — no CF hostname points at it.
2. **CF Tunnel — add `berlin.addrlens.de`:**
   - Dashboard → Zero Trust → Networks → Tunnels → `addrlens-prod` → Public Hostnames → Add.
   - `berlin.addrlens.de` → `http://app:8001`, Host header `berlin.addrlens.de`.
   - CF creates proxied CNAME automatically.
   - Verify: `curl -fsS https://berlin.addrlens.de/health` returns `{"status":"ok"}`.
   - **State now:** Berlin app answers on BOTH `addrlens.de` and `berlin.addrlens.de`. Safe overlap.
3. **CF Tunnel — repoint apex:**
   - Edit apex public hostname: change service **only** from `http://app:8001` to `http://app-landing:8000`. Host header stays `addrlens.de` (already correct).
   - Verify: `curl -fsS https://addrlens.de/` returns landing HTML.
   - `curl -fsS https://berlin.addrlens.de/` returns Berlin app (unchanged).
3.5. **Purge CF edge cache for apex:**
   - Cloudflare → Caching → Configuration → Purge Cache → **Custom Purge by URL**.
   - URLs: `https://addrlens.de/`, `https://addrlens.de`, `https://addrlens.de/impressum`, `https://addrlens.de/datenschutzerklaerung`.
   - Rationale: apex HTML may have been cached at edge with the pre-cutover Berlin content. Skipping this leaves users on stale HTML for the TTL window.
4. **Add Redirect Rule** for legacy apex paths (see §12.2). Smoke set (run all before declaring cutover done):
   ```bash
   for path in /api/lookup /api/suggest /api/config /api/lens_insight /ready /static/app.js /static/img/hero/berlin.png; do
     printf '%-40s ' "$path"
     curl -sSI "https://addrlens.de${path}" | awk 'NR==1 || /^location:/i'
   done
   # Expect: HTTP/2 301 + location: https://berlin.addrlens.de<path>
   ```
5. **Update GSC** — add `berlin.addrlens.de` property (DNS or HTML-tag verification), submit sitemap.
6. **Announce** — README + optional social post ("We moved: Berlin now lives at berlin.addrlens.de, apex is a city hub.").

## 16. Rollback Plan

**If landing container is broken at boot:**
- `docker compose … up -d app-landing` fails healthcheck → `update.sh` gate fires → deploy aborts. Berlin apex still served (nothing changed yet at CF layer).

**If landing works but users hate it, or apex regression discovered post-cutover:**
- CF Tunnel: edit apex public hostname → change service back to `http://app:8001`, host header back to `addrlens.de`. Effective within seconds.
- Keep `berlin.addrlens.de` hostname registered (harmless overlap).
- Remove Redirect Rule (or set to "disabled" for the 301 rule).
- Total rollback time: 2-3 minutes, dashboard only, no code deploy.

**If Berlin subdomain (`berlin.addrlens.de`) breaks but apex is fine:**
- Remove `berlin.` public hostname; users can still reach Berlin via apex during the debug window.

## 17. Effort Estimate

| Chunk | Time |
|---|---|
| Landing HTML (index + 2 legal, DE/EN, tokens/CSS) | 3-5h |
| Static assets copy (logo, hero, favicon, og-image reused) | 30m |
| `app/landing/main.py` + import guard test | 45m |
| `web/landing/robots.txt` + `sitemap.xml` | 15m |
| **New `ops/Dockerfile.landing` (minimal deps)** | **30m** |
| `docker-compose.prod.yml` `app-landing` service | 30m |
| Berlin canonical/OG/JSON-LD/sitemap/robots edits | 30m |
| Berlin legal text updates (2 files × 2 langs) | 30m |
| `compare.js` print header edit | 10m |
| CF Tunnel reconfig + Redirect Rule | 1h |
| `update.sh` + `rollback.sh` edits | 45m |
| `ops/cloudflared/README.md` + `ops/deploy/README.md` updates | 45m |
| Prod cutover + verify 3 hosts + 301s | 1.5h |
| GSC property + sitemap submit | 30m |
| **Focused work total** | **~11-15h** |
| SEO stabilization (Google's clock) | 2-4 weeks |

## 18. Risks + Mitigations

| Risk | Mitigation |
|---|---|
| Landing container couples to `app.core` over time → slow cold start | Import-guard test in CI (see 6.2) |
| Rollback omits `app-landing` from build list → stale landing after rollback | Explicit service list in `rollback.sh`; PR-review checklist item |
| Redirect Rule allow-list drifts from actual landing paths | Comment in `web/landing/` README pointing at the CF rule; treat as coupled |
| Google splits authority between apex + berlin, drops rankings | Accept 2-4wk dip; 301s + separate GSC properties minimize loss; monitor Search Console weekly for 4 weeks |
| Umami tracking merges apex + berlin traffic confusingly | Add hostname filter or split into two websites post-cutover |
| Legal duplicate-content flag (impressum on 3 hosts) | Distinct canonical URLs per host; add scoped preamble ("This imprint covers the addrlens.de landing page. For Berlin app, see berlin.addrlens.de/impressum.") — 15min copy work |
| `Dockerfile.landing` fastapi/uvicorn pins drift from app's `pyproject.toml` → two versions in prod | Comment above the `uv pip install` line in `Dockerfile.landing` naming the sync obligation; optional CI grep-check; landing dep set is tiny so drift caught in code review |
| Landing goes down → apex 502s | Same failure model as any origin; healthcheck + `restart: unless-stopped` covers container crash |

## 19. Decisions (resolved)

1. **Address counts on city cards:** **removed from scope.** Landing subline uses soft copy (EN: "Address compare · Life-situation lens" / DE: "Adressvergleich · Lebenslagen-Linsen"). No `CityConfig.public_address_count` field, no build-time bake. Not deferred to v2 — dropped entirely; if counts ever wanted, revisit as a fresh spec.
2. **Roadmap teaser line:** **skipped.** Landing shows only cities live today. Adding a city = editing the city-cards grid; no roadmap promises to keep in sync.
3. **`og-image.jpg`:** **reuse existing `web/static/img/og-image.jpg`.** Copied verbatim to `web/landing/static/img/og-image.jpg`.
4. **Analytics:** **three separate Umami websites** (`addrlens.de`, `berlin.addrlens.de`, `hamburg.addrlens.de`), wired via `UMAMI_WEBSITE_ID_{LANDING,BERLIN,HAMBURG}` env vars — see §13.
5. **Primary language:** **English default**, DE toggle (reverses city-app DE-default convention). Rationale: landing is the expat-facing discovery surface. See §8.3.
6. **Footer GitHub link:** **removed.** Footer carries Imprint + Privacy only. Rationale: reduce apex chrome, no confusion for non-technical visitors; project code remains discoverable via search.

## 20. Out of scope (deferred to future spec)

- Munich, Cologne onboarding (existing `docs/onboarding-a-new-city.md` covers city addition; landing card add is 20-line diff per city).
- Landing v2: dynamic address counts, "recently updated" data-freshness badge, city screenshots.
- Landing blog / changelog page.
- Dark mode support on landing (city apps also don't have it).
- Consolidated `sitemap_index.xml` across all 3 hosts (mild SEO win; not blocking).
- Playwright visual-diff smoke across all 3 hostnames at 375+1440 (nice-to-have; MVP is manual cross-browser check per §14).
- Codifying the CF Redirect Rule as YAML in `ops/cloudflared/redirect-rules.yaml` (source-of-truth for a dashboard-only rule; adds maintenance surface — defer unless the rule drifts in practice).

## 21. Follow-ups from code review (2026-09-25)

Spec revised in place. Below are the deferred items the reviewer surfaced — none block implementation, but capture them so the plan writer or a future edit doesn't lose them:

1. **`web/landing/README.md`** — a one-page README under `web/landing/` naming (a) the files, (b) the coupling with the CF Redirect Rule's landing allow-list (see §12.2), (c) "how to add a city card". Included in the "Landing HTML" chunk of §17 effort estimate.
2. **CF Redirect Rule YAML mirror** (deferred — see §20).
3. **Playwright cross-hostname visual diff** (deferred — see §20).
4. **CI grep-check for fastapi/uvicorn version sync** across `pyproject.toml` + `ops/Dockerfile.landing` — nice-to-have per §10.1, not blocking.
