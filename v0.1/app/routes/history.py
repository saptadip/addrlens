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
"""
from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException

from app.cities.base import CityConfig
from app.config import INFERENCE_TIMEOUT_S, INFERENCE_URL
from app.deps import get_city, get_index

router = APIRouter()

_HISTORIC_RADIUS_M = 500
_MAX_FEATURES     = 5


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
    raw = osm.near("historic", lon, lat, _HISTORIC_RADIUS_M)
    features = [f for f in (_shape_historic(r) for r in raw) if f]
    features = features[:_MAX_FEATURES]     # already sorted by distance

    if not features:
        # Short-circuit — no need to hit the LLM if there's nothing to write about.
        return {"history": "No historic points on record within 500 m of this address.",
                "features_count": 0, "model": "none"}

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
    return {
        "history":        summary.get("history", ""),
        "features_count": len(features),
        "model":          body.get("model", "unknown"),
    }
