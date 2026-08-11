"""/api/impression — delegates to inference-service, then runs city glossary
post-processing.

Contract (plan §7.3):
  POST {INFERENCE_URL}/summarize
    { "template": "impression", "context": {...}, "city": "<slug>" }
  ->
    { "summary": { <tab>: <text> }, "model": "...", "trace_id": "..." }

Response to client mirrors phase3/server.py:_impression exactly:
  { "summary": { <tab>: <text> }, "model": "..." }
"""
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request

from app.cities.base import CityConfig
from app.config import INFERENCE_TIMEOUT_S, INFERENCE_URL
from app.core.gloss import gloss
from app.deps import get_city

router = APIRouter()


@router.post("/api/impression")
async def impression(request: Request, cfg: CityConfig = Depends(get_city)):
    try:
        d = await request.json()
    except Exception as e:
        raise HTTPException(400, f"bad body: {e}")

    addr = (d.get("address") or "this address").strip()[:120]
    votes = d.get("votes") or {}

    payload = {
        "template": "impression",
        "context": {"address": addr, "votes": votes},
        "city": cfg.slug,
    }
    try:
        async with httpx.AsyncClient(timeout=INFERENCE_TIMEOUT_S) as client:
            r = await client.post(f"{INFERENCE_URL}/summarize", json=payload)
    except httpx.RequestError as e:
        # Inference unreachable — plan §7.6 says surface 503, never block the map.
        raise HTTPException(503, f"inference-service unreachable: {e}")

    if r.status_code >= 500:
        raise HTTPException(504, f"inference-service {r.status_code}: {r.text[:200]}")
    if r.status_code >= 400:
        raise HTTPException(r.status_code, f"inference-service: {r.text[:200]}")

    body = r.json()
    summary = body.get("summary") or {}
    # Apply city glossary post-processing (plan §7.6). Small models leave
    # German admin terms untranslated; gloss() is the safety net.
    summary = {tab: gloss(text, cfg.bilingual_glossary) if isinstance(text, str) else text
               for tab, text in summary.items()}
    return {"summary": summary, "model": body.get("model", "unknown")}
