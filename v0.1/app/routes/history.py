"""/api/history — one-paragraph AI narrative of the location's history.

Pipeline (v0.1 only — needs the local Geofabrik snapshot):
  1. Read OSM historic=* features within 500 m from Index.osm_local.
  2. Shape into the inference `history` template's context payload.
  3. POST to {INFERENCE_URL}/summarize with template=history.
  4. Return { "history": "<paragraph>", "features_count": N, "model": "..." }.

If the local snapshot is missing (Overpass-only deployment) the route responds
503 with a clear message — history is a snapshot-derived feature.

Feature-shape rules:
  - keep name + inscription + start_date + wikipedia link + distance_m
  - drop unnamed items with no inscription (noise)
  - sort by distance, cap at 5 (matches history template's shown limit)

Caching:
  llama-cpp generation dominates wall time (~35 s on CX22). Historic features
  are OSM-snapshot data, refreshed weekly by the systemd timer, so the same
  address returns identical output for at least seven days. Wrap the whole
  response dict in a TTLCache keyed on rounded (lat, lon) so repeat visits
  and neighbouring addresses hit the cache instead of the LLM.

  Env overrides (all optional):
    HISTORY_CACHE_TTL_S   default 604800  (7 days — matches OSM refresh cadence)
    HISTORY_CACHE_SIZE    default 1000    (~500 KB memory; LRU eviction beyond)
    HISTORY_CACHE_GRID    default 3       (decimal places on lat/lon; 3 = ~100 m cell)
"""
from __future__ import annotations

import os

import httpx
from cachetools import TTLCache
from fastapi import APIRouter, Depends, HTTPException

from app.cities.base import CityConfig
from app.config import INFERENCE_TIMEOUT_S, INFERENCE_URL
from app.deps import get_city, get_index

router = APIRouter()

_HISTORIC_RADIUS_M = 500
_MAX_FEATURES     = 5

_CACHE_TTL_S  = int(os.environ.get("HISTORY_CACHE_TTL_S", 7 * 24 * 3600))
_CACHE_SIZE   = int(os.environ.get("HISTORY_CACHE_SIZE",  1000))
_CACHE_GRID   = int(os.environ.get("HISTORY_CACHE_GRID",  3))

# Module-level cache — one per app process. TTLCache is thread-safe under
# the GIL for get/set. Concurrent requests for the same missing key may
# both generate; acceptable pending a real thundering-herd guard.
_history_cache: TTLCache = TTLCache(maxsize=_CACHE_SIZE, ttl=_CACHE_TTL_S)


def _cache_key(city_slug: str, lat: float, lon: float) -> tuple[str, float, float]:
    """Rounded lat/lon key so neighbouring addresses share an entry. City
    slug is included so a multi-city deployment does not cross-contaminate."""
    return (city_slug, round(lat, _CACHE_GRID), round(lon, _CACHE_GRID))


def _shape_historic(f: dict) -> dict | None:
    """Keep only the fields the inference prompt uses. Drop pure-noise rows
    (no name AND no inscription) — the model has nothing to say about them."""
    tags = f.get("tags") or {}
    name = (f.get("name") or "").strip()
    inscription = (tags.get("inscription") or "").strip().replace("|", ", ")
    if not name and not inscription:
        return None
    return {
        "distance_m":  f.get("distance_m"),
        "historic":    tags.get("historic"),
        "name":        name,
        "inscription": inscription[:200] if inscription else None,
        "start_date":  tags.get("start_date"),
        "wikipedia":   tags.get("wikipedia"),
    }


@router.get("/api/history")
async def history(
    lat: float, lon: float,
    street:   str = "?", hnr:      str = "?", plz: str = "?",
    bezirk:   str = "?", ortsteil: str = "?",
    cfg: CityConfig = Depends(get_city),
    index=Depends(get_index),
):
    osm = getattr(index, "osm_local", None)
    if osm is None:
        raise HTTPException(503,
            "Location history requires the local OSM snapshot (v0.1 only). "
            "Run scripts/refresh_osm_amenities.py to seed it.")

    key = _cache_key(cfg.slug, lat, lon)
    hit = _history_cache.get(key)
    if hit is not None:
        return {**hit, "cached": True}

    raw = osm.near("historic", lon, lat, _HISTORIC_RADIUS_M)
    features = [f for f in (_shape_historic(r) for r in raw) if f]
    features = features[:_MAX_FEATURES]     # already sorted by distance

    if not features:
        # Short-circuit — no need to hit the LLM if there's nothing to write about.
        empty = {"history": "No historic points on record within 500 m of this address.",
                 "features_count": 0, "model": "none"}
        _history_cache[key] = empty
        return {**empty, "cached": False}

    payload = {
        "template": "history",
        "city":     cfg.slug,
        "context":  {
            "street": street, "hnr": hnr, "plz": plz,
            "bezirk": bezirk, "ortsteil": ortsteil,
            "features": features,
        },
    }
    try:
        # Model generation dominates the wall time — bump the client timeout
        # generously so a slow first-token pull doesn't 504.
        timeout = max(60, INFERENCE_TIMEOUT_S)
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(f"{INFERENCE_URL}/summarize", json=payload)
    except httpx.RequestError as e:
        raise HTTPException(503, f"inference-service unreachable: {e}")

    if r.status_code >= 500:
        raise HTTPException(504, f"inference-service {r.status_code}: {r.text[:200]}")
    if r.status_code >= 400:
        raise HTTPException(r.status_code, f"inference-service: {r.text[:200]}")

    body = r.json()
    summary = body.get("summary") or {}
    result = {
        "history":        summary.get("history", ""),
        "features_count": len(features),
        "model":          body.get("model", "unknown"),
    }
    # Only cache non-empty narratives — an empty string is likely a transient
    # inference-side failure and should be retried on the next request.
    if result["history"]:
        _history_cache[key] = result
    return {**result, "cached": False}


if __name__ == "__main__":
    # Pure selfcheck — no I/O. Exercises the cache key + TTLCache behaviour.
    assert _cache_key("berlin", 52.48864, 13.39631) == ("berlin", 52.489, 13.396)
    assert _cache_key("berlin", 52.48862, 13.39664) == ("berlin", 52.489, 13.397), \
        "adjacent addresses across a 3rd-decimal boundary must map to distinct cells"
    assert _cache_key("hamburg", 52.48864, 13.39631) != _cache_key("berlin", 52.48864, 13.39631), \
        "cache key must be city-scoped so multi-city deployments do not collide"
    # Cache round-trip
    _tmp = TTLCache(maxsize=2, ttl=60)
    _tmp[("berlin", 52.489, 13.396)] = {"history": "x", "features_count": 1, "model": "m"}
    assert _tmp.get(("berlin", 52.489, 13.396))["history"] == "x"
    # LRU eviction at maxsize
    _tmp[("berlin", 52.500, 13.400)] = {"v": 2}
    _tmp[("berlin", 52.510, 13.410)] = {"v": 3}
    assert ("berlin", 52.489, 13.396) not in _tmp, "oldest entry must evict at maxsize"
    print("history.py cache selfcheck OK")
