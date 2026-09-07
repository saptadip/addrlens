"""Contract tests for `/health` + `/ready`.

/health = liveness (200 unconditionally).
/ready  = readiness (200 iff Index is loaded; 503 while cold).
"""
import pytest


def test_health_liveness_always_200(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"


def test_ready_shape_when_index_present(client):
    # The `client` fixture wires `app.state.index` to the fake index, so
    # /ready should report ready + carry the city slug.
    r = client.get("/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ready"
    assert body["city"] == "berlin"


def test_ready_returns_503_when_index_missing(berlin_config, monkeypatch):
    """503 is the pre-boot readiness signal for orchestrators."""
    from fastapi.testclient import TestClient
    from app.main import app

    # Force the "cold" branch by clearing the state attribute.
    prior = getattr(app.state, "index", None)
    if hasattr(app.state, "index"):
        delattr(app.state, "index")
    try:
        tc = TestClient(app)
        r = tc.get("/ready")
        assert r.status_code == 503
        assert r.json()["status"] == "loading"
    finally:
        if prior is not None:
            app.state.index = prior


def test_lifespan_fires_and_populates_state(monkeypatch, berlin_config):
    """Smoke-test the FastAPI lifespan handler end-to-end.

    Every other test in this suite constructs a bare `TestClient(app)`
    without the `with:` context manager, which SKIPS the lifespan
    handler (so `app.main.lifespan` never runs). That's fine for the
    per-route contract tests — but it means a regression in the lifespan
    body (bad Index kwarg, wrong `load_city` call, silent exception in
    `_load_*`) would land on `main` unnoticed by the test suite.

    This test wraps `TestClient` in `with:` so the lifespan actually
    fires. To keep it fast (< 1 s vs. the ~10 s WFS-heavy real path)
    we monkeypatch `Index.__init__` to a no-op that populates just the
    handful of attributes `/ready` and the routes read.
    """
    from fastapi.testclient import TestClient

    import app.main as main_mod
    from app.core.index import Index

    def _fake_init(self, cfg):
        # Populate only what /ready looks at — every other attribute
        # would be exercised by follow-on route tests, not this smoke.
        self.cfg = cfg

    monkeypatch.setattr(Index, "__init__", _fake_init)

    # Preserve + restore app.state so this test does not leak into the
    # session-scoped `client` fixture.
    prior_index = getattr(main_mod.app.state, "index", None)
    prior_city  = getattr(main_mod.app.state, "city", None)
    try:
        with TestClient(main_mod.app) as tc:
            # Lifespan startup has completed by the time the context
            # manager yields — /ready must be 200 with the city slug.
            r = tc.get("/ready")
            assert r.status_code == 200
            body = r.json()
            assert body["status"] == "ready"
            assert body["city"] == "berlin"
            # /health is orthogonal and must also be 200 inside the
            # lifespan window.
            assert tc.get("/health").status_code == 200
    finally:
        main_mod.app.state.index = prior_index
        main_mod.app.state.city  = prior_city
