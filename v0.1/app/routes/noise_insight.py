"""/api/noise_insight — plain-English gloss of the Façade noise tile.

Reads Berlin's façade-noise WFS via noise_at() (same helper used by
/api/noise and by the /api/lookup composer), passes the L_DEN + L_night
breakdown to inference template=noise_insight, returns { insight,
l_den_total, tier, model }.

Naming convention shared with gesix_insight + refuge_insight: one
route + template per card; path == template name == card_key + '_insight'.
"""
from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException

from app.cities.base import CityConfig
from app.config import INFERENCE_TIMEOUT_S, INFERENCE_URL
from app.core.scorer import noise_tier
from app.core.wfs import noise_at
from app.deps import get_city

router = APIRouter()


@router.get("/api/noise_insight")
async def noise_insight(
    lat: float, lon: float,
    cfg: CityConfig = Depends(get_city),
):
    try:
        n = noise_at(cfg, lon, lat)
    except Exception:
        n = {"unavailable": True}
    if not n or n.get("unavailable"):
        return {"insight": "No façade-noise reading available for this address.",
                "l_den_total": None, "tier": "unknown", "model": "none"}

    l_den   = n.get("l_den") or {}
    l_night = n.get("l_night") or {}
    tier    = noise_tier(l_den.get("total"))

    payload = {
        "template": "noise_insight",
        "city":     cfg.slug,
        "context":  {"l_den": l_den, "l_night": l_night, "tier": tier},
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
        "insight":     summary.get("insight", ""),
        "l_den_total": l_den.get("total"),
        "tier":        tier,
        "model":       body.get("model", "unknown"),
    }
