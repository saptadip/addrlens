"""Contract tests for `GET /api/history`.

The route reads `historic=*` OSM features within 500 m of the given
lat/lon from `Index.osm_local`, shapes them into the inference `history`
template's payload, and returns a one-paragraph AI narrative.

We stub `httpx.AsyncClient.post` at the httpx layer + populate
`fake_index.osm_local` with a single fake feature so the request/response
contract is exercised without the network or the LLM.
"""
from unittest.mock import AsyncMock, patch

import httpx


def _fake_response(status: int, body: dict) -> httpx.Response:
    return httpx.Response(status_code=status, json=body,
                          request=httpx.Request("POST", "http://x/summarize"))


def _clear_history_cache():
    """Drop cached entries so a repeat lat/lon in another test doesn't
    short-circuit the LLM call this test needs to observe."""
    from app.core.cache import HISTORY
    HISTORY.clear()


class _FakeOSMWithFeatures:
    """OSM-local snapshot stub that returns one historic feature per call."""

    def __init__(self, features):
        self._features = features

    def near(self, cat, lon, lat, radius_m):
        # Only respond to the `historic` category the route asks for; every
        # other category (used by lookup) still returns [].
        return list(self._features) if cat == "historic" else []


# --- Contract tests ------------------------------------------------


def test_history_forwards_expected_payload_to_inference(client, fake_index):
    _clear_history_cache()
    fake_index.osm_local = _FakeOSMWithFeatures([
        {"name": "Stolperstein Hans Meyer",
         "distance_m": 120,
         "tags": {"historic": "memorial",
                  "inscription": "In memoriam 1938",
                  "start_date": "1938",
                  "wikipedia": "de:Stolpersteine"}},
    ])

    happy = _fake_response(200, {
        "summary": {"history": "A short narrative about the block."},
        "model": "llama-3",
    })
    with patch("httpx.AsyncClient.post",
               new=AsyncMock(return_value=happy)) as post:
        r = client.get("/api/history", params={
            "lat": 52.5219, "lon": 13.4132,
            "bezirk": "Mitte", "ortsteil": "Mitte",
        })

    assert r.status_code == 200
    _, kwargs = post.call_args
    sent = kwargs["json"]
    # Contract with inference-service: template + city + shaped features.
    assert sent["template"] == "history"
    assert sent["city"] == "berlin"
    assert sent["context"]["bezirk"] == "Mitte"
    features = sent["context"]["features"]
    assert len(features) == 1
    assert features[0]["name"] == "Stolperstein Hans Meyer"
    # Route deliberately drops street/hnr/plz from the prompt payload —
    # the cache is per ~100 m grid cell so an address-specific opener
    # would poison neighbouring lookups.
    assert "street" not in sent["context"]
    assert "hnr" not in sent["context"]
    assert "plz" not in sent["context"]


def test_history_happy_path_response_shape(client, fake_index):
    _clear_history_cache()
    fake_index.osm_local = _FakeOSMWithFeatures([
        {"name": "Stolperstein X", "distance_m": 80,
         "tags": {"historic": "memorial", "inscription": "..."}},
    ])
    happy = _fake_response(200, {
        "summary": {"history": "A one-paragraph narrative."},
        "model": "llama-3",
    })
    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=happy)):
        body = client.get("/api/history",
                          params={"lat": 52.5, "lon": 13.4}).json()

    assert body["history"] == "A one-paragraph narrative."
    assert body["features_count"] == 1
    assert body["model"] == "llama-3"
    assert body["cached"] is False


def test_history_short_circuits_when_no_features(client, fake_index):
    _clear_history_cache()
    fake_index.osm_local = _FakeOSMWithFeatures([])   # empty snapshot
    # No LLM call is issued — the route returns a canned "no history" line.
    with patch("httpx.AsyncClient.post", new=AsyncMock()) as post:
        r = client.get("/api/history",
                       params={"lat": 52.6, "lon": 13.5}).json()
    assert post.await_count == 0
    assert r["features_count"] == 0
    assert r["model"] == "none"
    assert "No historic points" in r["history"]


def test_history_503_when_snapshot_missing(client, fake_index):
    _clear_history_cache()
    # Deployment without the local OSM snapshot (Overpass-only mode).
    fake_index.osm_local = None
    r = client.get("/api/history", params={"lat": 52.5, "lon": 13.4})
    assert r.status_code == 503
    assert "local OSM snapshot" in r.json()["detail"]


def test_history_transport_error_returns_503(client, fake_index):
    _clear_history_cache()
    fake_index.osm_local = _FakeOSMWithFeatures([
        {"name": "Stolperstein X", "distance_m": 80,
         "tags": {"historic": "memorial", "inscription": "..."}},
    ])
    err = httpx.ConnectError("nope", request=httpx.Request("POST", "http://x/"))
    with patch("httpx.AsyncClient.post", new=AsyncMock(side_effect=err)):
        r = client.get("/api/history", params={"lat": 52.5, "lon": 13.4})
    assert r.status_code == 503
