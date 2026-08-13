"""POST /api/card_insight — one endpoint for every Young Family card's
AI paragraph. Replaces the per-card GET routes (gesix / refuge / noise
insight) with a single dispatcher.

Body shape:
  { "card":  "<card_key>",                          # kita, playground, gesix, …
    "tile":  { tier, rule, numeric, features?, metadata? } }

The frontend passes the tile object it already has in eduData; the
route reshapes minimal context per card and calls inference with
template = <card_key>_insight. No re-fetch of amenities / WFS data on
the hot path.

Adding a new card = one row in _CARD_CONTEXT_BUILDERS below (plus a
matching template file registered in inference/main.py).
"""
from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException, Request

from app.cities.base import CityConfig
from app.config import INFERENCE_TIMEOUT_S, INFERENCE_URL
from app.deps import get_city
from fastapi import Depends

router = APIRouter()


def _tile(payload: dict) -> dict:
    return payload.get("tile") or {}


def _ctx_features(payload: dict) -> dict:
    """Common shape for feature-list-driven cards (kita, playground,
    pediatrician, transit, supermarket)."""
    t = _tile(payload)
    return {
        "tier":     t.get("tier"),
        "rule":     t.get("rule"),
        "numeric":  t.get("numeric"),
        "features": t.get("features") or [],
    }


def _ctx_gesix(payload: dict) -> dict:
    t = _tile(payload)
    g = (t.get("metadata") or {}).get("gesix") or {}
    return {
        "plr_name":   g.get("plr_name"),
        "quintile_5": g.get("quintile_5"),
        "rang":       g.get("rang"),
        "total":      g.get("total"),
        "lens":       payload.get("lens", "young_family"),
    }


def _ctx_refuge(payload: dict) -> dict:
    t = _tile(payload)
    quiet = (t.get("features") or [None])[0] if t.get("features") else None
    trees = (t.get("metadata") or {}).get("trees") or {}
    return {"quiet": quiet, "trees": trees, "tier": t.get("tier")}


def _ctx_noise(payload: dict) -> dict:
    md = (_tile(payload).get("metadata") or {})
    return {"l_den":   md.get("l_den") or {},
            "l_night": md.get("l_night") or {},
            "tier":    _tile(payload).get("tier")}


def _ctx_heat(payload: dict) -> dict:
    md = (_tile(payload).get("metadata") or {})
    return {"class":   md.get("day_class") or _tile(payload).get("numeric"),
            "tier":    _tile(payload).get("tier"),
            "rule":    _tile(payload).get("rule"),
            "numeric": _tile(payload).get("numeric")}


def _ctx_air(payload: dict) -> dict:
    md = (_tile(payload).get("metadata") or {})
    return {"ugm3":    md.get("no2_ugm3"),
            "tier":    _tile(payload).get("tier"),
            "rule":    _tile(payload).get("rule"),
            "numeric": _tile(payload).get("numeric")}


# Card → context builder. Adding a new card: append one row.
_CARD_CONTEXT_BUILDERS = {
    "kita":         _ctx_features,
    "playground":   _ctx_features,
    "pediatrician": _ctx_features,
    "transit":      _ctx_features,
    "supermarket":  _ctx_features,
    "gesix":        _ctx_gesix,
    "refuge":       _ctx_refuge,
    "noise":        _ctx_noise,
    "heat":         _ctx_heat,
    "air":          _ctx_air,
    # Newcomer lens cards (Task 7)
    "buergeramt":       _ctx_features,
    "transit_newcomer": _ctx_features,
    "intl_food":        _ctx_features,
    "coworking":        _ctx_features,
    "english_clinic":   _ctx_features,
    "gesix_newcomer":   _ctx_gesix,
}


@router.post("/api/card_insight")
async def card_insight(request: Request, cfg: CityConfig = Depends(get_city)):
    try:
        payload = await request.json()
    except Exception as e:
        raise HTTPException(400, f"bad body: {e}")

    card = (payload.get("card") or "").strip()
    build_ctx = _CARD_CONTEXT_BUILDERS.get(card)
    if build_ctx is None:
        raise HTTPException(400, f"unknown card {card!r}; expected one of "
                                  f"{sorted(_CARD_CONTEXT_BUILDERS)}")

    body = {"template": f"{card}_insight", "city": cfg.slug,
            "context":  build_ctx(payload)}
    try:
        async with httpx.AsyncClient(timeout=max(60, INFERENCE_TIMEOUT_S)) as c:
            r = await c.post(f"{INFERENCE_URL}/summarize", json=body)
    except httpx.RequestError as e:
        raise HTTPException(503, f"inference-service unreachable: {e}")
    if r.status_code >= 500:
        raise HTTPException(504, f"inference-service {r.status_code}: {r.text[:200]}")
    if r.status_code >= 400:
        raise HTTPException(r.status_code, f"inference-service: {r.text[:200]}")

    resp = r.json()
    summary = resp.get("summary") or {}
    return {"insight": summary.get("insight", ""),
            "card":    card,
            "model":   resp.get("model", "unknown")}


if __name__ == "__main__":
    # Verify all six newcomer-lens card keys are registered
    expected_new_keys = {"buergeramt", "transit_newcomer", "intl_food",
                         "coworking", "english_clinic", "gesix_newcomer"}
    actual_keys = set(_CARD_CONTEXT_BUILDERS.keys())
    for key in expected_new_keys:
        assert key in actual_keys, f"missing card key {key!r}"

    # Verify context builders are assigned correctly
    assert _CARD_CONTEXT_BUILDERS["buergeramt"] is _ctx_features
    assert _CARD_CONTEXT_BUILDERS["transit_newcomer"] is _ctx_features
    assert _CARD_CONTEXT_BUILDERS["intl_food"] is _ctx_features
    assert _CARD_CONTEXT_BUILDERS["coworking"] is _ctx_features
    assert _CARD_CONTEXT_BUILDERS["english_clinic"] is _ctx_features
    assert _CARD_CONTEXT_BUILDERS["gesix_newcomer"] is _ctx_gesix

    print("selfcheck ok: all 6 newcomer-lens cards registered in _CARD_CONTEXT_BUILDERS")
