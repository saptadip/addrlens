"""Per-IP rate limiting shared across the app.

We sit behind Cloudflare Tunnel in production: `request.client.host` is the
IP of the `cloudflared` container on the internal Docker bridge, identical
for every real client. The real client IP lives in the `CF-Connecting-IP`
header (always set by CF on tunnel-routed traffic).

Local dev (bare uvicorn or docker-compose without a tunnel) has no CF
header, so we fall back to X-Forwarded-For and then `request.client.host`.

Limits are per-IP + per-route. slowapi stores counters in-process (default
in-memory backend), which is fine for the single-process uvicorn we run in
prod. If we scale horizontally the counters need Redis — env-toggle later.
"""
from __future__ import annotations

from fastapi import Request
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address


def _client_ip(request: Request) -> str:
    """Return the effective client IP, honouring CF-Connecting-IP first."""
    cf = request.headers.get("cf-connecting-ip")
    if cf:
        return cf.strip()
    xff = request.headers.get("x-forwarded-for")
    if xff:
        # X-Forwarded-For is a comma-separated chain; the first entry is the
        # closest to the origin client. Strip whitespace.
        return xff.split(",", 1)[0].strip()
    return get_remote_address(request)


# Module-level singleton — imported by main.py and by each router that
# wants to decorate an endpoint. Default in-memory storage.
limiter = Limiter(key_func=_client_ip, default_limits=[])


__all__ = ["limiter", "RateLimitExceeded", "_client_ip"]


if __name__ == "__main__":
    # Pure selfcheck — no server. Fake a Request-like object.
    class _Fake:
        def __init__(self, headers, host="127.0.0.1"):
            self.headers = headers
            self.client = type("C", (), {"host": host})()

    # CF header wins.
    assert _client_ip(_Fake({"cf-connecting-ip": "203.0.113.7",
                              "x-forwarded-for": "198.51.100.1"})) == "203.0.113.7"
    # Falls back to XFF first entry.
    assert _client_ip(_Fake({"x-forwarded-for": "198.51.100.1, 172.18.0.3"})) \
        == "198.51.100.1"
    # Local dev — no headers.
    assert _client_ip(_Fake({}, host="127.0.0.1")) == "127.0.0.1"
    # Lookups use lowercase keys — Starlette's Headers dict is case-insensitive
    # in production, so the code passes lowercase strings to .get(). The fake
    # dict here is case-sensitive, so we only assert the shape the code
    # actually depends on.
    assert _client_ip(_Fake({"cf-connecting-ip": "203.0.113.9"})) == "203.0.113.9"
    print("rate_limit.py selfcheck OK")
