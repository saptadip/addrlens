"""/api/gesix_insight — plain-English gloss of the Senate GESIx composite index.

Pipeline (v0.1):
  1. Read GESIx metadata for the address's Planungsraum from index.gesix_at.
  2. POST inference/summarize with template=insight, lens-aware context.
  3. Return { "insight": "<paragraph>", "plr_name": "...", "quintile": N,
              "rank": N, "total": N, "model": "..." }.

Fails soft: address outside any GESIx polygon → 200 with a plain
'not available' message so the frontend can render a benign state.
"""
from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException

from app.cities.base import CityConfig
from app.config import INFERENCE_TIMEOUT_S, INFERENCE_URL
from app.deps import get_city, get_index

router = APIRouter()


@router.get("/api/gesix_insight")
async def insight(
    lat: float, lon: float, lens: str = "young_family",
    cfg: CityConfig = Depends(get_city),
    index=Depends(get_index),
):
    if not hasattr(index, "gesix_at"):
        raise HTTPException(503, "GESIx unavailable — Index has no gesix_at method.")
    g = index.gesix_at(lon, lat)
    if not g:
        return {
            "insight": "No neighbourhood profile available for this address "
                       "(outside the Senate's GESIx polygons).",
            "plr_name": None, "quintile": None, "rank": None, "total": None,
            "model": "none",
        }

    payload = {
        "template": "gesix_insight",
        "city":     cfg.slug,
        "context":  {
            "plr_name":   g.get("plr_name"),
            "quintile_5": g.get("quintile_5"),
            "rang":       g.get("rang"),
            "total":      g.get("total"),
            "lens":       lens if lens in ("young_family", "bureaucracy") else "young_family",
        },
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
        "insight":  summary.get("insight", ""),
        "plr_name": g.get("plr_name"),
        "quintile": g.get("quintile_5"),
        "rank":     g.get("rang"),
        "total":    g.get("total"),
        "model":    body.get("model", "unknown"),
    }
