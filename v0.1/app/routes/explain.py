"""/api/explain — delegates to inference-service, then runs city glossary
post-processing.

Contract (plan §7.3):
  POST {INFERENCE_URL}/summarize
    { "template": "explain", "context": {"card_type": "...", "fields": {...}}, "city": "<slug>" }
  ->
    { "summary": { "explanation": "..." }, "model": "...", "trace_id": "..." }

Response to client mirrors phase3/server.py:_explain exactly:
  { "explanation": "...", "model": "..." }

Note: the inference service wraps the explain output in `summary.explanation`;
the app unwraps to preserve the phase3 client-side contract.
"""
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request

from app.cities.base import CityConfig
from app.config import INFERENCE_TIMEOUT_S, INFERENCE_URL
from app.core.gloss import gloss
from app.deps import get_city

router = APIRouter()


@router.post("/api/explain")
async def explain(request: Request, cfg: CityConfig = Depends(get_city)):
    try:
        d = await request.json()
    except Exception as e:
        raise HTTPException(400, f"bad body: {e}")

    card_type = (d.get("card_type") or "").strip()[:40]
    fields = d.get("fields") or {}
    if not card_type or not fields:
        raise HTTPException(400, "card_type and fields required")

    payload = {
        "template": "explain",
        "context": {"card_type": card_type, "fields": fields},
        "city": cfg.slug,
    }
    try:
        async with httpx.AsyncClient(timeout=INFERENCE_TIMEOUT_S) as client:
            r = await client.post(f"{INFERENCE_URL}/summarize", json=payload)
    except httpx.RequestError as e:
        raise HTTPException(503, f"inference-service unreachable: {e}")

    if r.status_code >= 500:
        raise HTTPException(504, f"inference-service {r.status_code}: {r.text[:200]}")
    if r.status_code >= 400:
        raise HTTPException(r.status_code, f"inference-service: {r.text[:200]}")

    body = r.json()
    summary = body.get("summary") or {}
    explanation = summary.get("explanation", "")
    return {"explanation": gloss(explanation, cfg.bilingual_glossary),
            "model": body.get("model", "unknown")}
