"""Contract tests for the security-headers middleware in `app/main.py`.

Every response must carry the content-agnostic hardening headers
(X-Content-Type-Options, Referrer-Policy, Permissions-Policy,
X-Frame-Options). HTML responses additionally carry
Content-Security-Policy. JSON API responses do NOT — browsers do not
render them as documents, so a CSP header on `/api/config` would be
noise on every request.
"""


def _assert_baseline_security_headers(response):
    """Content-agnostic headers that must be present on every response."""
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert response.headers.get("X-Frame-Options") == "DENY"
    pp = response.headers.get("Permissions-Policy", "")
    for feature in ("geolocation=()", "microphone=()", "camera=()"):
        assert feature in pp, f"{feature!r} missing from Permissions-Policy"


# --- Baseline headers on every response ------------------------------------

def test_health_response_has_baseline_headers(client):
    r = client.get("/health")
    _assert_baseline_security_headers(r)


def test_api_config_has_baseline_headers(client):
    r = client.get("/api/config")
    _assert_baseline_security_headers(r)


def test_api_lookup_has_baseline_headers(client):
    r = client.get("/api/lookup",
                   params={"address": "Kastanienallee 12, 10435"})
    _assert_baseline_security_headers(r)


def test_impressum_has_baseline_headers_and_csp(client):
    """Legal page is served via FileResponse — must still get CSP."""
    r = client.get("/impressum")
    _assert_baseline_security_headers(r)
    assert "Content-Security-Policy" in r.headers


def test_datenschutz_has_baseline_headers_and_csp(client):
    """Datenschutzerklärung is served via FileResponse — must still get CSP."""
    r = client.get("/datenschutzerklaerung")
    _assert_baseline_security_headers(r)
    assert "Content-Security-Policy" in r.headers


# --- CSP on HTML only ------------------------------------------------------

def test_html_root_has_csp_header(client):
    r = client.get("/")
    csp = r.headers.get("Content-Security-Policy", "")
    assert csp, "CSP missing from HTML response"
    # Every directive the middleware sets must be present.
    for directive in (
        "default-src 'self'",
        "script-src ",
        "style-src ",
        "font-src ",
        "img-src ",
        "connect-src ",
        "frame-ancestors 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "object-src 'none'",
    ):
        assert directive in csp, f"CSP missing directive: {directive!r}"


def test_csp_permits_leaflet_cdn(client):
    """Leaflet is loaded from unpkg.com — both JS and CSS."""
    csp = client.get("/").headers.get("Content-Security-Policy", "")
    # Extract script-src fragment for a precise assertion.
    script_src = _directive(csp, "script-src")
    style_src  = _directive(csp, "style-src")
    assert "https://unpkg.com" in script_src, script_src
    assert "https://unpkg.com" in style_src,  style_src


def test_csp_permits_google_fonts(client):
    csp = client.get("/").headers.get("Content-Security-Policy", "")
    style_src = _directive(csp, "style-src")
    font_src  = _directive(csp, "font-src")
    assert "https://fonts.googleapis.com" in style_src, style_src
    assert "https://fonts.gstatic.com"    in font_src,  font_src


def test_csp_permits_osm_tiles(client):
    csp = client.get("/").headers.get("Content-Security-Policy", "")
    img_src = _directive(csp, "img-src")
    assert "https://*.tile.openstreetmap.org" in img_src, img_src
    assert "data:" in img_src, img_src  # Leaflet marker shadow


def test_csp_blocks_inline_scripts(client):
    """No `'unsafe-inline'` in script-src — the SPA has zero inline scripts."""
    csp = client.get("/").headers.get("Content-Security-Policy", "")
    script_src = _directive(csp, "script-src")
    assert "'unsafe-inline'" not in script_src, (
        f"script-src accidentally allows 'unsafe-inline': {script_src!r}"
    )


def test_csp_permits_inline_styles_for_leaflet(client):
    """Leaflet writes element.style.* at runtime — 'unsafe-inline' required."""
    csp = client.get("/").headers.get("Content-Security-Policy", "")
    style_src = _directive(csp, "style-src")
    assert "'unsafe-inline'" in style_src, style_src


# --- CSP absent on API responses -------------------------------------------

def test_api_config_has_no_csp(client):
    """CSP is browser-content-only; JSON API responses skip it."""
    r = client.get("/api/config")
    assert "Content-Security-Policy" not in r.headers


def test_api_lookup_has_no_csp(client):
    r = client.get("/api/lookup",
                   params={"address": "Kastanienallee 12, 10435"})
    assert "Content-Security-Policy" not in r.headers


# --- helpers ---------------------------------------------------------------

def _directive(csp: str, name: str) -> str:
    """Return the value of a single CSP directive, empty string if absent."""
    for chunk in csp.split(";"):
        chunk = chunk.strip()
        if chunk.startswith(name + " ") or chunk == name:
            return chunk[len(name):].strip()
    return ""
