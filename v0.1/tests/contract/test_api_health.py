"""Contract tests for `/health` + `/ready`.

/health = liveness (200 unconditionally).
/ready  = readiness (200 iff Index is loaded; 503 while cold).
"""


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
