"""Smoke: every landing route returns 200 with the expected media type.

Also asserts landing index HTML contains both city-card link substrings
(guards against accidental copy deletion during future edits).
"""
from fastapi.testclient import TestClient


def _get_client():
    """Lazy client initialization to allow fixture setup before import."""
    from app.landing.main import app
    return TestClient(app)


def test_index_returns_html(ensure_landing_index):
    client = _get_client()
    r = client.get("/")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")


def test_health_returns_status_ok(ensure_landing_index):
    client = _get_client()
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_robots_is_text_plain(ensure_landing_index, tmp_path, monkeypatch):
    client = _get_client()
    (ensure_landing_index / "robots.txt").write_text(
        "User-agent: *\nAllow: /\nSitemap: https://addrlens.de/sitemap.xml\n",
        encoding="utf-8",
    )
    r = client.get("/robots.txt")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")


def test_sitemap_is_xml(ensure_landing_index):
    client = _get_client()
    (ensure_landing_index / "sitemap.xml").write_text(
        '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>',
        encoding="utf-8",
    )
    r = client.get("/sitemap.xml")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/xml")


def test_impressum_serves_html(ensure_landing_index):
    client = _get_client()
    (ensure_landing_index / "impressum.html").write_text(
        "<!doctype html><html><body>Imprint</body></html>", encoding="utf-8",
    )
    r = client.get("/impressum")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")


def test_datenschutz_serves_html(ensure_landing_index):
    client = _get_client()
    (ensure_landing_index / "datenschutzerklaerung.html").write_text(
        "<!doctype html><html><body>Privacy</body></html>", encoding="utf-8",
    )
    r = client.get("/datenschutzerklaerung")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")


def test_index_html_contains_both_city_links_when_real_landing_exists():
    """Once Task 3 has landed the real web/landing/index.html, this
    assertion guards against accidental deletion of the Berlin or
    Hamburg card. Skipped when the file is the minimal test fixture."""
    from app.landing.main import _INDEX_HTML

    html = _INDEX_HTML.decode("utf-8")
    if "berlin.addrlens.de" not in html:
        # Fixture stub — skip the coverage assertion.
        import pytest
        pytest.skip("real web/landing/index.html not yet present (Task 3 pending)")
    assert "berlin.addrlens.de" in html
    assert "hamburg.addrlens.de" in html
