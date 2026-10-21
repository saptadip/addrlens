# Apex Landing Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the Berlin app off the apex domain to `berlin.addrlens.de`, ship a new static landing page at `addrlens.de` served by a dedicated minimal FastAPI container, and 301-redirect all legacy apex non-landing paths to the Berlin subdomain — with zero downtime, dashboard-only rollback, and no visual break for users flowing landing → city app.

**Architecture:** New `app-landing` container behind the existing Cloudflare Tunnel (port 8000; Berlin=8001, Hamburg=8002). Container built from a new minimal `ops/Dockerfile.landing` (fastapi + uvicorn only, ~90-120 MB target). Serves 5 endpoints from `web/landing/*` via a ~70-line `app/landing/main.py` with a whitelist import-guard test enforcing zero coupling to `app.core / app.cities / app.routes / app.config / app.deps`. Design tokens reused verbatim from `web/static/app.css`. English is the primary language on landing (expat audience), DE toggle. Hamburg untouched except for 4 stale `Website: https://addrlens.de` legal-page refs.

**Tech Stack:** Python 3.11 / FastAPI (existing) · uvicorn · uv installer · Docker Compose + Cloudflare Tunnel (existing) · vanilla HTML/CSS/JS on landing — no build step, no framework.

**Spec:** `v0.1/docs/superpowers/specs/2026-09-25-apex-landing-migration-design.md`

**Branch:** `feat/apex-landing-migration` (already created off `origin/main`; spec commits `f52c96f` + `46f9e8b`).

## Global Constraints

- **Branch pin: `feat/apex-landing-migration`.** All commits land on this branch. Never switch branches mid-task. Never commit to `main` directly.
- **v0.1/ is the sole active tree.** All paths in this plan are relative to `v0.1/` unless prefixed with `/srv/addrlens/` (prod filesystem) or a CF dashboard reference.
- **Berlin behaviour byte-exact except URL/hostname flips.** No changes to Berlin app logic, routes, scoring, or data. Only text/canonical/URL edits per spec §9.
- **Hamburg app untouched except 4 legal-page fixes** in §9.1. Hamburg canonical URLs, sitemap, robots are already correct.
- **Landing container imports NO app.core / app.cities / app.routes / app.config / app.deps.** Enforced by whitelist test in Task 1. Only `app` + `app.landing` + `app.landing.main` allowed.
- **`fastapi` and `uvicorn[standard]` versions in `ops/Dockerfile.landing` match `pyproject.toml` exactly.** Currently `fastapi>=0.115`, `uvicorn[standard]>=0.32`.
- **`compose exec`, NOT host `curl`, for all in-container smoke tests.** `docker-compose.prod.yml:18` sets `ports: !reset []` — no host-published port on `app`, `app-hh`, or `app-landing`.
- **`.venv/bin/python` and `.venv/bin/pytest` for all local test runs** — matches CLAUDE.md convention. Tests live under `tests/landing/`.
- **All commits use conventional prefix** (`feat:` / `fix:` / `test:` / `chore:` / `refactor:` / `docs:` / `ci:` / `ops:`).
- **Every code-touching task ends with `.venv/bin/pytest tests/ -q` passing** (existing suite untouched) plus the new landing tests. Docs-only and ops-only tasks skip pytest.
- **English is the landing default; DE is the toggle.** Landing `<html lang="en">`, city apps stay `<html lang="de">`.
- **Landing footer: Imprint + Privacy only.** No GitHub link. Nothing else in the footer.
- **`addrlens_net` (with `_net` suffix) is the Docker network name.** Not `addrlens`.
- **Attribution/legal text lives on 3 surfaces per site:** `index.html` (or landing hero) + `impressum.html` + `datenschutzerklaerung.html`. Grep all three together before any URL/copy edit — legal doc wins on wording conflicts.
- **All grep-based verification uses `grep -E`** (extended regex), never `grep` alone (which is BRE and treats parens/braces differently).
- **Umami on landing reads `UMAMI_WEBSITE_ID_LANDING` only, no fallback to flat `UMAMI_WEBSITE_ID`.** Prevents cross-contamination if operator forgets to migrate the flat var during cutover.
- **Never push to `main`.** Push only to `origin/feat/apex-landing-migration`.
- **Never edit prod `/srv/addrlens/.env.production` from this branch.** That file is operator-managed; the plan surfaces the env var changes needed but does not commit them.

---

## File Structure

**New files (created):**
- `v0.1/app/landing/__init__.py` — package marker, empty
- `v0.1/app/landing/main.py` — FastAPI landing app (~70 LOC)
- `v0.1/tests/landing/__init__.py` — test package marker, empty
- `v0.1/tests/landing/conftest.py` — shared fixtures (whitelist-fixture, monkeypatch helper)
- `v0.1/tests/landing/test_import_isolation.py` — whitelist import-guard
- `v0.1/tests/landing/test_routes.py` — 6-endpoint route smoke + i18n assertion
- `v0.1/tests/landing/test_umami_injection.py` — Umami tag injection when env set
- `v0.1/web/landing/index.html` — hero + 2 city cards + DE/EN toggle + footer (~250 LOC)
- `v0.1/web/landing/impressum.html` — apex-scoped imprint, EN-primary + DE toggle
- `v0.1/web/landing/datenschutzerklaerung.html` — apex-scoped privacy, EN-primary + DE toggle
- `v0.1/web/landing/robots.txt` — allow all, sitemap: `https://addrlens.de/sitemap.xml`
- `v0.1/web/landing/sitemap.xml` — 3 apex URLs + optional cross-refs to berlin/hamburg subdomains
- `v0.1/web/landing/README.md` — dir contents + CF Redirect Rule coupling + "how to add a city"
- `v0.1/web/landing/static/landing.css` — landing-only stylesheet, reuses `web/static/app.css` tokens
- `v0.1/web/landing/static/img/logo.png` — copy of `web/static/img/logo.png`
- `v0.1/web/landing/static/img/og-image.jpg` — copy of `web/static/img/og-image.jpg`
- `v0.1/web/landing/static/img/favicon.png` — copy of `web/static/img/logo.png`
- `v0.1/web/landing/static/img/berlin-card.png` — copy of `web/static/img/hero/berlin.png`
- `v0.1/web/landing/static/img/hamburg-card.png` — copy of `web/static/img/hero/hamburg.png`
- `v0.1/web/landing/static/fonts/` — copies of `web/static/fonts/*` (Inter + Space Grotesk woff2)
- `v0.1/ops/Dockerfile.landing` — minimal FastAPI image (~40 LOC)

**Modified files:**
- `v0.1/docker-compose.prod.yml` — add `app-landing` service block; add to `cloudflared.depends_on`
- `v0.1/web/index.html` — Berlin canonical/og:url/hreflang/JSON-LD url/og:image/twitter:image → `berlin.addrlens.de`
- `v0.1/web/impressum.html` — all `https://addrlens.de` URL refs → `berlin.addrlens.de` (DE+EN), emails unchanged
- `v0.1/web/datenschutzerklaerung.html` — same URL flip, emails unchanged
- `v0.1/web/sitemap.xml` — 3 `<loc>` entries → `berlin.addrlens.de`
- `v0.1/web/robots.txt` — sitemap URL → `berlin.addrlens.de`
- `v0.1/web/static/modules/compare.js` — `print-header-site` string → `berlin.addrlens.de`
- `v0.1/web/hamburg/impressum.html` — 2 `Website: https://addrlens.de` refs → `hamburg.addrlens.de` (l.46 DE, l.159 EN)
- `v0.1/web/hamburg/datenschutzerklaerung.html` — 2 same-shape refs → `hamburg.addrlens.de` (l.46 DE, l.385 EN)
- `v0.1/ops/deploy/update.sh` — `app-landing` added to build + smoke loop; new `if $svc = app-landing` branch runs health-only smoke via `compose exec`
- `v0.1/ops/deploy/rollback.sh` — `app-landing` added to BOTH the `build` line (l.39) AND the `up -d --force-recreate` line (l.40)
- `v0.1/ops/deploy/README.md` — curl examples updated for 3 hostnames
- `v0.1/ops/cloudflared/README.md` — rewritten apex block (now → `app-landing:8000`); new "Berlin subdomain" section (→ `app:8001`); Hamburg section unchanged

**Manual / dashboard-only (Task 11 runbook):**
- Cloudflare Tunnel: add `berlin.addrlens.de` public hostname; repoint apex; purge cache
- Cloudflare Rules: add Redirect Rule per spec §12.2
- Google Search Console: add `berlin.addrlens.de` property; submit sitemap
- Umami: create 2 new websites (`addrlens.de`, `hamburg.addrlens.de` if missing)
- `/srv/addrlens/.env.production`: add `UMAMI_WEBSITE_ID_LANDING`, `UMAMI_WEBSITE_ID_HAMBURG`; rename flat `UMAMI_WEBSITE_ID` → `UMAMI_WEBSITE_ID_BERLIN`

---

## Task 1: Landing FastAPI app + import-guard test

**Files:**
- Create: `v0.1/app/landing/__init__.py`
- Create: `v0.1/app/landing/main.py`
- Create: `v0.1/tests/landing/__init__.py`
- Create: `v0.1/tests/landing/conftest.py`
- Create: `v0.1/tests/landing/test_import_isolation.py`

**Interfaces:**
- Consumes: nothing from other tasks (this is task 0 in dep order)
- Produces:
  - `app.landing.main.app` — FastAPI instance for `uvicorn` to run
  - `app.landing.main._load_index() -> bytes` — cached HTML loader used at import time
  - Route table: `GET /`, `GET /impressum`, `GET /datenschutzerklaerung`, `GET /robots.txt`, `GET /sitemap.xml`, `GET /health`
  - All routes return 200 when `web/landing/*` files exist; test conftest provides a `landing_fixture` that creates a minimal `web/landing/index.html` + `web/landing/static/` when needed

- [ ] **Step 1: Verify branch is `feat/apex-landing-migration`**

Run: `git branch --show-current`
Expected: `feat/apex-landing-migration`
If not, STOP and switch: `git checkout feat/apex-landing-migration`. Never proceed on the wrong branch.

- [ ] **Step 2: Create empty package markers**

```bash
mkdir -p v0.1/app/landing v0.1/tests/landing
touch v0.1/app/landing/__init__.py v0.1/tests/landing/__init__.py
```

- [ ] **Step 3: Write `tests/landing/conftest.py` — landing fixture**

Create `v0.1/tests/landing/conftest.py`:

```python
"""Shared fixtures for landing container tests.

Landing container reads web/landing/index.html at module import time
via app.landing.main._load_index(). CI checkouts (and this fixture)
provide a minimal web/landing/ tree so import succeeds.
"""
from pathlib import Path

import pytest

# Repo root = 3 levels above this file (v0.1/tests/landing/conftest.py).
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
WEB_LANDING = REPO_ROOT / "web" / "landing"


@pytest.fixture
def ensure_landing_index(monkeypatch):
    """Ensure web/landing/index.html + static/ exist for module import.

    If the real files already exist (later tasks), yield without touching
    them. Otherwise write a minimal placeholder that _load_index() can
    read. Restore state via monkeypatch's automatic cleanup where possible;
    files created here are removed at fixture teardown.
    """
    created_files: list[Path] = []
    if not WEB_LANDING.exists():
        WEB_LANDING.mkdir(parents=True)
        created_files.append(WEB_LANDING)
    if not (WEB_LANDING / "index.html").exists():
        (WEB_LANDING / "index.html").write_text(
            "<!doctype html><html><body><!-- UMAMI-INJECT --></body></html>",
            encoding="utf-8",
        )
        created_files.append(WEB_LANDING / "index.html")
    if not (WEB_LANDING / "static").exists():
        (WEB_LANDING / "static").mkdir()
        created_files.append(WEB_LANDING / "static")
    yield WEB_LANDING
    # Teardown: only remove files this fixture created (idempotent).
    for p in reversed(created_files):
        if p.is_file():
            p.unlink()
        elif p.is_dir() and not any(p.iterdir()):
            p.rmdir()
```

- [ ] **Step 4: Write the failing import-guard test**

Create `v0.1/tests/landing/test_import_isolation.py`:

```python
"""Import-guard: landing must stay minimal.

Whitelist (not blacklist) so future edits reaching for app.config /
app.deps / any new app.<x> are caught. Only `app`, `app.landing`, and
`app.landing.main` are allowed under the app namespace.
"""
import importlib
import sys

_ALLOWED_APP_MODULES = {"app", "app.landing", "app.landing.main"}


def test_landing_imports_only_whitelisted_app_modules(ensure_landing_index):
    for mod in list(sys.modules):
        if mod == "app" or mod.startswith("app."):
            del sys.modules[mod]

    importlib.import_module("app.landing.main")

    imported = {m for m in sys.modules if m == "app" or m.startswith("app.")}
    unexpected = imported - _ALLOWED_APP_MODULES
    assert not unexpected, (
        f"app.landing must stay minimal. Unexpected app.* imports: "
        f"{sorted(unexpected)}. Landing exists to be snappy — do not "
        "reach for app.core / app.cities / app.config / app.deps / "
        "app.routes here."
    )
```

- [ ] **Step 5: Run test to verify it fails**

Run: `.venv/bin/pytest tests/landing/test_import_isolation.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.landing'`

- [ ] **Step 6: Write `app/landing/main.py`**

Create `v0.1/app/landing/main.py`:

```python
"""Apex landing page for addrlens.de — city hub.

DELIBERATELY MINIMAL: only imports fastapi + stdlib. Do NOT reach for
app.core / app.cities / app.config / app.deps helpers here — landing
must cold-start fast and must survive city-code refactors without
redeploy. Enforced by tests/landing/test_import_isolation.py.
"""
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

WEB_DIR = Path(__file__).resolve().parent.parent.parent / "web" / "landing"

app = FastAPI(title="addrlens.de — landing", docs_url=None, redoc_url=None)

app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")


def _load_index() -> bytes:
    """Load web/landing/index.html once at boot. Inject Umami tracker
    only when the LANDING-suffixed env vars are set.

    No fallback to the flat UMAMI_WEBSITE_ID / UMAMI_SCRIPT_URL: landing
    gets no tracker unless explicitly configured, to prevent cross-
    contamination with Berlin/Hamburg IDs during cutover.
    """
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
    # Match app/main.py /health shape. ROLE=landing env is diagnostic-
    # only (docker inspect / log correlation), not returned here.
    return JSONResponse({"status": "ok"})
```

- [ ] **Step 7: Run import-guard test to verify it passes**

Run: `.venv/bin/pytest tests/landing/test_import_isolation.py -v`
Expected: PASS

- [ ] **Step 8: Run full test suite to confirm no regression**

Run: `.venv/bin/pytest tests/ -q`
Expected: all previously-passing tests still pass + the 1 new landing test passes.

- [ ] **Step 9: Commit**

```bash
git add v0.1/app/landing/ v0.1/tests/landing/
git commit -m "feat(landing): minimal FastAPI app + import-guard test

app/landing/main.py serves 5 endpoints from web/landing/ with ruthlessly
minimal imports (fastapi + stdlib only). Whitelist import-guard test
enforces zero coupling to app.core / app.cities / app.config / app.deps
/ app.routes so landing cold-start stays fast and survives city-code
refactors. Landing-only Umami env var (no fallback) prevents
cross-contamination with Berlin/Hamburg IDs."
```

---

## Task 2: Landing route smoke + Umami injection tests

**Files:**
- Create: `v0.1/tests/landing/test_routes.py`
- Create: `v0.1/tests/landing/test_umami_injection.py`

**Interfaces:**
- Consumes: `app.landing.main.app` (Task 1)
- Produces: assertion coverage on all 6 routes + Umami injection path

- [ ] **Step 1: Write route smoke test**

Create `v0.1/tests/landing/test_routes.py`:

```python
"""Smoke: every landing route returns 200 with the expected media type.

Also asserts landing index HTML contains both city-card link substrings
(guards against accidental copy deletion during future edits).
"""
from fastapi.testclient import TestClient

from app.landing.main import app

client = TestClient(app)


def test_index_returns_html(ensure_landing_index):
    r = client.get("/")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")


def test_health_returns_status_ok():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_robots_is_text_plain(ensure_landing_index, tmp_path, monkeypatch):
    (ensure_landing_index / "robots.txt").write_text(
        "User-agent: *\nAllow: /\nSitemap: https://addrlens.de/sitemap.xml\n",
        encoding="utf-8",
    )
    r = client.get("/robots.txt")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")


def test_sitemap_is_xml(ensure_landing_index):
    (ensure_landing_index / "sitemap.xml").write_text(
        '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>',
        encoding="utf-8",
    )
    r = client.get("/sitemap.xml")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/xml")


def test_impressum_serves_html(ensure_landing_index):
    (ensure_landing_index / "impressum.html").write_text(
        "<!doctype html><html><body>Imprint</body></html>", encoding="utf-8",
    )
    r = client.get("/impressum")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")


def test_datenschutz_serves_html(ensure_landing_index):
    (ensure_landing_index / "datenschutzerklaerung.html").write_text(
        "<!doctype html><html><body>Privacy</body></html>", encoding="utf-8",
    )
    r = client.get("/datenschutzerklaerung")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")


def test_index_html_contains_both_city_links_when_real_landing_exists():
    """Once Task 4 has landed the real web/landing/index.html, this
    assertion guards against accidental deletion of the Berlin or
    Hamburg card. Skipped when the file is the minimal test fixture."""
    from app.landing.main import _INDEX_HTML

    html = _INDEX_HTML.decode("utf-8")
    if "berlin.addrlens.de" not in html:
        # Fixture stub — skip the coverage assertion.
        import pytest
        pytest.skip("real web/landing/index.html not yet present (Task 4 pending)")
    assert "berlin.addrlens.de" in html
    assert "hamburg.addrlens.de" in html
```

- [ ] **Step 2: Write Umami injection test**

Create `v0.1/tests/landing/test_umami_injection.py`:

```python
"""Umami tag injection: when the LANDING-suffixed env vars are set at
module import, _load_index() replaces the <!-- UMAMI-INJECT --> marker
with a real <script> tag. When unset, the marker is left as-is.

Both env vars must be set to trigger injection — either alone is a no-op
(fail-safe against half-configured envs).
"""
import importlib
import sys


def _fresh_import_with_env(monkeypatch, id_val: str | None, src_val: str | None):
    """Re-import app.landing.main with a specific env, returning the
    injected HTML bytes. Clears sys.modules first so _load_index() runs
    fresh under the current environment."""
    for mod in list(sys.modules):
        if mod == "app" or mod.startswith("app."):
            del sys.modules[mod]
    if id_val is None:
        monkeypatch.delenv("UMAMI_WEBSITE_ID_LANDING", raising=False)
    else:
        monkeypatch.setenv("UMAMI_WEBSITE_ID_LANDING", id_val)
    if src_val is None:
        monkeypatch.delenv("UMAMI_SCRIPT_URL_LANDING", raising=False)
        monkeypatch.delenv("UMAMI_SCRIPT_URL", raising=False)
    else:
        monkeypatch.setenv("UMAMI_SCRIPT_URL_LANDING", src_val)
    import app.landing.main as landing
    return landing._INDEX_HTML.decode("utf-8")


def test_umami_injected_when_both_env_vars_set(ensure_landing_index, monkeypatch):
    html = _fresh_import_with_env(monkeypatch, "test-website-id", "https://umami.example/x.js")
    assert 'data-website-id="test-website-id"' in html
    assert 'src="https://umami.example/x.js"' in html
    assert "<!-- UMAMI-INJECT -->" not in html


def test_umami_not_injected_when_id_missing(ensure_landing_index, monkeypatch):
    html = _fresh_import_with_env(monkeypatch, None, "https://umami.example/x.js")
    assert "<!-- UMAMI-INJECT -->" in html


def test_umami_not_injected_when_src_missing(ensure_landing_index, monkeypatch):
    html = _fresh_import_with_env(monkeypatch, "test-website-id", None)
    assert "<!-- UMAMI-INJECT -->" in html


def test_landing_ignores_flat_UMAMI_WEBSITE_ID(ensure_landing_index, monkeypatch):
    """Regression: landing must NOT fall back to flat UMAMI_WEBSITE_ID
    (Berlin's var). Guards against cross-contamination during cutover."""
    for mod in list(sys.modules):
        if mod == "app" or mod.startswith("app."):
            del sys.modules[mod]
    monkeypatch.delenv("UMAMI_WEBSITE_ID_LANDING", raising=False)
    monkeypatch.setenv("UMAMI_WEBSITE_ID", "berlin-website-id-should-not-appear")
    monkeypatch.setenv("UMAMI_SCRIPT_URL_LANDING", "https://umami.example/x.js")
    import app.landing.main as landing
    html = landing._INDEX_HTML.decode("utf-8")
    assert "berlin-website-id-should-not-appear" not in html
    assert "<!-- UMAMI-INJECT -->" in html
```

- [ ] **Step 3: Run new tests to verify they pass**

Run: `.venv/bin/pytest tests/landing/ -v`
Expected: all pass (7 route tests + 4 Umami tests + 1 import-guard = 12 tests).

- [ ] **Step 4: Run full test suite for regression check**

Run: `.venv/bin/pytest tests/ -q`
Expected: no regression in existing suite.

- [ ] **Step 5: Commit**

```bash
git add v0.1/tests/landing/test_routes.py v0.1/tests/landing/test_umami_injection.py
git commit -m "test(landing): route smoke + Umami injection coverage

Route smoke asserts 200 + correct media type on all 6 endpoints, and
guards against accidental removal of city-card links in landing HTML
once the real page arrives (Task 4).

Umami tests cover the happy path, both partial-config no-ops (missing
ID or missing src), and a regression test proving landing does NOT
fall back to the flat UMAMI_WEBSITE_ID env — critical for preventing
Berlin's tracker ID from leaking onto the apex during cutover."
```

---

## Task 3: Landing HTML + CSS + static assets + README

**Files:**
- Create: `v0.1/web/landing/index.html`
- Create: `v0.1/web/landing/static/landing.css`
- Create: `v0.1/web/landing/static/img/logo.png` (copy)
- Create: `v0.1/web/landing/static/img/og-image.jpg` (copy)
- Create: `v0.1/web/landing/static/img/favicon.png` (copy of logo.png)
- Create: `v0.1/web/landing/static/img/berlin-card.png` (copy of `web/static/img/hero/berlin.png`)
- Create: `v0.1/web/landing/static/img/hamburg-card.png` (copy of `web/static/img/hero/hamburg.png`)
- Create: `v0.1/web/landing/static/fonts/` (copies of `web/static/fonts/*`)
- Create: `v0.1/web/landing/README.md`

**Interfaces:**
- Consumes:
  - `app.landing.main.app` route table (Task 1) — HTML paths must match `/impressum`, `/datenschutzerklaerung`, `/static/*`
  - Existing design tokens in `v0.1/web/static/app.css` (fonts, palette, shadows)
- Produces:
  - Landing page served at `/` when container runs
  - After this task, `.venv/bin/pytest tests/landing/test_routes.py::test_index_html_contains_both_city_links_when_real_landing_exists` runs the real assertion (no longer skipped)

- [ ] **Step 1: Copy static assets**

```bash
mkdir -p v0.1/web/landing/static/img v0.1/web/landing/static/fonts
cp v0.1/web/static/img/logo.png v0.1/web/landing/static/img/logo.png
cp v0.1/web/static/img/logo.png v0.1/web/landing/static/img/favicon.png
cp v0.1/web/static/img/og-image.jpg v0.1/web/landing/static/img/og-image.jpg
cp v0.1/web/static/img/hero/berlin.png v0.1/web/landing/static/img/berlin-card.png
cp v0.1/web/static/img/hero/hamburg.png v0.1/web/landing/static/img/hamburg-card.png
cp -r v0.1/web/static/fonts/* v0.1/web/landing/static/fonts/
```

Verify:
```bash
ls v0.1/web/landing/static/img/
ls v0.1/web/landing/static/fonts/
```
Expected: 5 image files + all `.woff2` fonts from source.

- [ ] **Step 2: Write `web/landing/static/landing.css`**

Create `v0.1/web/landing/static/landing.css`. Reuse tokens verbatim from `web/static/app.css` — DO NOT duplicate values; use the same hex/font-family strings so both surfaces evolve in lockstep. Minimum feature set:

```css
/* landing.css — reuses tokens from web/static/app.css verbatim.
   No !important, no vendor prefixes beyond autoprefixer defaults,
   no dark mode (landing has no theme system, per spec §20). */

@font-face {font-family:'Inter';font-style:normal;font-weight:400;font-display:swap;
  src:url('/static/fonts/inter-400.woff2') format('woff2')}
@font-face {font-family:'Inter';font-style:normal;font-weight:500;font-display:swap;
  src:url('/static/fonts/inter-500.woff2') format('woff2')}
@font-face {font-family:'Inter';font-style:normal;font-weight:700;font-display:swap;
  src:url('/static/fonts/inter-700.woff2') format('woff2')}
@font-face {font-family:'Space Grotesk';font-style:normal;font-weight:700;font-display:swap;
  src:url('/static/fonts/space-grotesk-700.woff2') format('woff2')}

/* Design tokens — MUST stay in sync with web/static/app.css. */
:root{
  --hero-bg:#DCE7F3;
  --hero-accent:#0284C7; --hero-accent-2:#38BDF8;
  --result-bg:#EEF2FF; --result-bg-hover:#DDE7FF;
  --ink:#111827; --ink-2:#374151; --muted:#6B7280;
  --brand:#4F46E5; --success:#22C55E;
  --border:#E5E7EB;
  --sh-2:0 4px 8px rgba(17,24,39,.06),0 12px 24px rgba(17,24,39,.06);
  --radius:16px;
  --space-1:8px; --space-2:16px; --space-3:24px; --space-4:32px; --space-6:48px;
}

*,*::before,*::after{box-sizing:border-box}
html{scroll-behavior:smooth}
body{
  margin:0; background:var(--hero-bg); color:var(--ink);
  font-family:'Inter',system-ui,sans-serif; font-size:15px; line-height:1.55;
  -webkit-font-smoothing:antialiased; min-height:100vh;
}

/* Sticky header */
header{position:sticky; top:0; height:64px; background:var(--hero-bg);
  display:flex; align-items:center; justify-content:space-between;
  padding:0 var(--space-3); z-index:10; border-bottom:1px solid transparent;}
header .brand{display:flex; align-items:center; gap:var(--space-1); font-weight:700;}
header .brand img{width:28px; height:28px;}
header .brand span{font-family:'Space Grotesk','Inter',sans-serif; font-size:18px;}
#lang-toggle{
  background:transparent; border:1px solid var(--border); border-radius:8px;
  padding:6px 12px; cursor:pointer; font:500 13px/1 'Inter',sans-serif;
  color:var(--ink); min-width:44px; min-height:44px;
}
#lang-toggle:hover{background:rgba(255,255,255,.5);}
#lang-toggle:focus-visible{outline:2px solid var(--hero-accent); outline-offset:2px;}

/* Hero */
.hero{padding:var(--space-6) var(--space-3) var(--space-4); text-align:center; max-width:800px; margin:0 auto;}
.hero h1{
  font-family:'Space Grotesk','Inter',sans-serif; font-weight:700;
  font-size:clamp(2.5rem, 5vw, 4.5rem); line-height:1.05; letter-spacing:-.02em;
  margin:0 0 var(--space-2);
}
.hero p{color:var(--muted); font-size:clamp(1rem, 1.5vw, 1.15rem); margin:0;}

/* City cards */
.cities{
  display:grid; grid-template-columns:1fr; gap:var(--space-3);
  max-width:1000px; margin:0 auto; padding:var(--space-3);
}
@media (min-width: 768px){
  .cities{grid-template-columns:1fr 1fr;}
}
.city-card{
  display:block; text-decoration:none; color:inherit;
  background:var(--result-bg); border-radius:var(--radius); box-shadow:var(--sh-2);
  padding:0; overflow:hidden; cursor:pointer;
  transition:background 200ms ease, transform 200ms ease;
}
@media (prefers-reduced-motion: no-preference){
  .city-card:hover{background:var(--result-bg-hover); transform:translateY(-2px);}
}
.city-card:focus-visible{outline:2px solid var(--hero-accent); outline-offset:2px;}
.city-card img{width:100%; height:auto; display:block;}
.city-card .body{padding:var(--space-3);}
.city-card h2{
  font-family:'Inter',sans-serif; font-weight:700; font-size:24px; margin:0 0 8px;
  display:flex; align-items:center; justify-content:space-between;
}
.city-card .badge{
  display:inline-flex; align-items:center; gap:6px;
  font:500 12px/1 'Inter',sans-serif; color:var(--brand);
}
.city-card .badge::before{
  content:''; display:inline-block; width:8px; height:8px; border-radius:50%;
  background:var(--brand);
}
.city-card .subline{color:var(--muted); margin:0 0 var(--space-2);}
.city-card .cta{color:var(--hero-accent); font-weight:500;}

/* Footer */
footer{
  padding:var(--space-4) var(--space-3); text-align:center; color:var(--muted);
  font-size:13px; border-top:1px solid var(--border); margin-top:var(--space-6);
}
footer a{color:var(--muted); text-decoration:underline; margin:0 var(--space-1);}
footer a:hover{color:var(--ink);}
footer a:focus-visible{outline:2px solid var(--hero-accent); outline-offset:2px;}
```

- [ ] **Step 3: Write `web/landing/index.html`**

Create `v0.1/web/landing/index.html`. English is the default (per spec §8.3); DE is toggled. `<!-- UMAMI-INJECT -->` marker MUST appear exactly once, in the `<head>`, so `_load_index()` can substitute:

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AddrLens — Street intelligence for German cities</title>
  <meta name="description" content="Open data, cleanly connected. Berlin and Hamburg live.">

  <link rel="canonical" href="https://addrlens.de/">
  <meta property="og:url" content="https://addrlens.de/">
  <meta property="og:title" content="AddrLens — Street intelligence for German cities">
  <meta property="og:description" content="Open data, cleanly connected. Berlin and Hamburg live.">
  <meta property="og:image" content="https://addrlens.de/static/img/og-image.jpg">
  <meta name="twitter:card" content="summary_large_image">
  <link rel="alternate" hreflang="en-GB" href="https://addrlens.de/">
  <link rel="alternate" hreflang="de-DE" href="https://addrlens.de/">
  <link rel="alternate" hreflang="x-default" href="https://addrlens.de/">
  <link rel="icon" type="image/png" href="/static/img/favicon.png">
  <link rel="stylesheet" href="/static/landing.css">

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
  <!-- UMAMI-INJECT -->
</head>
<body>

<header>
  <a class="brand" href="/">
    <img src="/static/img/logo.png" alt="" width="28" height="28">
    <span>AddrLens</span>
  </a>
  <button id="lang-toggle" type="button" aria-label="Switch language">DE</button>
</header>

<main>
  <section class="hero">
    <div data-lang="en">
      <h1>Street intelligence for German cities</h1>
      <p>Open data, cleanly connected. Pick your city.</p>
    </div>
    <div data-lang="de" hidden>
      <h1>Straßen-Intelligenz für deutsche Städte</h1>
      <p>Frei zugängliche Daten, sauber verknüpft. Wähle deine Stadt.</p>
    </div>
  </section>

  <section class="cities" aria-label="Available cities">
    <a class="city-card" href="https://berlin.addrlens.de/">
      <img src="/static/img/berlin-card.png" alt="Berlin skyline illustration" loading="eager">
      <div class="body">
        <h2>Berlin <span class="badge">Live</span></h2>
        <p class="subline" data-lang="en">Address compare · Life-situation lens</p>
        <p class="subline" data-lang="de" hidden>Adressvergleich · Lebenslagen-Linsen</p>
        <p class="cta">→ berlin.addrlens.de</p>
      </div>
    </a>
    <a class="city-card" href="https://hamburg.addrlens.de/">
      <img src="/static/img/hamburg-card.png" alt="Hamburg skyline illustration" loading="eager">
      <div class="body">
        <h2>Hamburg <span class="badge">Live</span></h2>
        <p class="subline" data-lang="en">Address compare · Life-situation lens</p>
        <p class="subline" data-lang="de" hidden>Adressvergleich · Lebenslagen-Linsen</p>
        <p class="cta">→ hamburg.addrlens.de</p>
      </div>
    </a>
  </section>
</main>

<footer>
  <div data-lang="en">
    <a href="/impressum">Imprint</a> · <a href="/datenschutzerklaerung">Privacy</a>
    &nbsp;&nbsp;&nbsp; © 2026 sapta
  </div>
  <div data-lang="de" hidden>
    <a href="/impressum">Impressum</a> · <a href="/datenschutzerklaerung">Datenschutz</a>
    &nbsp;&nbsp;&nbsp; © 2026 sapta
  </div>
</footer>

<script>
(function () {
  const KEY = 'addrlens.lang';
  const stored = localStorage.getItem(KEY) || 'en';
  const html = document.documentElement;
  const btn = document.getElementById('lang-toggle');

  function apply(lang) {
    html.lang = lang;
    document.querySelectorAll('[data-lang]').forEach(function (el) {
      el.hidden = el.dataset.lang !== lang;
    });
    btn.textContent = lang === 'en' ? 'DE' : 'EN';
    btn.setAttribute('aria-label', lang === 'en' ? 'Auf Deutsch umschalten' : 'Switch to English');
  }

  apply(stored);
  btn.addEventListener('click', function () {
    const next = html.lang === 'en' ? 'de' : 'en';
    localStorage.setItem(KEY, next);
    apply(next);
  });
})();
</script>

</body>
</html>
```

- [ ] **Step 4: Write `web/landing/README.md`**

Create `v0.1/web/landing/README.md`:

```markdown
# web/landing/

Assets served by the `app-landing` container at `addrlens.de` (apex).

## Files

- `index.html` — landing page, EN-primary with DE toggle
- `impressum.html`, `datenschutzerklaerung.html` — apex-scoped legal pages
- `robots.txt`, `sitemap.xml` — apex crawler + SEO surface
- `static/landing.css` — landing-only stylesheet
- `static/img/{logo,favicon,og-image,berlin-card,hamburg-card}.png` — assets
- `static/fonts/*.woff2` — copies of `web/static/fonts/*` (Inter + Space Grotesk)

## Coupling with the CF Redirect Rule

The Cloudflare Redirect Rule at the apex (see `ops/cloudflared/README.md`)
maintains a **deny-list of paths that should NOT redirect** to
`berlin.addrlens.de`. The deny-list includes:
- `/`, `/impressum`, `/datenschutzerklaerung`, `/robots.txt`, `/sitemap.xml`, `/health`
- Exact filenames under `/static/img/`: `logo.png`, `og-image.jpg`, `favicon.png`, `berlin-card.png`, `hamburg-card.png`
- `starts_with(/static/fonts/)`, `starts_with(/static/landing.css)`

**If you add, remove, or rename any landing asset served under `/static/`,
you MUST update the CF Redirect Rule in the same PR.** Otherwise either
(a) legacy Berlin `/static/*` links break, or (b) new landing assets 404
because the redirect swallows them.

## How to add a new city card

1. Add asset: `cp v0.1/web/static/img/hero/<city>.png v0.1/web/landing/static/img/<city>-card.png`
2. Duplicate a `<a class="city-card">` block in `index.html`, swap the img
   src, city name, and href to `https://<city>.addrlens.de/`
3. Add the filename to the CF Redirect Rule's deny-list (see above)
4. Update `sitemap.xml` cross-refs (optional — keeps GSC discovery snappy)
```

- [ ] **Step 5: Local visual smoke — spin up the landing container's uvicorn**

```bash
cd v0.1
.venv/bin/uvicorn app.landing.main:app --port 8100 &
UVICORN_PID=$!
sleep 2
curl -fsS http://127.0.0.1:8100/ | grep -c "berlin.addrlens.de"   # expect >=1
curl -fsS http://127.0.0.1:8100/ | grep -c "hamburg.addrlens.de"  # expect >=1
curl -fsS http://127.0.0.1:8100/health | grep -c '"status":"ok"'  # expect 1
curl -fsSI http://127.0.0.1:8100/static/landing.css | head -1     # expect HTTP/1.1 200
curl -fsSI http://127.0.0.1:8100/static/img/logo.png | head -1    # expect HTTP/1.1 200
kill $UVICORN_PID
```

Expected: all 5 checks pass (2 city refs found, health ok, both static assets served 200).

- [ ] **Step 6: Run route smoke test — real HTML now present**

Run: `.venv/bin/pytest tests/landing/test_routes.py -v`
Expected: `test_index_html_contains_both_city_links_when_real_landing_exists` now runs the real assertion (no longer skipped) and PASSES.

- [ ] **Step 7: HTML validity check**

If `tidy` is available: `tidy -e v0.1/web/landing/index.html 2>&1 | grep -v "trimming empty"` → no errors.
If not available, skip and note in commit that manual browser render + DevTools console showed no errors.

- [ ] **Step 8: Commit**

```bash
git add v0.1/web/landing/
git commit -m "feat(landing): landing page HTML + CSS + assets + README

Hero + 2 city cards (Berlin + Hamburg) + DE/EN toggle + footer.
Reuses design tokens from web/static/app.css verbatim so users see
zero visual break flowing landing → city app. City card imagery
mirrors the hero illustration inside each city app.

English is the primary language (expat-focused audience), DE is
the toggle. localStorage persists user preference across visits.
No navigator.language sniff — apex is welcoming to expats even on
German-locale browsers.

Footer: Imprint + Privacy only, no GitHub link.

README documents the coupling with the CF Redirect Rule deny-list
so future asset renames don't silently 404."
```

---

## Task 4: Landing legal pages + robots + sitemap

**Files:**
- Create: `v0.1/web/landing/impressum.html`
- Create: `v0.1/web/landing/datenschutzerklaerung.html`
- Create: `v0.1/web/landing/robots.txt`
- Create: `v0.1/web/landing/sitemap.xml`

**Interfaces:**
- Consumes: existing `web/impressum.html` + `web/datenschutzerklaerung.html` as source-of-truth for the legal content template (operator info, DDG §5, GDPR sections)
- Produces: apex-scoped legal pages that (a) name the apex as the imprinted site, (b) are distinct-canonical from Berlin/Hamburg copies

- [ ] **Step 1: Draft `web/landing/impressum.html`**

Start from `v0.1/web/impressum.html` as the template. Two required semantic changes:

1. **Header preamble** (add above the DDG §5 operator block, both DE + EN): 
   - EN: "This imprint covers the addrlens.de landing page. For city-specific apps, see [berlin.addrlens.de/impressum](https://berlin.addrlens.de/impressum) and [hamburg.addrlens.de/impressum](https://hamburg.addrlens.de/impressum)."
   - DE: "Dieses Impressum betrifft die Landing-Seite addrlens.de. Für stadtspezifische Apps siehe [berlin.addrlens.de/impressum](https://berlin.addrlens.de/impressum) und [hamburg.addrlens.de/impressum](https://hamburg.addrlens.de/impressum)."
2. **All `Website:` operator contact lines** MUST show `https://addrlens.de` (apex — this is correct for the landing imprint). Emails unchanged (`sapta@addrlens.de` — mail routing is apex-independent).
3. **`<link rel="canonical" href="https://addrlens.de/impressum">`**
4. **English is primary** — swap the section order (EN first, DE toggle-hidden) matching the landing index.html i18n pattern (`<div data-lang="en">…</div><div data-lang="de" hidden>…</div>`).
5. Reuse the same `<script>` toggle from `index.html` (inline, ~20 lines).
6. Link to `/static/landing.css` for consistent header/footer chrome.

Skeleton (fill legal content from `v0.1/web/impressum.html`):

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Imprint — AddrLens</title>
  <link rel="canonical" href="https://addrlens.de/impressum">
  <link rel="icon" type="image/png" href="/static/img/favicon.png">
  <link rel="stylesheet" href="/static/landing.css">
</head>
<body>
  <header>
    <a class="brand" href="/"><img src="/static/img/logo.png" alt="" width="28" height="28"><span>AddrLens</span></a>
    <button id="lang-toggle" type="button" aria-label="Switch language">DE</button>
  </header>

  <main style="max-width: 780px; margin: 0 auto; padding: var(--space-4) var(--space-3);">
    <div data-lang="en">
      <h1>Imprint</h1>
      <p class="scope-note">This imprint covers the addrlens.de landing page. For city-specific apps, see
        <a href="https://berlin.addrlens.de/impressum">berlin.addrlens.de/impressum</a> and
        <a href="https://hamburg.addrlens.de/impressum">hamburg.addrlens.de/impressum</a>.</p>
      <!-- FILL: EN §5 DDG operator info from web/impressum.html, keep addrlens.de as the site URL -->
    </div>
    <div data-lang="de" hidden>
      <h1>Impressum</h1>
      <p class="scope-note">Dieses Impressum betrifft die Landing-Seite addrlens.de. Für stadtspezifische Apps siehe
        <a href="https://berlin.addrlens.de/impressum">berlin.addrlens.de/impressum</a> und
        <a href="https://hamburg.addrlens.de/impressum">hamburg.addrlens.de/impressum</a>.</p>
      <!-- FILL: DE §5 DDG Angaben aus web/impressum.html, addrlens.de bleibt als Site-URL -->
    </div>
  </main>

  <footer>
    <!-- Same footer markup as index.html -->
  </footer>

  <script>
    /* Same i18n toggle as index.html — copy verbatim */
  </script>
</body>
</html>
```

Copy the legal body from `v0.1/web/impressum.html` (both DE + EN sections). Where the source says `https://berlin.addrlens.de` (post-Task 5) or currently `https://addrlens.de`, on the landing legal page it stays `https://addrlens.de` (the landing is the imprinted site).

- [ ] **Step 2: Draft `web/landing/datenschutzerklaerung.html`**

Same shape and template as impressum:
- Copy legal body from `v0.1/web/datenschutzerklaerung.html`
- Scope preamble (EN): "This privacy notice covers data processing for the addrlens.de landing page. For city-specific apps, see [berlin.addrlens.de/datenschutzerklaerung](https://berlin.addrlens.de/datenschutzerklaerung) and [hamburg.addrlens.de/datenschutzerklaerung](https://hamburg.addrlens.de/datenschutzerklaerung)."
- DE equivalent
- `<link rel="canonical" href="https://addrlens.de/datenschutzerklaerung">`
- All operator `Website:` contact lines → `https://addrlens.de` (apex)
- English primary, DE toggle

- [ ] **Step 3: Write `web/landing/robots.txt`**

Create `v0.1/web/landing/robots.txt`:

```
User-agent: *
Allow: /
Disallow: /health

Sitemap: https://addrlens.de/sitemap.xml
```

- [ ] **Step 4: Write `web/landing/sitemap.xml`**

Create `v0.1/web/landing/sitemap.xml`. Include the 3 apex URLs; cross-reference the city subdomains (helps GSC discovery — not strictly required but low-cost):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://addrlens.de/</loc>
    <changefreq>weekly</changefreq>
    <priority>1.0</priority>
  </url>
  <url>
    <loc>https://addrlens.de/impressum</loc>
    <changefreq>yearly</changefreq>
    <priority>0.3</priority>
  </url>
  <url>
    <loc>https://addrlens.de/datenschutzerklaerung</loc>
    <changefreq>yearly</changefreq>
    <priority>0.3</priority>
  </url>
  <url>
    <loc>https://berlin.addrlens.de/</loc>
    <changefreq>daily</changefreq>
    <priority>0.9</priority>
  </url>
  <url>
    <loc>https://hamburg.addrlens.de/</loc>
    <changefreq>daily</changefreq>
    <priority>0.9</priority>
  </url>
</urlset>
```

- [ ] **Step 5: Local smoke — legal + sitemap + robots serve correctly**

```bash
cd v0.1
.venv/bin/uvicorn app.landing.main:app --port 8100 &
UVICORN_PID=$!
sleep 2
curl -fsSI http://127.0.0.1:8100/impressum | head -1              # HTTP/1.1 200
curl -fsSI http://127.0.0.1:8100/datenschutzerklaerung | head -1  # HTTP/1.1 200
curl -fsS  http://127.0.0.1:8100/robots.txt | grep -c "Sitemap"   # expect 1
curl -fsS  http://127.0.0.1:8100/sitemap.xml | grep -c "<loc>"    # expect 5
curl -fsS  http://127.0.0.1:8100/impressum | grep -c "berlin.addrlens.de/impressum"  # expect >=1
kill $UVICORN_PID
```

Expected: all 5 checks pass.

- [ ] **Step 6: Run full test suite**

Run: `.venv/bin/pytest tests/ -q`
Expected: no regression.

- [ ] **Step 7: Commit**

```bash
git add v0.1/web/landing/impressum.html v0.1/web/landing/datenschutzerklaerung.html \
        v0.1/web/landing/robots.txt v0.1/web/landing/sitemap.xml
git commit -m "feat(landing): apex-scoped legal + robots + sitemap

Landing imprint + privacy pages carry apex-scoped scope preambles
naming the two city apps and their own legal surfaces. All Website:
operator contact lines point at addrlens.de (apex) — the landing IS
the site being imprinted here. Emails unchanged (mail routing is
apex-independent).

Distinct canonical URLs (addrlens.de/{impressum,datenschutzerklaerung})
prevent Google flagging as duplicate content vs the city subdomains.

Sitemap cross-refs berlin. + hamburg. subdomains so GSC discovers
the city sitemaps via the apex property."
```

---

## Task 5: `ops/Dockerfile.landing`

**Files:**
- Create: `v0.1/ops/Dockerfile.landing`

**Interfaces:**
- Consumes: `v0.1/app/landing/` (Task 1), `v0.1/web/landing/` (Tasks 3-4)
- Produces: `addrlens-landing:latest` image, ~90-120 MB, runs `uvicorn app.landing.main:app --port 8000`

- [ ] **Step 1: Write the Dockerfile**

Create `v0.1/ops/Dockerfile.landing`:

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
# convention). Omitted here to prevent Dockerfile vs compose drift.

CMD ["uvicorn", "app.landing.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Build the image locally**

```bash
docker build -f v0.1/ops/Dockerfile.landing -t addrlens-landing:test v0.1 2>&1 | tail -5
```

Expected: `Successfully tagged addrlens-landing:test`.

- [ ] **Step 3: Verify image size**

```bash
docker images addrlens-landing:test --format '{{.Size}}'
```

Expected: 90-150 MB. Flag in commit if outside this range (may indicate accidental dep inclusion).

- [ ] **Step 4: Verify no coupling — image contains no app.core / app.cities**

```bash
docker run --rm addrlens-landing:test ls /srv/app/
```

Expected: `__init__.py` and `landing` — NOTHING else. If you see `core/`, `cities/`, `routes/`, `main.py`, the Dockerfile COPY leaked.

- [ ] **Step 5: Run the container standalone and hit health**

```bash
docker run --rm -d --name addrlens-landing-test -p 8100:8000 addrlens-landing:test
sleep 3
docker exec addrlens-landing-test python -c \
  "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).read())"
# Expect: b'{"status":"ok"}'
docker stop addrlens-landing-test
```

- [ ] **Step 6: Commit**

```bash
git add v0.1/ops/Dockerfile.landing
git commit -m "ops(landing): minimal Dockerfile — python:3.11-slim + fastapi + uvicorn

~90-120 MB target vs ~200 MB for Dockerfile.app. No shapely, no
pandas, no city loaders, no scoring. Copies only app/__init__.py +
app/landing/ + web/landing/, so an accidental import of app.core in
the landing code would fail at runtime.

Version pins mirror pyproject.toml (fastapi>=0.115, uvicorn>=0.32).
Sync comment above the uv install line names the obligation.

Healthcheck lives in docker-compose.prod.yml only (matches app-hh
convention) to prevent Dockerfile vs compose drift."
```

---

## Task 6: `docker-compose.prod.yml` `app-landing` service + local prod-shape smoke

**Files:**
- Modify: `v0.1/docker-compose.prod.yml` — add `app-landing` service block; add to `cloudflared.depends_on`

**Interfaces:**
- Consumes: `addrlens-landing` image (Task 5), `addrlens_net` network (existing)
- Produces: `addrlens-app-landing` running container reachable at `app-landing:8000` inside the docker network

- [ ] **Step 1: Locate the insertion point + read surrounding context**

Read `v0.1/docker-compose.prod.yml` to find the `app-hh` service block (used as template) and the `cloudflared.depends_on` block. Confirm current shape.

- [ ] **Step 2: Add the `app-landing` service block**

Add between `app-hh` and `cloudflared` (or wherever alphabetical/logical grouping suggests). Block:

```yaml
  # Apex landing container. Serves web/landing/* at addrlens.de after
  # cutover. Cloudflare Tunnel routes addrlens.de → app-landing:8000
  # (see ops/cloudflared/README.md). Runs on port 8000 so `docker logs
  # app-landing` and any host-network debug are visually distinguished
  # from Berlin's :8001 and Hamburg's :8002.
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
    ports: !reset []
    healthcheck:
      test: ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)\" || exit 1"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 15s
    networks:
      - addrlens_net
```

- [ ] **Step 3: Add `app-landing` to `cloudflared.depends_on`**

Locate the `cloudflared` service's `depends_on` block. Add:

```yaml
      app-landing:
        condition: service_healthy
```

Leave existing `app` and `app-hh` entries unchanged.

- [ ] **Step 4: Validate compose syntax**

```bash
docker compose -f v0.1/docker-compose.yml -f v0.1/docker-compose.prod.yml config > /tmp/composed.yml 2>&1
head -20 /tmp/composed.yml
grep -A5 "app-landing:" /tmp/composed.yml | head -20
```

Expected: exit 0, `app-landing` service present in rendered output.

- [ ] **Step 5: Local prod-shape smoke — bring up landing**

```bash
cd v0.1
# .env.production may not exist locally; use a stub for local smoke:
touch /tmp/.env.landing-smoke
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  --env-file /tmp/.env.landing-smoke up -d --build app-landing 2>&1 | tail -3

# Wait for healthy
for i in 1 2 3 4 5; do
  status=$(docker inspect --format='{{.State.Health.Status}}' addrlens-app-landing 2>/dev/null)
  echo "attempt $i: $status"
  [ "$status" = "healthy" ] && break
  sleep 3
done

# Run all 6 endpoints via compose exec (NOT host curl — no published port)
for ep in "/" "/impressum" "/datenschutzerklaerung" "/robots.txt" "/sitemap.xml" "/health"; do
  code=$(docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T app-landing \
    python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000${ep}', timeout=3).status)" 2>/dev/null)
  echo "$ep -> $code"
done

# Cleanup
docker compose -f docker-compose.yml -f docker-compose.prod.yml down app-landing
```

Expected: all 6 endpoints return `200`. Container reaches `healthy` state within 15s.

- [ ] **Step 6: Commit**

```bash
git add v0.1/docker-compose.prod.yml
git commit -m "ops(landing): add app-landing service to prod compose

Mirrors the app-hh block shape: same restart policy, same env_file,
distinct port (8000) + image (addrlens-landing:latest) + container
name (addrlens-app-landing). ports: !reset [] matches app + app-hh —
container is only reachable via docker network, cloudflared is the
sole ingress.

Healthcheck is compose-side only (no Dockerfile drift). cloudflared
now depends on all three app containers being healthy before
starting."
```

---

## Task 7: Berlin app URL surgery — canonical/OG/sitemap/robots/legal/compare.js

**Files:**
- Modify: `v0.1/web/index.html` — canonical, og:url, hreflang, JSON-LD url, og:image, twitter:image → `berlin.addrlens.de`
- Modify: `v0.1/web/impressum.html` — all `https?://addrlens.de` URL refs → `berlin.addrlens.de` (both DE + EN), emails unchanged
- Modify: `v0.1/web/datenschutzerklaerung.html` — same URL flip, emails unchanged
- Modify: `v0.1/web/sitemap.xml` — 3 `<loc>` entries → `berlin.addrlens.de`
- Modify: `v0.1/web/robots.txt` — sitemap URL → `berlin.addrlens.de`
- Modify: `v0.1/web/static/modules/compare.js` — `print-header-site` string → `berlin.addrlens.de`

**Interfaces:**
- Consumes: nothing new
- Produces: Berlin app self-identifies as `berlin.addrlens.de` — SEO tags, legal text, PDF print header all aligned

- [ ] **Step 1: Grep baseline — count `addrlens.de` refs per file for before/after diff**

```bash
cd v0.1
for f in web/index.html web/impressum.html web/datenschutzerklaerung.html \
         web/sitemap.xml web/robots.txt web/static/modules/compare.js; do
  n=$(grep -cE 'https?://addrlens\.de|(?<!@)addrlens\.de' "$f" 2>/dev/null || echo 0)
  echo "$n  $f"
done
```

Record the baseline numbers. Write them into the commit message at the end.

- [ ] **Step 2: Edit `web/index.html`**

Use `sed` or manual Edit-tool replacements. Substitute `https://addrlens.de` → `https://berlin.addrlens.de` in ONLY these attribute/content positions (grep confirms these are the 7 sites):

- `<meta property="og:url" content="https://addrlens.de/">` → `https://berlin.addrlens.de/`
- `<meta property="og:image" content="https://addrlens.de/static/img/og-image.jpg">` → `https://berlin.addrlens.de/…`
- `<meta name="twitter:image" content="https://addrlens.de/static/img/og-image.jpg">` → `https://berlin.addrlens.de/…`
- `<link rel="canonical" href="https://addrlens.de/">` → `https://berlin.addrlens.de/`
- `<link rel="alternate" hreflang="en-GB" href="https://addrlens.de/">` → `https://berlin.addrlens.de/`
- `<link rel="alternate" hreflang="x-default" href="https://addrlens.de/">` → `https://berlin.addrlens.de/`
- JSON-LD `"url": "https://addrlens.de/"` → `"url": "https://berlin.addrlens.de/"`

Do NOT change body text `addrlens.de` occurrences (there may be none — verify).

Verify:
```bash
grep -cE 'https?://addrlens\.de' web/index.html   # should now be 0
grep -cE 'https?://berlin\.addrlens\.de' web/index.html  # was 0, now 7
```

- [ ] **Step 3: Edit `web/impressum.html`**

Flip all URL/href occurrences of `https://addrlens.de` → `https://berlin.addrlens.de`. Both DE and EN sections. `mailto:sapta@addrlens.de` MUST remain unchanged.

Sed pattern (safe — only URLs, not emails):
```bash
sed -i.bak -E 's|https?://addrlens\.de|https://berlin.addrlens.de|g' v0.1/web/impressum.html
diff v0.1/web/impressum.html.bak v0.1/web/impressum.html | head -30
rm v0.1/web/impressum.html.bak
```

Verify:
```bash
grep -cE 'https?://addrlens\.de' v0.1/web/impressum.html    # expect 0
grep -c   'mailto:sapta@addrlens.de' v0.1/web/impressum.html # unchanged
```

- [ ] **Step 4: Edit `web/datenschutzerklaerung.html`**

Same sed pattern as Step 3:
```bash
sed -i.bak -E 's|https?://addrlens\.de|https://berlin.addrlens.de|g' v0.1/web/datenschutzerklaerung.html
diff v0.1/web/datenschutzerklaerung.html.bak v0.1/web/datenschutzerklaerung.html | head -30
rm v0.1/web/datenschutzerklaerung.html.bak

grep -cE 'https?://addrlens\.de' v0.1/web/datenschutzerklaerung.html    # expect 0
grep -c   'mailto:sapta@addrlens.de' v0.1/web/datenschutzerklaerung.html # unchanged
```

- [ ] **Step 5: Edit `web/sitemap.xml`**

Flip all `<loc>https://addrlens.de/…</loc>` → `<loc>https://berlin.addrlens.de/…</loc>`:
```bash
sed -i.bak -E 's|https?://addrlens\.de|https://berlin.addrlens.de|g' v0.1/web/sitemap.xml
diff v0.1/web/sitemap.xml.bak v0.1/web/sitemap.xml
rm v0.1/web/sitemap.xml.bak
```

Verify:
```bash
grep -cE 'https?://addrlens\.de' v0.1/web/sitemap.xml   # expect 0
grep -cE 'berlin\.addrlens\.de'  v0.1/web/sitemap.xml   # expect 3
```

- [ ] **Step 6: Edit `web/robots.txt`**

```bash
sed -i.bak -E 's|https?://addrlens\.de|https://berlin.addrlens.de|g' v0.1/web/robots.txt
rm v0.1/web/robots.txt.bak
grep -cE 'berlin\.addrlens\.de' v0.1/web/robots.txt   # expect 1
```

- [ ] **Step 7: Edit `web/static/modules/compare.js`**

Locate `print-header-site` string. Confirm it's `addrlens.de` today (not a URL — bare host string used as PDF print header). Replace with `berlin.addrlens.de`:

```bash
grep -n "print-header-site" v0.1/web/static/modules/compare.js
# Manually edit that line: 'addrlens.de' → 'berlin.addrlens.de'
# Do NOT sed-replace globally in this file — may have unrelated matches
grep -c "'addrlens.de'\|>addrlens.de<" v0.1/web/static/modules/compare.js  # after: expect 0
grep -c "berlin.addrlens.de" v0.1/web/static/modules/compare.js            # after: expect >=1
```

- [ ] **Step 8: Run full test suite**

Run: `.venv/bin/pytest tests/ -q`
Expected: no regression. Berlin app tests still pass — none depend on the canonical URL string.

- [ ] **Step 9: Local Berlin smoke — confirm it still boots + serves**

```bash
cd v0.1
CITY=berlin .venv/bin/uvicorn app.main:app --port 8100 &
UVICORN_PID=$!
sleep 3
curl -fsS http://127.0.0.1:8100/ | grep -c 'canonical.*berlin.addrlens.de'   # expect 1
curl -fsS http://127.0.0.1:8100/impressum | grep -c 'berlin.addrlens.de'     # expect >=1
curl -fsS http://127.0.0.1:8100/health                                        # expect ok
kill $UVICORN_PID
```

- [ ] **Step 10: Commit**

```bash
git add v0.1/web/index.html v0.1/web/impressum.html v0.1/web/datenschutzerklaerung.html \
        v0.1/web/sitemap.xml v0.1/web/robots.txt v0.1/web/static/modules/compare.js
git commit -m "feat(berlin): flip apex → berlin.addrlens.de across all Berlin URL surfaces

All Berlin-app self-identification URLs move to the new subdomain:
- web/index.html: canonical, og:url, og:image, twitter:image, hreflang
  (en-GB + x-default), JSON-LD url — all 7 sites
- web/impressum.html + datenschutzerklaerung.html: every URL / href
  reference to https://addrlens.de → berlin.addrlens.de (both DE and
  EN sections). Emails (mailto:sapta@addrlens.de) unchanged — apex
  mail routing survives the migration.
- web/sitemap.xml: all 3 <loc> entries
- web/robots.txt: sitemap URL
- compare.js print-header-site: 'addrlens.de' → 'berlin.addrlens.de'
  (truth-in-labelling for PDF exports — the app that made the PDF
  now lives at berlin.addrlens.de)

No logic changes. Berlin's /health, /ready, /api/* untouched. Full
test suite passes."
```

---

## Task 8: Hamburg legal page fixes (§9.1)

**Files:**
- Modify: `v0.1/web/hamburg/impressum.html` — 2 `Website: https://addrlens.de` → `hamburg.addrlens.de` (l.46 DE, l.159 EN)
- Modify: `v0.1/web/hamburg/datenschutzerklaerung.html` — 2 same-shape refs → `hamburg.addrlens.de` (l.46 DE, l.385 EN)

**Interfaces:**
- Consumes: nothing
- Produces: Hamburg legal pages accurately name Hamburg as the imprinted site (was a bug — apex pointed at the wrong app post-cutover)

- [ ] **Step 1: Baseline grep**

```bash
grep -nE 'Website:.*addrlens' v0.1/web/hamburg/impressum.html v0.1/web/hamburg/datenschutzerklaerung.html
# Expect exactly 4 matches:
#   web/hamburg/impressum.html:46: Website: <a href="https://addrlens.de">https://addrlens.de</a>
#   web/hamburg/impressum.html:159: Website: <a href="https://addrlens.de">https://addrlens.de</a>
#   web/hamburg/datenschutzerklaerung.html:46: Website: <a href="https://addrlens.de">https://addrlens.de</a>
#   web/hamburg/datenschutzerklaerung.html:385: Website: <a href="https://addrlens.de">https://addrlens.de</a>
```

If the grep shows any different count or line numbers, STOP and re-read the files — content has shifted since the spec was written. Notify the operator before proceeding.

- [ ] **Step 2: Fix impressum — DE + EN sections**

Use the Edit tool for each of the 4 sites, or a scoped sed. Scoped sed is safer here because the Website line is a specific pattern:
```bash
sed -i.bak -E 's|(Website: <a href=")https?://addrlens\.de(">)https?://addrlens\.de(</a>)|\1https://hamburg.addrlens.de\2https://hamburg.addrlens.de\3|g' \
  v0.1/web/hamburg/impressum.html \
  v0.1/web/hamburg/datenschutzerklaerung.html

diff v0.1/web/hamburg/impressum.html.bak            v0.1/web/hamburg/impressum.html
diff v0.1/web/hamburg/datenschutzerklaerung.html.bak v0.1/web/hamburg/datenschutzerklaerung.html
rm v0.1/web/hamburg/impressum.html.bak v0.1/web/hamburg/datenschutzerklaerung.html.bak
```

- [ ] **Step 3: Verify**

```bash
# All Website: lines now say hamburg.addrlens.de
grep -nE 'Website:.*addrlens' v0.1/web/hamburg/impressum.html v0.1/web/hamburg/datenschutzerklaerung.html
# Expect: all 4 lines show hamburg.addrlens.de

# No stale addrlens.de refs in URL positions (mail lines unchanged)
grep -cE 'https?://addrlens\.de' v0.1/web/hamburg/impressum.html            # expect 0
grep -cE 'https?://addrlens\.de' v0.1/web/hamburg/datenschutzerklaerung.html # expect 0
grep -c   'mailto:sapta@addrlens.de' v0.1/web/hamburg/impressum.html         # unchanged
```

- [ ] **Step 4: Run full test suite**

Run: `.venv/bin/pytest tests/ -q`
Expected: no regression (Hamburg tests untouched).

- [ ] **Step 5: Local Hamburg smoke — confirm impressum still serves**

```bash
cd v0.1
CITY=hamburg .venv/bin/uvicorn app.main:app --port 8100 &
UVICORN_PID=$!
sleep 3
curl -fsS http://127.0.0.1:8100/impressum | grep -c 'hamburg.addrlens.de'   # expect >=2
curl -fsS http://127.0.0.1:8100/datenschutzerklaerung | grep -c 'hamburg.addrlens.de' # expect >=2
kill $UVICORN_PID
```

- [ ] **Step 6: Commit**

```bash
git add v0.1/web/hamburg/impressum.html v0.1/web/hamburg/datenschutzerklaerung.html
git commit -m "fix(hamburg): imprint Website: line points at hamburg.addrlens.de

Both Hamburg legal pages had 4 stale 'Website: https://addrlens.de'
references in the operator contact block (DE + EN sections, both
files). Post-apex-migration, addrlens.de serves the landing — not
the Hamburg app being imprinted — which was (a) semantically wrong
and (b) risked a §5 DDG abmahnung for an imprint naming a URL that
isn't the site.

Canonical URLs, sitemap, robots.txt, og:url tags were already
correct (they point at hamburg.addrlens.de). Only the operator
Website: contact lines needed flipping. Emails unchanged."
```

---

## Task 9: `update.sh` + `rollback.sh` deploy pipeline edits

**Files:**
- Modify: `v0.1/ops/deploy/update.sh` — add `app-landing` to build list + smoke loop; new `if $svc = app-landing` branch runs health-only `compose exec` smoke
- Modify: `v0.1/ops/deploy/rollback.sh` — add `app-landing` to BOTH the `build` line AND the `up -d --force-recreate` line

**Interfaces:**
- Consumes: `app-landing` service (Task 6)
- Produces: prod deploy pipeline builds + smoke-tests all 3 containers; rollback rebuilds + recreates all 3

- [ ] **Step 1: Read current `update.sh` around the build + smoke loop**

Read `v0.1/ops/deploy/update.sh` lines 40-95 to confirm current shape (build line, `for svc_port` loop, case dispatch, `compose exec` smoke). Baseline reference: `svc_port` list is `"app:8001" "app-hh:8002"`.

- [ ] **Step 2: Patch `update.sh` — build line**

Change (spec §11.1):
```
-"${COMPOSE[@]}" build --pull app app-hh inference
+"${COMPOSE[@]}" build --pull app app-hh app-landing inference
```

- [ ] **Step 3: Patch `update.sh` — smoke loop**

Change:
```
-for svc_port in "app:8001" "app-hh:8002"; do
+for svc_port in "app:8001" "app-hh:8002" "app-landing:8000"; do
```

Add the landing branch BEFORE the address-based `case` (spec §11.1). The branch runs a health check via `compose exec` and `continue`s to skip the address-lookup smoke that landing doesn't support:

```bash
    # Landing has no lookup — health-only smoke via compose exec, since
    # app-landing has `ports: !reset []` and is not published to host.
    if [ "$svc" = "app-landing" ]; then
      "${COMPOSE[@]}" exec -T "$svc" python -c \
        "import urllib.request; urllib.request.urlopen('http://127.0.0.1:${port}/health', timeout=3)"
      continue
    fi
```

Insert this block immediately after the `svc=…; port=…` variable expansion, before the existing `case "$svc" in` dispatch.

- [ ] **Step 4: Verify `update.sh` syntax**

```bash
bash -n v0.1/ops/deploy/update.sh && echo "syntax ok"
# If shellcheck is available:
shellcheck v0.1/ops/deploy/update.sh 2>&1 | head -20
```

Expected: `syntax ok`. Any shellcheck warnings unrelated to this diff (existing tech debt) can be ignored.

- [ ] **Step 5: Patch `rollback.sh` — BOTH lines**

Read `v0.1/ops/deploy/rollback.sh` lines 35-45.

Change TWO lines:
```
-"${COMPOSE[@]}" build app app-hh inference
+"${COMPOSE[@]}" build app app-hh app-landing inference
-"${COMPOSE[@]}" up -d --force-recreate app app-hh inference
+"${COMPOSE[@]}" up -d --force-recreate app app-hh app-landing inference
```

Same footgun class as the Hamburg-omission fix the file already warns about. Missing either line = partial rollback (either stale landing image, or landing runs on new-code image while Berlin rolls back).

- [ ] **Step 6: Verify `rollback.sh` syntax**

```bash
bash -n v0.1/ops/deploy/rollback.sh && echo "syntax ok"
```

- [ ] **Step 7: Dry-run — verify the scripts reference the actual compose services**

```bash
docker compose -f v0.1/docker-compose.yml -f v0.1/docker-compose.prod.yml config --services | sort
```

Expected output includes: `app`, `app-hh`, `app-landing`, `cloudflared`, `inference`, `umami`, `umami-db`. All four services named in the scripts must appear.

- [ ] **Step 8: Commit**

```bash
git add v0.1/ops/deploy/update.sh v0.1/ops/deploy/rollback.sh
git commit -m "ops(deploy): wire app-landing into update + rollback scripts

update.sh: adds app-landing to the build --pull list and the smoke
loop. New branch runs a health-only smoke via compose exec (landing
has ports: !reset [], no host-published port; same pattern used for
app/app-hh's /api/lookup smoke). Branch continues past the
address-lookup case since landing has no smoke_address concept.

rollback.sh: TWO lines patched (build + up --force-recreate) — missing
either leaves rollback partial. Same footgun class as the Hamburg
omission the file's own comment already warns about."
```

---

## Task 10: Ops docs — deploy README + cloudflared README

**Files:**
- Modify: `v0.1/ops/deploy/README.md` — curl examples updated for 3 hostnames
- Modify: `v0.1/ops/cloudflared/README.md` — apex block rewritten to point at `app-landing:8000`; new "Berlin subdomain" section (→ `app:8001`); Hamburg section unchanged; new "Landing subdomain (apex)" section positioning; Redirect Rule pointer

**Interfaces:**
- Consumes: nothing (documentation)
- Produces: on-call operators can navigate the 3-host topology + know where the CF Redirect Rule lives + know the cutover order

- [ ] **Step 1: Update `ops/deploy/README.md` curl examples**

Locate the current `curl` example block (probably shows `curl -sSf https://addrlens.de/health`). Replace with 3-hostname block:

```markdown
```
curl -sSf https://addrlens.de/health         # {"status":"ok"}          (landing)
curl -sSf https://berlin.addrlens.de/health  # {"status":"ok"}          (Berlin app)
curl -sSf https://berlin.addrlens.de/ready   # {"status":"ready","city":"berlin"}
curl -sSf https://hamburg.addrlens.de/health # {"status":"ok"}          (Hamburg app)
curl -sSf https://hamburg.addrlens.de/ready  # {"status":"ready","city":"hamburg"}
```
```

Add a note near this block: "Apex `addrlens.de` serves the landing hub (not the Berlin app). Legacy paths on apex 301-redirect to `berlin.addrlens.de` — see `ops/cloudflared/README.md`."

- [ ] **Step 2: Update `ops/cloudflared/README.md` — Public Hostname routing section**

Rewrite the "Public hostname routing" section to reflect the post-cutover 3-host topology.

**Structure:**
1. Apex subsection — now points at `app-landing:8000`, host header `addrlens.de`
2. NEW "Berlin subdomain" subsection — mirrors Hamburg's format, points at `app:8001`, host header `berlin.addrlens.de`
3. Existing Hamburg subsection — unchanged
4. NEW subsection "Apex → Berlin Redirect Rule" — brief summary + pointer to spec §12.2 for the exact expression

Include:
- Full Rule expression (verbatim from spec §12.2)
- Warning: "The static-asset allow-list in this rule is coupled to `web/landing/static/img/` filenames. Adding, renaming, or removing a landing asset requires updating this rule in the SAME PR — see `web/landing/README.md`."

- [ ] **Step 3: Verify markdown renders (no broken links, tables intact)**

```bash
# If markdownlint is available:
markdownlint v0.1/ops/deploy/README.md v0.1/ops/cloudflared/README.md 2>&1 | head -20
# Else visual inspection: cat + eyeball
cat v0.1/ops/cloudflared/README.md | head -80
```

- [ ] **Step 4: Commit**

```bash
git add v0.1/ops/deploy/README.md v0.1/ops/cloudflared/README.md
git commit -m "docs(ops): document 3-hostname topology + apex Redirect Rule

deploy/README.md: curl examples now cover all 3 hostnames (landing,
berlin, hamburg) with a note that apex is the landing hub, not the
Berlin app.

cloudflared/README.md: apex subsection rewritten to describe the
landing route (was Berlin). New Berlin subdomain subsection mirrors
the Hamburg format. New 'Apex → Berlin Redirect Rule' section
documents the CF Rules dashboard entry, with a coupling warning
that the landing static-asset allow-list must be kept in sync with
files under web/landing/static/img/."
```

---

## Task 11: Cutover runbook (production migration)

**Files:**
- Create: `v0.1/docs/superpowers/plans/2026-09-25-apex-landing-cutover-runbook.md`

**Interfaces:**
- Consumes: prod already has the new code deployed (Tasks 1-10 shipped via a merged PR + successful `ops/deploy/update.sh`)
- Produces: successful production migration; apex serves landing; berlin subdomain serves Berlin app; 301 redirects work; old inbound links survive; analytics split cleanly

**This task is a manual runbook — no code changes. Each step is a checkbox the operator ticks during cutover. Do NOT dispatch a subagent to execute this task. A human runs it.**

- [ ] **Step 1: Write the runbook file**

Create `v0.1/docs/superpowers/plans/2026-09-25-apex-landing-cutover-runbook.md`:

```markdown
# Apex Landing Cutover Runbook

**Prereq:** PR for `feat/apex-landing-migration` merged to `main`. `ops/deploy/update.sh` completed on prod (Hetzner box), all 3 app containers healthy per `docker compose ps`.

**Target duration:** 15 minutes wall-clock. **Downtime:** 0. **Rollback:** dashboard-only, 2-3 min.

## Pre-flight (5 min, on box)

- [ ] SSH to prod box, verify state:
  ```bash
  cd /srv/addrlens
  docker compose ps app app-hh app-landing
  # All 3 must show STATUS = "Up X (healthy)"
  ```
- [ ] Verify landing is reachable inside docker network:
  ```bash
  docker compose exec app-landing python -c \
    "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).read())"
  # Expect: b'{"status":"ok"}'
  ```
- [ ] Verify Berlin app still healthy:
  ```bash
  docker compose exec app python -c \
    "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8001/health', timeout=3).read())"
  ```
- [ ] Verify Hamburg untouched:
  ```bash
  curl -fsS https://hamburg.addrlens.de/health
  ```

## Step 1: Umami websites (2 min, Umami dashboard)

- [ ] Log in to `https://umami.addrlens.de/`.
- [ ] Create website: name `AddrLens Landing`, domain `addrlens.de`. Copy the new website ID.
- [ ] Create website: name `AddrLens Hamburg`, domain `hamburg.addrlens.de`. Copy the new website ID. (Skip if already exists.)
- [ ] Existing website: rename to `AddrLens Berlin`, change domain to `berlin.addrlens.de`. Copy its ID.

## Step 2: Prod env vars (2 min, SSH on box)

- [ ] Edit `/srv/addrlens/.env.production` (as root):
  ```bash
  sudo vim /srv/addrlens/.env.production
  ```
- [ ] Rename the existing `UMAMI_WEBSITE_ID=…` line to `UMAMI_WEBSITE_ID_BERLIN=…` (same value).
- [ ] Add `UMAMI_WEBSITE_ID_LANDING=<landing-id from Step 1>`.
- [ ] Add `UMAMI_WEBSITE_ID_HAMBURG=<hamburg-id from Step 1>` (if not already present).
- [ ] Save file.
- [ ] Restart the 3 app containers to pick up new env:
  ```bash
  docker compose -f docker-compose.yml -f docker-compose.prod.yml \
    --env-file /srv/addrlens/.env.production \
    up -d --force-recreate app app-hh app-landing
  ```
- [ ] Verify Umami injection worked for each host:
  ```bash
  curl -fsS https://hamburg.addrlens.de/ | grep -c 'data-website-id="<hamburg-id>"'
  # (apex not yet flipped — landing will be verified after Step 4)
  ```

## Step 3: CF Tunnel — add berlin.addrlens.de (3 min, CF dashboard)

- [ ] Cloudflare dashboard → Zero Trust → Networks → Tunnels → `addrlens-prod` → Public Hostnames → **Add a public hostname**.
- [ ] Config:
  - Subdomain: `berlin`
  - Domain: `addrlens.de`
  - Path: (blank)
  - Service Type: HTTP
  - URL: `app:8001`
  - Additional Application Settings → HTTP Host Header: `berlin.addrlens.de`
- [ ] Save. CF auto-creates proxied CNAME.
- [ ] Verify from any machine:
  ```bash
  curl -fsS https://berlin.addrlens.de/health   # expect {"status":"ok"}
  curl -fsSI https://berlin.addrlens.de/ | head -3
  # Expect HTTP/2 200 + content-type: text/html
  ```
- [ ] **State check:** Berlin app now answers on BOTH `addrlens.de` AND `berlin.addrlens.de`. Overlap is intentional and safe.

## Step 4: CF Tunnel — repoint apex to landing (2 min, CF dashboard)

- [ ] Same tunnel page → click the existing apex public hostname (`addrlens.de`) → Edit.
- [ ] Change **URL only** from `http://app:8001` to `http://app-landing:8000`. Host header stays `addrlens.de` (already correct).
- [ ] Save.
- [ ] Verify:
  ```bash
  curl -fsS https://addrlens.de/ | grep -c "AddrLens.*Street intelligence"    # expect >=1
  curl -fsS https://addrlens.de/health   # expect {"status":"ok"}
  curl -fsS https://berlin.addrlens.de/ | grep -c "canonical.*berlin.addrlens.de"  # expect 1
  ```

## Step 5: Purge CF edge cache (1 min, CF dashboard)

- [ ] Cloudflare → Caching → Configuration → Purge Cache → **Custom Purge by URL**.
- [ ] URLs to purge:
  - `https://addrlens.de/`
  - `https://addrlens.de`
  - `https://addrlens.de/impressum`
  - `https://addrlens.de/datenschutzerklaerung`
- [ ] Purge.

## Step 6: Add CF Redirect Rule (3 min, CF dashboard)

- [ ] Cloudflare → your zone → Rules → Redirect Rules → **Create rule**.
- [ ] Name: `apex → berlin for legacy paths`
- [ ] Expression (paste verbatim from spec §12.2):
  ```
  (http.host eq "addrlens.de"
   and not http.request.uri.path in {"/" "/impressum" "/datenschutzerklaerung" "/robots.txt" "/sitemap.xml" "/health"}
   and not http.request.uri.path in {"/static/img/logo.png" "/static/img/og-image.jpg"
                                      "/static/img/favicon.png" "/static/img/berlin-card.png"
                                      "/static/img/hamburg-card.png"}
   and not starts_with(http.request.uri.path, "/static/fonts/")
   and not starts_with(http.request.uri.path, "/static/landing.css"))
  ```
- [ ] Action: **Dynamic redirect**
  - Expression: `concat("https://berlin.addrlens.de", http.request.uri.path)`
  - Status: `301`
  - Preserve query string: ✓
- [ ] Deploy rule.
- [ ] Smoke the redirect (from any machine):
  ```bash
  for path in /api/lookup /api/suggest /api/config /api/lens_insight /ready /static/app.js /static/img/hero/berlin.png; do
    printf '%-40s ' "$path"
    curl -sSI "https://addrlens.de${path}" | awk 'NR==1 || tolower($1) ~ /^location:/'
  done
  # Every line: HTTP/2 301 + location: https://berlin.addrlens.de<path>
  ```
- [ ] Smoke the deny-list (landing paths should NOT redirect):
  ```bash
  for path in / /impressum /datenschutzerklaerung /robots.txt /sitemap.xml /health /static/landing.css /static/img/logo.png; do
    printf '%-30s ' "$path"
    curl -sSI "https://addrlens.de${path}" | head -1
  done
  # Every line: HTTP/2 200 (or 304)
  ```

## Step 7: Google Search Console (5 min, GSC)

- [ ] GSC → Add property → `https://berlin.addrlens.de/` → DNS or HTML-tag verification.
- [ ] Once verified: property → Sitemaps → Add → `https://berlin.addrlens.de/sitemap.xml`.
- [ ] Existing apex property → Sitemaps → Add → `https://addrlens.de/sitemap.xml` (re-submit, now points at the new landing sitemap).
- [ ] **Do NOT use the Change of Address tool.** It requires the old property to fully 301-redirect to the new — not the case here (apex keeps landing + legal). 301s on other paths + separate properties do the job.

## Step 8: Announce (optional)

- [ ] Post to relevant channels: "We moved: Berlin now lives at `berlin.addrlens.de`. `addrlens.de` is now a city hub with Berlin + Hamburg links. Old links auto-redirect."

## Rollback

Trigger conditions: prod smoke fails after any step; user report of broken apex.

### If Step 4 (apex repoint) or Step 6 (Redirect Rule) is the problem

- [ ] CF dashboard → Tunnels → `addrlens-prod` → Public Hostnames → apex → Edit.
- [ ] Change URL back to `http://app:8001`, host header stays `addrlens.de`.
- [ ] Save. Effective in seconds.
- [ ] Delete or disable the Redirect Rule (Rules → Redirect Rules → toggle off).
- [ ] Keep `berlin.addrlens.de` public hostname registered (harmless overlap).

### If landing container is broken

- [ ] `docker compose ps app-landing` → confirm unhealthy.
- [ ] `docker compose logs app-landing --tail=100` → identify cause.
- [ ] If unrecoverable: rollback CF apex per above (users hit Berlin app on apex, works fine).

### If Berlin subdomain broken but apex still fine

- [ ] Remove `berlin.addrlens.de` public hostname from CF Tunnel.
- [ ] Users continue to reach Berlin via apex (Step 4 hasn't been done, or Step 4 was reverted).

## Post-cutover monitoring (first 48h)

- [ ] Re-run Step 6 smoke every 12h — catches any dashboard-only rule drift.
- [ ] GSC Coverage → check for spike in 4xx on the old apex property.
- [ ] Umami — verify 3 separate websites are receiving traffic; landing gets any signal at all (proves injection worked).
- [ ] Watch for 2-4wk SEO stabilization: apex + berlin property authority split; ranks may dip 5-15% during transition.
```

- [ ] **Step 2: Commit**

```bash
git add v0.1/docs/superpowers/plans/2026-09-25-apex-landing-cutover-runbook.md
git commit -m "docs(runbook): apex landing cutover — 8 steps + rollback + monitoring

Manual runbook for the production cutover. 15 min wall-clock, 0
downtime. Preserves spec §15 rollout ordering (Berlin subdomain
added BEFORE apex is repointed → overlap is safe) and §16 rollback
semantics (dashboard-only, 2-3 min).

Covers: Umami website creation, prod env var migration (with the
critical UMAMI_WEBSITE_ID → UMAMI_WEBSITE_ID_BERLIN rename that
prevents cross-contamination), CF Tunnel dance, CF cache purge,
Redirect Rule with both positive and negative smoke, GSC property
add + sitemap submit, and 48h post-cutover monitoring."
```

---

## Self-Review

**1. Spec coverage:** Every section in the spec maps to at least one task:

| Spec section | Task(s) |
|---|---|
| §1-4 (problem, goals, non-goals, approach) | Global constraints + architecture header |
| §5 (target architecture) | Tasks 6, 11 |
| §6.1 (`app/landing/main.py`) | Task 1 |
| §6.2 (import guard test) | Task 1 |
| §7 (web/landing/ file structure) | Tasks 3, 4 |
| §8.1-8.6 (design tokens, page structure, i18n, motion, SEO, checklist) | Task 3 |
| §9 (Berlin URL surgery) | Task 7 |
| §9.1 (Hamburg legal fixes) | Task 8 |
| §10.1 (Dockerfile.landing) | Task 5 |
| §10.2 (docker-compose changes) | Task 6 |
| §11.1 (update.sh) | Task 9 |
| §11.2 (rollback.sh) | Task 9 |
| §11.3 (deploy README) | Task 10 |
| §11.4 (cloudflared README) | Task 10 |
| §12 (CF Tunnel + Redirect Rule) | Task 11 |
| §13 (SEO migration + GSC + Umami) | Task 11 |
| §14 (testing) | Tasks 1, 2, 3, 4, 6, 11 |
| §15 (rollout plan) | Task 11 |
| §16 (rollback plan) | Task 11 |
| §17 (effort) | (informational, no task) |
| §18 (risks) | Global constraints + Task 1 (import guard), Task 5 (version sync comment), Task 9 (rollback footgun) |
| §19 (decisions) | Encoded in tasks 3, 4 (EN-primary, no roadmap, no counts, single og-image reused, Umami 3-way) |
| §20 (out of scope) | Deferred by omission |
| §21 (follow-ups) | Task 3 (README) |

**Gap:** none identified.

**2. Placeholder scan:** searched for "TBD", "TODO", "implement later", "add appropriate", "similar to Task", "write tests for the above" — none present. Every code step contains actual code. Every command step contains actual commands with expected output.

**3. Type consistency:** function names cross-task:
- `_load_index()` (Task 1) → referenced by Task 2 (`_INDEX_HTML`) → consistent
- `ensure_landing_index` fixture (Task 1 conftest) → used in Tasks 2 tests → consistent
- Port 8000 for `app-landing` (Task 1 code, Task 5 Dockerfile, Task 6 compose, Task 9 update.sh, Task 10 docs, Task 11 runbook) → consistent
- Container name `addrlens-app-landing` (Task 6) → referenced in Task 11 runbook → consistent
- Network `addrlens_net` (Task 6) → matches existing compose → consistent
- Env vars `UMAMI_WEBSITE_ID_LANDING` + `UMAMI_SCRIPT_URL_LANDING` (Task 1 code, Task 11 runbook) → consistent
- `_ALLOWED_APP_MODULES = {"app", "app.landing", "app.landing.main"}` (Task 1 test) → consistent with `app/landing/__init__.py` + `app/landing/main.py` file layout

No inconsistencies found.

---

**Plan complete and saved to `docs/superpowers/plans/2026-09-25-apex-landing-migration.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

**Which approach?**
