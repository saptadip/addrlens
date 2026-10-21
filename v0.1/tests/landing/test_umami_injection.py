"""Umami tag injection: when the LANDING-suffixed env vars are set at
module import, _load_index() replaces the <!-- UMAMI-INJECT --> marker
with a real <script> tag. When unset, the marker is left as-is.

Both env vars must be set to trigger injection — either alone is a no-op
(fail-safe against half-configured envs).
"""
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
