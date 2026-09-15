"""Contract tests for `POST /api/lens_insight`.

The route proxies to the inference-service (`{INFERENCE_URL}/summarize`).
We stub `httpx.AsyncClient.post` at the httpx layer so the tests never
touch the network and exercise every branch of the route body:
  - request-body shape sent to inference,
  - happy-path response shape returned to the client,
  - inference 5xx → 504 (gateway timeout) at our boundary,
  - inference RequestError (connection refused, DNS fail) → 503,
  - inference returns empty `lens_insight` → 502 upstream error.

The rate-limiter is left in place — 10/minute per IP is generous
enough that a handful of test calls per test never trips it.
"""
from unittest.mock import AsyncMock, patch

import httpx
import pytest


# --- Helpers --------------------------------------------------------


def _valid_body(lens: str = "newcomer") -> dict:
    """Minimum body the route accepts — mirrors the SPA payload."""
    return {
        "lens": lens,
        "address": {
            "lat": 52.5219, "lon": 13.4132,
            "bezirk": "Mitte", "ortsteil": "Mitte",
        },
        "tiles": [
            {"key": "buergeramt", "label": "Bürgeramt reach",
             "tier": "green", "rule": "≥1 within 15 min",
             "numeric": "14 min", "caveat": None},
        ],
    }


def _fake_response(status: int, body: dict) -> httpx.Response:
    """Build an httpx.Response the same way the real client would."""
    return httpx.Response(status_code=status, json=body,
                          request=httpx.Request("POST", "http://x/summarize"))


def _clear_lens_cache():
    """Drop the shared HISTORY cache so cached entries from an earlier
    test can't mask a fresh call. lens_insight namespaces its keys with
    `("lens_insight", ...)` so this is safe."""
    from app.core.cache import HISTORY
    HISTORY.clear()


# --- Contract tests -------------------------------------------------


def test_lens_insight_forwards_expected_payload_to_inference(client):
    _clear_lens_cache()
    happy = _fake_response(200, {
        "summary": {"lens_insight": {
            "executive_summary": "Test summary.",
            "sections": [], "highlights_green": [], "highlights_red": [],
        }},
        "model": "@cf/meta/llama-3.1-8b-instruct-fast",
    })

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=happy)) as post:
        r = client.post("/api/lens_insight", json=_valid_body("newcomer"))

    assert r.status_code == 200
    # Post was called once against /summarize.
    assert post.await_count == 1
    _, kwargs = post.call_args
    sent = kwargs["json"]
    # Contract with inference-service: template name + city slug + context.
    assert sent["template"] == "lens_newcomer_insight"
    assert sent["city"] == "berlin"
    # tile_contexts is the trimmed schema (no `features`, no `extras`).
    tiles = sent["context"]["tile_contexts"]
    assert len(tiles) == 1
    assert tiles[0]["key"] == "buergeramt"
    assert set(tiles[0].keys()) == {"key", "label", "tier", "rule", "numeric", "caveat"}


def test_lens_insight_happy_path_response_shape(client):
    _clear_lens_cache()
    happy = _fake_response(200, {
        "summary": {"lens_insight": {
            "executive_summary": "A concise 2-3 sentence summary.",
            "sections": [{"title": "Admin", "tiles": [], "verdict": "green",
                          "note": ""}],
            "highlights_green": [{"tile": "buergeramt", "one_line": "close"}],
            "highlights_red":   [],
        }},
        "model": "@cf/meta/llama-3.1-8b-instruct-fast",
    })

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=happy)):
        body = client.post("/api/lens_insight", json=_valid_body()).json()

    assert "lens_insight" in body
    assert body["lens_insight"]["executive_summary"].startswith("A concise")
    assert body["model"] == "@cf/meta/llama-3.1-8b-instruct-fast"
    assert body["cached"] is False


def test_lens_insight_rejects_unknown_lens(client):
    # Malicious / typo lens slug — no inference call should be issued.
    with patch("httpx.AsyncClient.post", new=AsyncMock()) as post:
        r = client.post("/api/lens_insight",
                        json={**_valid_body(), "lens": "zeus"})
    assert r.status_code == 400
    assert post.await_count == 0


def test_lens_insight_5xx_from_inference_returns_504_degraded(client):
    _clear_lens_cache()
    boom = _fake_response(500, {"detail": "model crashed"})
    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=boom)):
        r = client.post("/api/lens_insight", json=_valid_body())
    # Route classifies inference 5xx as an upstream gateway timeout (504)
    # so the SPA hides the panel gracefully. Status code preserved for
    # monitoring; structured body lets the SPA branch on error_code.
    assert r.status_code == 504
    assert r.headers.get("Retry-After") == "30"
    body = r.json()
    assert body["degraded"] is True
    assert body["error_code"] == "INFERENCE_UPSTREAM"
    assert "500" in body["error"]
    assert body["retry_after_seconds"] == 30


def test_lens_insight_transport_error_returns_503_degraded(client):
    _clear_lens_cache()
    # RequestError == connection refused / DNS failure / TLS reset. Route
    # returns 503 with a degraded body so the SPA can surface a
    # "temporarily unavailable" message without a hard error toast.
    err = httpx.ConnectError("nope", request=httpx.Request("POST", "http://x/"))
    with patch("httpx.AsyncClient.post", new=AsyncMock(side_effect=err)):
        r = client.post("/api/lens_insight", json=_valid_body())
    assert r.status_code == 503
    assert r.headers.get("Retry-After") == "60"
    body = r.json()
    assert body["degraded"] is True
    assert body["error_code"] == "INFERENCE_UNREACHABLE"
    assert body["retry_after_seconds"] == 60


def test_lens_insight_timeout_returns_503_degraded(client):
    _clear_lens_cache()
    # TimeoutException is distinct from RequestError — model warm-up or
    # slow generation. Shorter retry_after because odds of recovery on
    # next attempt are higher than for full-unreachable.
    err = httpx.ReadTimeout("slow", request=httpx.Request("POST", "http://x/"))
    with patch("httpx.AsyncClient.post", new=AsyncMock(side_effect=err)):
        r = client.post("/api/lens_insight", json=_valid_body())
    assert r.status_code == 503
    assert r.headers.get("Retry-After") == "30"
    body = r.json()
    assert body["degraded"] is True
    assert body["error_code"] == "INFERENCE_TIMEOUT"


def test_lens_insight_empty_lens_insight_returns_502_degraded(client):
    _clear_lens_cache()
    # Model returned an object but no executive_summary — route refuses
    # to cache an empty summary and surfaces the failure to the SPA
    # with a specific error_code so the SPA can nudge a retry.
    empty = _fake_response(200, {
        "summary": {"lens_insight": {"executive_summary": ""}},
        "model": "x",
    })
    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=empty)):
        r = client.post("/api/lens_insight", json=_valid_body())
    assert r.status_code == 502
    body = r.json()
    assert body["degraded"] is True
    assert body["error_code"] == "INFERENCE_EMPTY"
    assert body["retry_after_seconds"] == 15


def test_lens_insight_non_json_body_returns_502_degraded(client):
    """Regression guard for the r.json() decode-failure path.

    Cloudflare captive-portal HTML, corporate proxy interstitials, WAF
    error pages, and inference-side bugs can return HTTP 200 with a
    non-JSON body. Without the try/except around r.json(), FastAPI
    converts the JSONDecodeError into an opaque HTTP 500 — defeating
    the entire degradation layer this module exists for.
    """
    _clear_lens_cache()
    # 200 OK with HTML body — the classic CF-captive / proxy failure mode.
    html_resp = httpx.Response(
        status_code=200,
        content=b"<html><body>You are behind a firewall.</body></html>",
        headers={"content-type": "text/html"},
        request=httpx.Request("POST", "http://x/summarize"),
    )
    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=html_resp)):
        r = client.post("/api/lens_insight", json=_valid_body())
    assert r.status_code == 502
    body = r.json()
    assert body["degraded"] is True
    assert body["error_code"] == "INFERENCE_BAD_OUTPUT"
    assert "malformed" in body["error"].lower()


def test_lens_insight_upstream_4xx_returns_503_degraded(client):
    _clear_lens_cache()
    # Inference 4xx = template contract violation / schema failure after
    # two Cloudflare retries. Surfaced as degraded so the SPA hides the
    # panel gracefully instead of showing a raw HTTP 400/422 error toast.
    bad = _fake_response(422, {"detail": "schema validation failed"})
    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=bad)):
        r = client.post("/api/lens_insight", json=_valid_body())
    assert r.status_code == 503
    body = r.json()
    assert body["degraded"] is True
    assert body["error_code"] == "INFERENCE_BAD_OUTPUT"
