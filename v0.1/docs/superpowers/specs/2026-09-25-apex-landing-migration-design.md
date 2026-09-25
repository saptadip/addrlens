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
# Symmetric with app/main.py:122 — prefer the LANDING-suffixed env,
# fall back to the flat name. Prevents accidental collision with
# per-city Umami IDs.
def _load_index() -> bytes:
    html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
    umami_id = (os.environ.get("UMAMI_WEBSITE_ID_LANDING")
                or os.environ.get("UMAMI_WEBSITE_ID", "")).strip()
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
    return JSONResponse({"status": "ok", "role": "landing"})
```

### 6.2 Import guard test — `tests/landing/test_import_isolation.py`

Enforce the "minimal imports" rule so future edits don't silently couple landing to `app.core`:

```python
import sys
import importlib

def test_landing_does_not_import_app_core():
    # Fresh import to detect coupling introduced later.
    for mod in list(sys.modules):
        if mod.startswith("app."):
            del sys.modules[mod]
    importlib.import_module("app.landing.main")
    coupled = [m for m in sys.modules if m.startswith(("app.core", "app.cities", "app.routes"))]
    assert not coupled, (
        f"app.landing must stay minimal; imported: {coupled}. "
        "Landing exists to be snappy — do not reach for city helpers here."
    )
```

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
│  [logo.png] AddrLens                             [DE | EN] │  <- header, sticky (h=64px)
├────────────────────────────────────────────────────────────┤
│                                                            │
│       Straßen-Intelligenz für deutsche Städte             │  <- hero H1 (Space Grotesk)
│                                                            │
│       Frei zugängliche Daten, sauber verknüpft.           │  <- tagline (Inter 400, muted)
│       Wähle deine Stadt.                                   │
│                                                            │
├────────────────────────────────────────────────────────────┤
│                                                            │
│   ┌──────────────────────┐    ┌──────────────────────┐   │
│   │ [berlin-card.png]    │    │ [hamburg-card.png]   │   │  <- city cards (2-col ≥768px,
│   │                      │    │                      │   │     1-col <768px)
│   │  Berlin       ● Live │    │  Hamburg      ● Live │   │
│   │  Adressvergleich ·   │    │  Adressvergleich ·   │   │  <- subline (Inter 500)
│   │  Lebenslagen-Linsen  │    │  Lebenslagen-Linsen  │   │
│   │  → berlin.addrlens.de│    │  → hamburg.addrlens.de│  │  <- CTA link
│   └──────────────────────┘    └──────────────────────┘   │
│                                                            │
├────────────────────────────────────────────────────────────┤
│  Impressum · Datenschutz · GitHub          © 2026 sapta   │  <- footer
└────────────────────────────────────────────────────────────┘
```

**Notes:**
- City card image = the existing `web/static/img/hero/{city}.png` hero illustration — same visual users see when they land inside each city app. Zero visual break on click-through.
- "Live" badge = `--brand` filled dot + `● Live` in Inter 500, 12px.
- Subline uses soft copy ("Adressvergleich · Lebenslagen-Linsen") for MVP — no dynamic numbers, no build-time coupling to `CityConfig`. Address counts removed from scope (see §19).
- **No roadmap teaser line** — landing shows only cities that are live today (see §19). New cities are added by editing the city-cards grid, not by promising future work.

### 8.3 i18n toggle

Same pattern as city apps: DE default, EN toggle. Two independent HTML fragments in one file, JS toggles `hidden` attribute on `[data-lang]` wrappers. State persists in `localStorage['addrlens.lang']`. No i18n framework.

```html
<div data-lang="de">…German copy…</div>
<div data-lang="en" hidden>…English copy…</div>
<button id="lang-toggle" type="button">EN</button>
<script>
  const KEY = 'addrlens.lang';
  const stored = localStorage.getItem(KEY) || 'de';
  document.documentElement.lang = stored;
  document.querySelectorAll('[data-lang]').forEach(el => {
    el.hidden = el.dataset.lang !== stored;
  });
  document.getElementById('lang-toggle').textContent = stored === 'de' ? 'EN' : 'DE';
  document.getElementById('lang-toggle').addEventListener('click', () => {
    const next = document.documentElement.lang === 'de' ? 'en' : 'de';
    document.documentElement.lang = next;
    localStorage.setItem(KEY, next);
    document.querySelectorAll('[data-lang]').forEach(el => {
      el.hidden = el.dataset.lang !== next;
    });
    document.getElementById('lang-toggle').textContent = next === 'de' ? 'EN' : 'DE';
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
<meta property="og:title" content="AddrLens — Straßen-Intelligenz für deutsche Städte">
<meta property="og:description" content="Frei zugängliche Daten, sauber verknüpft. Berlin und Hamburg live.">
<meta property="og:image" content="https://addrlens.de/static/img/og-image.jpg">
<meta name="twitter:card" content="summary_large_image">
<link rel="alternate" hreflang="de-DE" href="https://addrlens.de/">
<link rel="alternate" hreflang="en-GB" href="https://addrlens.de/">
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
- [ ] `<html lang="de">` set + updates on toggle
- [ ] Alt text on all imgs (`alt="Berlin Skyline"`, `alt="Hamburg Skyline"`, `alt=""` on decorative logo when text follows)

## 9. Berlin App Changes (`web/*` — non-hamburg)

Text/URL surgery, no logic changes:

| File | Change |
|---|---|
| `web/index.html` | `og:url`, `canonical`, both `hreflang`, JSON-LD `url`, `og:image`, `twitter:image` → `https://berlin.addrlens.de/…` |
| `web/impressum.html` | 4 occurrences of `addrlens.de` in link text + href → `berlin.addrlens.de` (both DE + EN sections). Email `sapta@addrlens.de` unchanged (apex email routing preserved). |
| `web/datenschutzerklaerung.html` | Same shape as impressum: website URL refs → `berlin.addrlens.de`, email unchanged. |
| `web/sitemap.xml` | All 3 `<loc>` entries → `https://berlin.addrlens.de/…` |
| `web/robots.txt` | Sitemap line → `https://berlin.addrlens.de/sitemap.xml` |
| `web/static/modules/compare.js` | `print-header-site` string `addrlens.de` → `berlin.addrlens.de` (or keep as brand — see decision below) |

**`compare.js` print-header decision:** print header appears on lens-comparison PDF exports. Users read this offline; the brand string helps them find the site again. **Change to `berlin.addrlens.de`** — that's where the app that made the PDF actually lives. Matches truth-in-labelling.

Hamburg pages (`web/hamburg/*`) already correct — no change.

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
RUN uv pip install --system --no-cache \
        "fastapi>=0.110" "uvicorn[standard]>=0.29"

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
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)" || exit 1

CMD ["uvicorn", "app.landing.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Version-alignment discipline:** the `fastapi` + `uvicorn` pins in this Dockerfile must be kept in sync with the versions resolved from `pyproject.toml` for the app image. Drift = same code running against two versions in prod. Add a comment above the `uv pip install` line: `# Sync with pyproject.toml [project.dependencies]`. Optional: add a CI check that greps both files for version match — nice-to-have, not blocking.

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
      - addrlens

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
    svc="${svc_port%:*}"
    port="${svc_port#*:}"
    …
    case "$svc" in
      app)     ADDR=$("${COMPOSE[@]}" exec -T "$svc" python -c "from app.cities.berlin import BERLIN; print(BERLIN.smoke_address)") ;;
      app-hh)  ADDR=$("${COMPOSE[@]}" exec -T "$svc" python -c "from app.cities.hamburg import HAMBURG; print(HAMBURG.smoke_address)") ;;
+     app-landing)
+       # Landing has no lookup — health-only smoke.
+       curl -fsS "http://127.0.0.1:${port}/health" >/dev/null && continue
+       ;;
    esac
    …
  done
```

Landing smoke = `/health` only, no address lookup. Branch cleanly to `continue` before the address-based smoke block.

### 11.2 `ops/deploy/rollback.sh`

```diff
- "${COMPOSE[@]}" build app app-hh inference
+ "${COMPOSE[@]}" build app app-hh app-landing inference
```

Same footgun class as the Hamburg-omission fix. Explicit list keeps it obvious.

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
 and not starts_with(http.request.uri.path, "/static/"))
```

**Action:** Dynamic redirect
- **Expression:** `concat("https://berlin.addrlens.de", http.request.uri.path)`
- **Status:** `301`
- **Preserve query string:** ✓

This catches `/api/*`, `/lookup*`, `/ready`, `/lens-insight*`, and anything else the app defines — without needing to enumerate them. Fail-safe: new app paths auto-redirect.

## 13. SEO Migration

1. **Google Search Console:**
   - Add new property `https://berlin.addrlens.de/` (DNS or HTML-tag verification).
   - Submit new sitemap `https://berlin.addrlens.de/sitemap.xml`.
   - Old property `https://addrlens.de/` stays — landing sitemap will re-verify it.
   - GSC "Change of Address" tool **does not support subdomain moves** — skip. 301s + separate properties do the same job.
2. **Umami (analytics):** create **three separate Umami websites** (`addrlens.de`, `berlin.addrlens.de`, `hamburg.addrlens.de`), each with its own website ID. The app already supports per-city env suffix (`app/main.py:122` reads `UMAMI_WEBSITE_ID_<CITY>` with fallback to `UMAMI_WEBSITE_ID`). Landing follows the same pattern with `_LANDING` suffix. Prod `.env.production` gains:
   ```
   UMAMI_WEBSITE_ID_BERLIN=<existing-id>     # if not already using suffix form, migrate
   UMAMI_WEBSITE_ID_HAMBURG=<new-id>         # if not already set
   UMAMI_WEBSITE_ID_LANDING=<new-id>         # new
   ```
   No docker-compose `environment:` overrides needed — each container reads its own suffix. **Cutover step:** create the two new Umami websites (landing + hamburg if missing) before flipping CF Tunnel; add the new env vars to `.env.production`. If prod still uses the flat `UMAMI_WEBSITE_ID` (fallback), rename to `UMAMI_WEBSITE_ID_BERLIN` in the same edit so the fallback doesn't accidentally serve Berlin's ID to landing.
3. **Expected timeline:** 2-4 weeks for Google to catch up on canonicals + reallocate authority. Traffic dip 5-15% during transition is normal for subdomain moves.

## 14. Testing

1. **Import guard test** — `tests/landing/test_import_isolation.py` (see 6.2). Runs in CI.
2. **Landing route smoke** — new `tests/landing/test_routes.py`: 200 on `/`, `/impressum`, `/datenschutzerklaerung`, `/robots.txt`, `/sitemap.xml`, `/health`.
3. **HTML validity** — `web/landing/index.html` passes `tidy -e` (add to existing HTML lint job if one exists; else run manually pre-merge).
4. **Local prod-shape smoke** — `docker compose -f docker-compose.yml -f docker-compose.prod.yml up app-landing`, then `curl -fsS http://localhost:8000/{,impressum,datenschutzerklaerung,robots.txt,sitemap.xml,health}`.
5. **Cross-browser visual check** — Chrome + Firefox + Safari at 375/768/1024/1440. Playwright optional; manual for MVP.
6. **Reduced-motion check** — DevTools → Rendering → Emulate CSS `prefers-reduced-motion: reduce`; verify no motion.
7. **Contrast audit** — Chrome DevTools Lighthouse or manual axe run.

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
   - Edit apex public hostname: change service from `http://app:8001` to `http://app-landing:8000`, host header to `addrlens.de`.
   - Verify: `curl -fsS https://addrlens.de/` returns landing HTML.
   - `curl -fsS https://berlin.addrlens.de/` returns Berlin app (unchanged).
4. **Add Redirect Rule** for legacy apex paths (see 12.2). Test with `curl -sSI https://addrlens.de/api/lookup` — expect `301` to `berlin.addrlens.de`.
5. **Update GSC** — add `berlin.addrlens.de` property, submit sitemap.
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

1. **Address counts on city cards:** **removed from scope.** Landing subline uses soft copy ("Adressvergleich · Lebenslagen-Linsen"). No `CityConfig.public_address_count` field, no build-time bake. Not deferred to v2 — dropped entirely; if counts ever wanted, revisit as a fresh spec.
2. **Roadmap teaser line:** **skipped.** Landing shows only cities live today. Adding a city = editing the city-cards grid; no roadmap promises to keep in sync.
3. **`og-image.jpg`:** **reuse existing `web/static/img/og-image.jpg`.** Copied verbatim to `web/landing/static/img/og-image.jpg`.
4. **Analytics:** **three separate Umami websites** (`addrlens.de`, `berlin.addrlens.de`, `hamburg.addrlens.de`), wired via `UMAMI_WEBSITE_ID_{LANDING,BERLIN,HAMBURG}` env vars — see §13.

## 20. Out of scope (deferred to future spec)

- Munich, Cologne onboarding (existing `docs/onboarding-a-new-city.md` covers city addition; landing card add is 20-line diff per city).
- Landing v2: dynamic address counts, "recently updated" data-freshness badge, city screenshots.
- Landing blog / changelog page.
- Dark mode support on landing (city apps also don't have it).
- Consolidated `sitemap_index.xml` across all 3 hosts (mild SEO win; not blocking).
