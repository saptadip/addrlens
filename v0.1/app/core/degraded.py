"""Structured 503 responses for LLM-backed endpoints when the inference
layer is unreachable / times out / returns empty / errors upstream.

Frontend catches the structured body + specific `error_code` and shows
a per-code user-facing message instead of a generic "HTTP 5xx" toast.
The tile grid (which comes from `/api/lookup`, not the LLM endpoints)
keeps rendering independently — the site stays usable when the LLM
layer is degraded.

Related endpoints:
  - POST /api/lens_insight    (app/routes/lens_insight.py)
  - GET  /api/history         (app/routes/history.py)

Design decisions:
  - HTTP status codes kept distinct (502/503/504) for monitoring +
    log aggregation, but every degraded response carries the same
    structured body so the SPA can handle them uniformly.
  - `Retry-After` header is set AND echoed in the JSON body so the SPA
    can schedule a retry or show a countdown without parsing headers.
  - `error` field name matches the existing `formatApiError` shape at
    `web/static/modules/dom.js`, so no frontend helper changes are
    needed to display the message; `error_code` is additive and lets
    the SPA branch on specific cases (e.g. suppress retry button when
    the code is `INFERENCE_UNREACHABLE` for the third time in a row).
"""
from fastapi.responses import JSONResponse


# Error codes surfaced to the frontend. Adding a new code = also add
# its per-code UX handling in `web/static/modules/lens/ai.js` if the
# generic "AI insight temporarily unavailable" message isn't specific
# enough for that failure class.
INFERENCE_UNREACHABLE = "INFERENCE_UNREACHABLE"    # network error, DNS, connection refused
INFERENCE_TIMEOUT     = "INFERENCE_TIMEOUT"        # httpx.TimeoutException
INFERENCE_UPSTREAM    = "INFERENCE_UPSTREAM"       # inference-service returned 5xx
INFERENCE_BAD_OUTPUT  = "INFERENCE_BAD_OUTPUT"     # inference-service returned 4xx (template failure)
INFERENCE_EMPTY       = "INFERENCE_EMPTY"          # inference-service returned OK but empty payload


def degraded_ai_response(
    error_code: str,
    message: str,
    *,
    status_code: int = 503,
    retry_after_seconds: int = 30,
) -> JSONResponse:
    """Build a graceful-degradation JSON response for an LLM endpoint.

    Args:
      error_code: one of the module-level `INFERENCE_*` constants
        (or any short screaming-snake identifier). Surfaced to the SPA
        for programmatic branching.
      message: user-facing sentence — will render verbatim in the SPA
        error slot via `formatApiError`. Keep short (<200 chars).
      status_code: HTTP status. Default 503 (Service Unavailable).
        Callers can pass 502 (Bad Gateway) for malformed upstream
        replies or 504 (Gateway Timeout) for upstream latency — the
        distinction is preserved for monitoring / status-page tools
        while the SPA treats all three uniformly.
      retry_after_seconds: hint for when the SPA (or a downstream
        orchestrator) should retry. Echoed in both the `Retry-After`
        HTTP header and the JSON body.
    """
    return JSONResponse(
        status_code=status_code,
        headers={"Retry-After": str(retry_after_seconds)},
        content={
            "degraded":             True,
            "error_code":           error_code,
            "error":                message,
            "retry_after_seconds":  retry_after_seconds,
        },
    )


if __name__ == "__main__":
    # Pure asserts — no network, no FastAPI app required. Verifies the
    # response envelope shape the SPA depends on.
    import json

    # -- Default shape ---------------------------------------------------
    r = degraded_ai_response(INFERENCE_TIMEOUT, "It timed out.")
    assert r.status_code == 503, r.status_code
    assert r.headers.get("Retry-After") == "30"
    body = json.loads(r.body)
    assert body == {
        "degraded":             True,
        "error_code":           "INFERENCE_TIMEOUT",
        "error":                "It timed out.",
        "retry_after_seconds":  30,
    }, body

    # -- Custom status + retry_after -------------------------------------
    r = degraded_ai_response(INFERENCE_UPSTREAM, "Upstream 500.",
                              status_code=504, retry_after_seconds=15)
    assert r.status_code == 504, r.status_code
    assert r.headers.get("Retry-After") == "15"
    body = json.loads(r.body)
    assert body["error_code"] == "INFERENCE_UPSTREAM"
    assert body["retry_after_seconds"] == 15
    assert body["degraded"] is True

    # -- Empty output (upstream OK but no content) ----------------------
    r = degraded_ai_response(INFERENCE_EMPTY, "Empty summary.",
                              status_code=502, retry_after_seconds=10)
    assert r.status_code == 502
    body = json.loads(r.body)
    assert body["error_code"] == "INFERENCE_EMPTY"

    # -- Error-code constants are the exact strings the SPA depends on --
    # Adding / renaming a constant must also update the SPA per-code
    # branching in `web/static/modules/lens/ai.js`.
    assert INFERENCE_UNREACHABLE == "INFERENCE_UNREACHABLE"
    assert INFERENCE_TIMEOUT     == "INFERENCE_TIMEOUT"
    assert INFERENCE_UPSTREAM    == "INFERENCE_UPSTREAM"
    assert INFERENCE_BAD_OUTPUT  == "INFERENCE_BAD_OUTPUT"
    assert INFERENCE_EMPTY       == "INFERENCE_EMPTY"

    print("core.degraded selfcheck OK")
