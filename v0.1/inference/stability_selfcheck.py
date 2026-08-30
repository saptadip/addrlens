"""Async / timeout selfcheck for `inference.main`.

Pure — no model, no network. Uses `starlette.testclient` and
`httpx.AsyncClient` on the ASGI transport to exercise the three
stability guarantees the /summarize handler is supposed to give:

1. A slow template's generation returns 504 within
   `INFERENCE_GENERATION_TIMEOUT_S` instead of hanging the caller.
2. While /summarize is generating, /health remains responsive — proof
   that `asyncio.to_thread` is holding the blocking call off the event
   loop.
3. The remote backend init happens synchronously in `lifespan` before
   the local-loader thread is spawned — proof that a remote-only deploy
   can serve remote-eligible templates at t=0.

Run: `python -m inference.stability_selfcheck`. Emits a single OK line
on success; any assertion failure exits non-zero so the orchestrator
(`inference/selfcheck.py`) picks it up.
"""
from __future__ import annotations

import asyncio
import os
import sys
import time


def _prepare_module():
    """Import `inference.main` with a tight timeout so the selfcheck stays
    fast even if a future change adds a slow module-level init step.
    We pick 1.5 s — just above the module's 1.0 s floor — so the sleep
    durations below stay tight but never bump into the clamp.

    Stubs `_load_local_backend` to a no-op so the `TestClient` context
    doesn't spawn a background thread that tries to load MLX / llama.cpp
    in real time (which prints boot logs mid-selfcheck and races the
    process exit at teardown). Individual tests restore or override
    when they explicitly test lifespan wiring.
    """
    os.environ["INFERENCE_GENERATION_TIMEOUT_S"] = "1.5"
    import inference.main as m
    m._load_local_backend = lambda: None
    return m


class _FakeBackend:
    """Enough surface to satisfy `/summarize`'s reference to `.model_id`."""
    model_id = "test-model"


async def _assert_local_timeout_returns_504(m) -> None:
    """Register a template that sleeps past the wall-clock cap; hit
    /summarize; assert 504 with a "timed out" body."""
    from starlette.testclient import TestClient

    def _slow(_backend, _ctx):
        time.sleep(5.0)   # deliberately > INFERENCE_GENERATION_TIMEOUT_S (1.5s)
        return "unreachable"

    m._state["backend"] = _FakeBackend()
    m._state["remote"]  = None
    m.TEMPLATES["_slow_test"] = _slow
    try:
        with TestClient(m.app) as client:
            r = client.post("/summarize",
                            json={"template": "_slow_test", "context": {}})
        assert r.status_code == 504, f"expected 504, got {r.status_code}: {r.text}"
        assert "timed out" in r.text.lower(), r.text
        assert "template=_slow_test" in r.text, r.text
    finally:
        m.TEMPLATES.pop("_slow_test", None)


async def _assert_health_stays_fast_during_generation(m) -> None:
    """While a real /summarize is running (sleep 0.5 s, under the 1.5 s
    cap), /health must respond in under 100 ms. Pre-fix (`with _lock`
    inline in the async handler) `/health` would have blocked ~500 ms."""
    from httpx import ASGITransport, AsyncClient

    def _blocking(_backend, _ctx):
        time.sleep(0.5)
        return "ok"

    m._state["backend"] = _FakeBackend()
    m._state["remote"]  = None
    m.TEMPLATES["_block_test"] = _blocking
    try:
        transport = ASGITransport(app=m.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            gen = asyncio.create_task(
                client.post("/summarize",
                            json={"template": "_block_test", "context": {}}))
            # Yield briefly so the /summarize request lands and the
            # blocking sleep starts on the worker thread.
            await asyncio.sleep(0.05)
            t0 = time.perf_counter()
            hr = await client.get("/health")
            dt = time.perf_counter() - t0
            assert hr.status_code == 200, hr.text
            assert dt < 0.1, (
                f"/health blocked for {dt:.3f}s while /summarize was "
                "generating — event loop is not free")
            gr = await gen
            assert gr.status_code == 200, gr.text
    finally:
        m.TEMPLATES.pop("_block_test", None)


async def _assert_remote_init_runs_in_lifespan(m) -> None:
    """Patch `_init_remote_backend`, drive lifespan, assert exactly one
    invocation before `TestClient` becomes usable."""
    from starlette.testclient import TestClient

    calls: list[str] = []

    def _fake_init() -> None:
        calls.append("init")
        m._state["remote"] = _FakeBackend()

    m._state["backend"] = None
    m._state["remote"]  = None
    m._state["error"]   = None
    original = m._init_remote_backend
    m._init_remote_backend = _fake_init
    try:
        with TestClient(m.app) as client:
            # A no-op request just to prove lifespan has fully entered.
            client.get("/health")
        assert calls == ["init"], calls
        assert m._state["remote"] is not None
    finally:
        m._init_remote_backend = original


async def _assert_ready_reports_remote(m) -> None:
    """/ready payload should carry `remote: bool`. Distinguish
    unconfigured (False) from initialised (True). No 503 expected here
    — we set `_state['backend']` up front so /ready is 200.

    We stub `_init_remote_backend` and `_load_local_backend` so the
    `TestClient` context (which drives lifespan) doesn't overwrite the
    stubbed `_state` we care about.
    """
    from starlette.testclient import TestClient

    original_init  = m._init_remote_backend
    original_load  = m._load_local_backend
    m._init_remote_backend = lambda: None
    m._load_local_backend  = lambda: None
    try:
        # -- Case 1: remote unconfigured → /ready reports False.
        m._state["backend"] = _FakeBackend()
        m._state["remote"]  = None
        m._state["error"]   = None
        with TestClient(m.app) as client:
            r = client.get("/ready")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ready"] is True, body
        assert body["remote"] is False, body

        # -- Case 2: remote initialised → /ready reports True.
        m._state["backend"] = _FakeBackend()
        m._state["remote"]  = _FakeBackend()
        m._state["error"]   = None
        with TestClient(m.app) as client:
            r = client.get("/ready")
        body = r.json()
        assert body["remote"] is True, body
    finally:
        m._init_remote_backend = original_init
        m._load_local_backend  = original_load


async def main() -> None:
    m = _prepare_module()
    assert m.INFERENCE_GENERATION_TIMEOUT_S == 1.5, m.INFERENCE_GENERATION_TIMEOUT_S

    await _assert_local_timeout_returns_504(m)
    await _assert_health_stays_fast_during_generation(m)
    await _assert_remote_init_runs_in_lifespan(m)
    await _assert_ready_reports_remote(m)

    print("inference.stability_selfcheck OK")


if __name__ == "__main__":
    # Silence a benign warning from `starlette.testclient` about the
    # (already-installed) httpx dep; it isn't relevant to our asserts.
    import warnings
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    try:
        asyncio.run(main())
    except AssertionError:
        raise
    except Exception as e:
        print(f"inference.stability_selfcheck FAILED: {type(e).__name__}: {e}",
              file=sys.stderr)
        raise
