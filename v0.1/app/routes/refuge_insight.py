"""/api/refuge_insight — plain-English gloss of the Young Family 'Quiet /
green refuge nearby' tile for one address.

Same shape as /api/gesix_insight. Pulls two signals from Index:
  - nearest Berlin 'Ruhige Gebiete' quiet zone (name, distance, size)
  - street-tree canopy summary (count, crown-coverage %, top species)
POSTs to inference `/summarize` with template=refuge_insight. Returns
{ insight, quiet, trees, model }.

Naming convention shared with gesix_insight: one route per card, one
template per card, route path == template name == card_key + '_insight'.
"""
from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException

from app.cities.base import CityConfig
from app.config import INFERENCE_TIMEOUT_S, INFERENCE_URL
from app.deps import get_city, get_index

router = APIRouter()


def _shape_quiet(q):
    """Pass through the fields the LLM actually reads. None → None."""
    if not q or q.get("distance_m") is None:
        return None
    return {
        "name":       (q.get("name") or "").strip() or None,
        "distance_m": q.get("distance_m"),
        "size_ha":    q.get("size_ha"),
    }


def _shape_trees(t):
    """Trim to the fields the LLM references + cap species list at 3."""
    if not t or t.get("error"):
        return None
    return {
        "count":              t.get("count"),
        "crown_coverage_pct": t.get("crown_coverage_pct"),
        "avg_age_yr":         t.get("avg_age_yr"),
        "tallest_m":          t.get("tallest_m"),
        "top_species":        (t.get("top_species") or [])[:3],
    }


@router.get("/api/refuge_insight")
async def refuge_insight(
    lat: float, lon: float,
    cfg: CityConfig = Depends(get_city),
    index=Depends(get_index),
):
    # Reuse the same Index helpers the /api/lookup composer uses.
    quiet_raw = index.nearest_quiet_zone(lon, lat) if hasattr(index, "nearest_quiet_zone") else None
    trees_raw = index.trees_bbox(lon, lat) if hasattr(index, "trees_bbox") else None

    quiet = _shape_quiet(quiet_raw)
    trees = _shape_trees(trees_raw)
    tier  = "green" if (quiet and quiet["distance_m"] < 400) or \
                       (trees and (trees.get("crown_coverage_pct") or 0) >= 25) else \
            ("amber" if (quiet and quiet["distance_m"] < 1000) or \
                       (trees and (trees.get("crown_coverage_pct") or 0) >= 15) else "red")

    payload = {
        "template": "refuge_insight",
        "city":     cfg.slug,
        "context":  {"quiet": quiet, "trees": trees, "tier": tier},
    }
    try:
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
        "insight": summary.get("insight", ""),
        "quiet":   quiet,
        "trees":   trees,
        "model":   body.get("model", "unknown"),
    }
