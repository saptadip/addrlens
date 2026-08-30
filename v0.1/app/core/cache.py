"""Bounded in-memory caches — `TTLCache`-backed, thread-safe wrappers.

Consolidates six caches that used to live scattered across the codebase:

- `wfs._bod_cache`, `_noise_cache`, `_air_cache`, `_heat_cache` — were
  unbounded `dict`s protected by a per-cache `threading.Lock`. In a
  long-running FastAPI process every unique address geocoded ate a
  cache slot forever → slow memory leak.
- `amenities._amen_cache` — same shape, same leak.
- `history._history_cache` — was already `TTLCache`, but its config
  and instance lived under `routes/history.py` for historical
  reasons. Migrated for uniformity, kept with its distinct TTL.

Two `NamedCache` instances are exported:

- `HOT_PATH` — WFS bbox lookups + OSM/BOD amenity buckets. Short TTL
  because layers refresh (noise, air, heat all publish updates when
  the Senate re-runs their models) and one hour is more than enough
  to collapse a burst of same-address requests. Env-tunable:
  `APP_CACHE_SIZE` (default 4096), `APP_CACHE_TTL_S` (default 3600).
- `HISTORY` — LLM-generated Stolperstein prose. Long TTL because the
  underlying BOD layer changes at most a few times per year, and each
  generation costs real inference budget. Env-tunable:
  `HISTORY_CACHE_SIZE` (default 1000), `HISTORY_CACHE_TTL_S` (default
  7 × 24 × 3600 s = one week).

Kept separate so a memory spike on the fast cache doesn't evict
expensive summaries and vice versa.

Both wrap `cachetools.TTLCache` with an explicit `threading.Lock`
because `TTLCache` mutates its expiry queue on every `get()` — the GIL
alone is insufficient.

Callers namespace their keys by prefixing the tuple with a short string
(`"bod"`, `"noise"`, `"air"`, `"heat"`, `"amenities"`), so a shared
instance can serve multiple datasets without collision. See each
caller's implementation for the exact key shape.
"""
from __future__ import annotations

import os
import threading
from typing import Any, Callable

from cachetools import TTLCache


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw in (None, ""):
        return default
    try:
        return max(1, int(raw))
    except ValueError:
        return default


class NamedCache:
    """Thread-safe TTLCache wrapper.

    The wrapper itself is thin — one lock, a handful of methods. The
    value here is that every bounded cache in the app is now
    discoverable in one file and shares the same shape.
    """

    def __init__(self, size: int, ttl_s: int):
        self._cache: TTLCache = TTLCache(maxsize=size, ttl=ttl_s)
        self._lock = threading.Lock()

    def get(self, key: tuple) -> Any:
        """Return the cached value or None on miss / expiry."""
        with self._lock:
            return self._cache.get(key)

    def set(self, key: tuple, value: Any) -> None:
        with self._lock:
            self._cache[key] = value

    def get_or_load(self, key: tuple, loader: Callable[[], Any]) -> Any:
        """Cached load. Loader runs OUTSIDE the lock — a slow WFS call
        must not block other cache readers. Concurrent misses may both
        run the loader; that matches the pre-refactor behaviour of
        every caller (no thundering-herd guard was ever in place)."""
        hit = self.get(key)
        if hit is not None:
            return hit
        value = loader()
        self.set(key, value)
        return value

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._cache)

    def stats(self) -> dict:
        with self._lock:
            return {"size":    len(self._cache),
                    "maxsize": self._cache.maxsize,
                    "ttl_s":   self._cache.ttl}


# -- Instances ---------------------------------------------------------

HOT_PATH = NamedCache(
    size  = _env_int("APP_CACHE_SIZE",  4096),
    ttl_s = _env_int("APP_CACHE_TTL_S", 3600),
)

HISTORY = NamedCache(
    size  = _env_int("HISTORY_CACHE_SIZE",  1000),
    ttl_s = _env_int("HISTORY_CACHE_TTL_S", 7 * 24 * 3600),
)


if __name__ == "__main__":
    import time as _time

    # -- basic get/set + None-on-miss ------------------------------------
    c = NamedCache(size=10, ttl_s=3600)
    assert c.get(("nope",)) is None
    c.set(("a", 1), "value-a")
    assert c.get(("a", 1)) == "value-a"

    # -- namespace isolation via tuple prefix ---------------------------
    c.set(("bod",   "k"), [1, 2, 3])
    c.set(("noise", "k"), {"tier": "green"})
    assert c.get(("bod",   "k")) == [1, 2, 3]
    assert c.get(("noise", "k")) == {"tier": "green"}

    # -- get_or_load: loader fires exactly once on miss -----------------
    c.clear()
    calls = []
    def _loader():
        calls.append(1)
        return {"loaded": True}
    v1 = c.get_or_load(("k1",), _loader)
    v2 = c.get_or_load(("k1",), _loader)
    assert v1 == v2 == {"loaded": True}
    assert len(calls) == 1, calls

    # -- bounded size: overflow evicts (LRU) ----------------------------
    small = NamedCache(size=2, ttl_s=3600)
    small.set(("a",), 1)
    small.set(("b",), 2)
    small.set(("c",), 3)      # evicts "a"
    assert small.get(("a",)) is None
    assert small.get(("b",)) == 2
    assert small.get(("c",)) == 3
    assert len(small) == 2

    # -- TTL: entries expire ---------------------------------------------
    short = NamedCache(size=10, ttl_s=1)   # 1 s is the floor for `_env_int`
    # Manually shrink for the selfcheck — bypass the env floor.
    short._cache = TTLCache(maxsize=10, ttl=0.05)
    short.set(("x",), 42)
    assert short.get(("x",)) == 42
    _time.sleep(0.1)
    assert short.get(("x",)) is None

    # -- stats() reports shape ------------------------------------------
    st = c.stats()
    assert {"size", "maxsize", "ttl_s"} <= set(st.keys()), st

    # -- module-level instances exist with sensible defaults ------------
    assert isinstance(HOT_PATH, NamedCache)
    assert isinstance(HISTORY, NamedCache)
    assert HOT_PATH.stats()["maxsize"] >= 1
    assert HISTORY.stats()["ttl_s"]    >  HOT_PATH.stats()["ttl_s"]

    # -- env parsing: garbage / empty / negative fall through -----------
    os.environ["APP_CACHE_SIZE"] = "abc"
    assert _env_int("APP_CACHE_SIZE", 99) == 99
    os.environ["APP_CACHE_SIZE"] = ""
    assert _env_int("APP_CACHE_SIZE", 99) == 99
    os.environ["APP_CACHE_SIZE"] = "-5"
    assert _env_int("APP_CACHE_SIZE", 99) == 1    # clamped to positive floor
    del os.environ["APP_CACHE_SIZE"]

    print("cache.py selfcheck OK")
