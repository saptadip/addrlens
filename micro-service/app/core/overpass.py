"""OSM Overpass helper with tiered mirror rotation. Verbatim from phase3/server.py.

Mirror rotation is the cold-cache path only — Ship D step 2 adds a server-side
response cache in front of Overpass keyed by rounded lat/lon.
"""
import json
import sys
import urllib.parse
import urllib.request

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]


def overpass(ql, timeout_s=60):
    """Try Overpass mirrors in order with tiered per-mirror timeouts.
    Early mirrors get a short budget (fast-fail so we move on quickly);
    the last mirror gets the full timeout as a final chance. Total worst-case
    wait is roughly timeout_s instead of timeout_s × len(mirrors)."""
    # Tiered budgets: first mirror fails fast, later ones get more room.
    # For timeout_s=75 this is [25, 40, 75] → ~140s worst case vs. 225s before.
    per_mirror = [min(timeout_s, 25), min(timeout_s, 40), timeout_s]
    last_err = None
    for i, url in enumerate(OVERPASS_ENDPOINTS):
        t = per_mirror[i] if i < len(per_mirror) else timeout_s
        try:
            req = urllib.request.Request(
                url, data=urllib.parse.urlencode({"data": ql}).encode(),
                headers={"User-Agent": "berlin-family-address-intel/0.1"})
            return json.loads(urllib.request.urlopen(req, timeout=t).read())
        except Exception as e:
            last_err = e
            print(f"overpass: {url} failed after ~{t}s "
                  f"({type(e).__name__}: {str(e)[:120]}); trying next mirror",
                  file=sys.stderr)
    # Include which mirror was tried last so the client-facing error is actionable.
    raise RuntimeError(f"all overpass mirrors failed; last: {type(last_err).__name__}: {last_err}")


if __name__ == "__main__":
    # Mirror-rotation asserts copied verbatim from phase3/server.py:_selfcheck.
    import io
    calls = []
    real_urlopen = urllib.request.urlopen

    def _fake_urlopen(req, timeout=None):
        calls.append((req.full_url, timeout))
        if len(calls) == 1:
            raise TimeoutError("simulated first-mirror timeout")
        return io.BytesIO(b'{"elements": [{"tag": "ok"}]}')

    urllib.request.urlopen = _fake_urlopen
    try:
        got = overpass("out;", timeout_s=75)
        assert got == {"elements": [{"tag": "ok"}]}
        assert len(calls) == 2, f"expected 2 mirror attempts, got {len(calls)}"
        assert calls[0][1] == 25, f"first mirror should get short 25s budget, got {calls[0][1]}"
        assert calls[1][1] == 40, f"second mirror should get 40s budget, got {calls[1][1]}"
    finally:
        urllib.request.urlopen = real_urlopen

    # All mirrors fail ⇒ RuntimeError naming the last exception type.
    calls.clear()

    def _all_fail(req, timeout=None):
        calls.append(req.full_url)
        raise TimeoutError("boom")

    urllib.request.urlopen = _all_fail
    try:
        try:
            overpass("out;", timeout_s=75)
            assert False, "expected RuntimeError"
        except RuntimeError as e:
            assert "all overpass mirrors failed" in str(e)
            assert "TimeoutError" in str(e)
        assert len(calls) == len(OVERPASS_ENDPOINTS)
    finally:
        urllib.request.urlopen = real_urlopen
    print("overpass.py selfcheck OK")
