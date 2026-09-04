"""POST /api/lens_insight — per-lens executive-summary AI Insight.

Replaces the per-tile `Get Insight` dispatcher in `card_insight.py` for
lens-level summarisation. The frontend hits this ONCE per lens per
address (Newcomer pilot), gets back:

    {
      "lens_insight": {
        "executive_summary": "<2-3 sentences>",
        "sections":          [ {title, tiles, verdict, note}, ... ],
        "highlights_green":  [ {tile, one_line}, ... ],
        "highlights_red":    [ {tile, one_line}, ... ]
      },
      "model":  "<remote model id>",
      "cached": bool
    }

Body shape (from SPA):
  {
    "lens":    "newcomer",
    "address": { "lat": <float>, "lon": <float>,
                 "bezirk": "...", "ortsteil": "..." },
    "tiles":   [ { "key", "label", "tier", "rule", "numeric", "caveat" }, ... ]
  }

Design notes
------------
- Cache-key is `(lens, city, rounded_lat, rounded_lon)` — same ~100 m
  grid as history so neighbouring addresses share an entry. LLM cost per
  call is small (~$0.00003 on Cloudflare Workers AI) but latency (2-4 s
  p50) is user-visible, so the cache pays for itself.
- Frontend passes tiles it already has from `/api/lookup` — no re-
  computation on this hot path. Only the tier axis (`key`, `tier`,
  `rule`, `numeric`, `caveat`) travels; feature drill-down stays in the
  tile modals.
- Only `lens=newcomer` is wired today (pilot). Adding a lens =
  register a new `lens_<slug>_insight` template in
  `inference/main.py::TEMPLATES` and a row in `_LENS_TEMPLATES` here.
- All lens-level LLM traffic routes through Cloudflare Workers AI (see
  `inference/main.py::REMOTE_TEMPLATES` — `lens_newcomer_insight` is in
  the default allow-list). Local Qwen 1.5B cannot reliably produce the
  strict JSON schema this template requires; if the remote backend is
  down, the caller gets 502 and the SPA falls back to hiding the panel.
"""
from __future__ import annotations

import os

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request

from app.cities.base import CityConfig
from app.config import INFERENCE_TIMEOUT_S, INFERENCE_URL
from app.core.cache import HISTORY as _cache
from app.core.rate_limit import limiter
from app.deps import get_city

router = APIRouter()

# Per-lens inference template lookup. Grow as new lenses ship.
_LENS_TEMPLATES = {
    "newcomer": "lens_newcomer_insight",
}

# Same cache grid as history — ~100 m cells. Env-tunable.
_CACHE_GRID = int(os.environ.get("LENS_INSIGHT_CACHE_GRID", 3))

# Cache version — bump when LENS_SECTION_MAP or the template's system
# prompt changes materially. 7-day cached entries under an old version
# will simply miss and be regenerated, so stale summaries can't leak
# across a template edit.
_CACHE_VERSION = "v1"


def _cache_key(city_slug: str, lens: str, lat: float, lon: float) -> tuple:
    """`(namespace, version, city, lens, lat, lon)` — namespace prefix
    keeps this disjoint from the shared HISTORY cache's history keys;
    version bumps invalidate stale entries after a template edit."""
    return ("lens_insight", _CACHE_VERSION, city_slug, lens,
            round(lat, _CACHE_GRID), round(lon, _CACHE_GRID))


_ALLOWED_TIERS = {"green", "amber", "red", "unknown", "info"}


def _shape_tile_contexts(tiles: list) -> list:
    """Trim client-supplied tile payload to the schema the inference
    template consumes. Drops unknown fields; validates types minimally.
    A tile missing `key` is dropped — the summariser is keyed on
    `LENS_SECTION_MAP` which enumerates the tile keys. Unknown tier
    values (a malicious or malformed client sending `tier:"zeus"`)
    normalise to `"unknown"` so the deterministic rollup can't be
    poisoned into always-`unknown` by lying about tiers."""
    out = []
    for t in tiles or []:
        if not isinstance(t, dict):
            continue
        key = (t.get("key") or "").strip()
        if not key:
            continue
        tier = t.get("tier")
        if tier not in _ALLOWED_TIERS:
            tier = "unknown"
        out.append({
            "key":     key,
            "label":   t.get("label") or key,
            "tier":    tier,
            "rule":    t.get("rule"),
            "numeric": t.get("numeric"),
            "caveat":  t.get("caveat"),
        })
    return out


@router.post("/api/lens_insight")
@limiter.limit("10/minute")
async def lens_insight(
    request: Request,
    cfg: CityConfig = Depends(get_city),
):
    try:
        body = await request.json()
    except Exception as e:
        raise HTTPException(400, f"bad body: {e}")

    lens = (body.get("lens") or "").strip()
    if lens not in _LENS_TEMPLATES:
        raise HTTPException(400,
            f"unknown lens {lens!r}; expected one of {sorted(_LENS_TEMPLATES)}")

    address = body.get("address") or {}
    lat = address.get("lat")
    lon = address.get("lon")
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
        raise HTTPException(400, "address.lat and address.lon are required")

    tile_contexts = _shape_tile_contexts(body.get("tiles") or [])
    if not tile_contexts:
        raise HTTPException(400, "tiles array is required and non-empty")

    key = _cache_key(cfg.slug, lens, lat, lon)
    hit = _cache.get(key)
    if hit is not None:
        return {**hit, "cached": True}

    payload = {
        "template": _LENS_TEMPLATES[lens],
        "city":     cfg.slug,
        "context":  {
            "address_hint": {
                "bezirk":   address.get("bezirk", ""),
                "ortsteil": address.get("ortsteil", ""),
            },
            "tile_contexts": tile_contexts,
        },
    }
    try:
        # Cloudflare call dominates wall time (~2-4 s p50). Match the
        # inference-service `INFERENCE_GENERATION_TIMEOUT_S` default
        # (120 s) so a slow first-token pull the server is patiently
        # waiting on doesn't 504 at the app boundary before the
        # response can land.
        timeout = max(120, INFERENCE_TIMEOUT_S)
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(f"{INFERENCE_URL}/summarize", json=payload)
    except httpx.RequestError as e:
        raise HTTPException(503, f"inference-service unreachable: {e}")

    if r.status_code >= 500:
        raise HTTPException(504, f"inference-service {r.status_code}: {r.text[:200]}")
    if r.status_code >= 400:
        # 400 from inference = template contract violation OR schema
        # validation failure after two Cloudflare attempts. Surface the
        # detail so the SPA can degrade to hiding the panel.
        raise HTTPException(r.status_code, f"inference-service: {r.text[:200]}")

    body_json = r.json()
    summary = body_json.get("summary") or {}
    lens_obj = summary.get("lens_insight") or {}
    if not lens_obj.get("executive_summary"):
        raise HTTPException(502, "inference-service returned empty lens_insight")

    result = {
        "lens_insight": lens_obj,
        "model":        body_json.get("model", "unknown"),
    }
    _cache.set(key, result)
    return {**result, "cached": False}


if __name__ == "__main__":
    # -- Cache-key shape + namespace isolation -------------------------
    assert _cache_key("berlin", "newcomer", 52.48864, 13.39631) == \
        ("lens_insight", _CACHE_VERSION, "berlin", "newcomer", 52.489, 13.396)
    # Adjacent addresses across a 3rd-decimal boundary → distinct cells.
    assert _cache_key("berlin", "newcomer", 52.48862, 13.39664) == \
        ("lens_insight", _CACHE_VERSION, "berlin", "newcomer", 52.489, 13.397)
    # City-scoped: multi-city deployment mustn't cross-contaminate.
    assert _cache_key("hamburg", "newcomer", 52.489, 13.396) != \
        _cache_key("berlin", "newcomer", 52.489, 13.396)
    # Lens-scoped: same address on different lenses maps to distinct
    # cells (each lens has its own summariser output).
    assert _cache_key("berlin", "newcomer", 52.489, 13.396) != \
        _cache_key("berlin", "quiet_living", 52.489, 13.396)
    # Namespace prefix keeps this disjoint from history keys.
    assert _cache_key("berlin", "newcomer", 52.489, 13.396)[0] == "lens_insight"
    # Cache version threads through so a template edit invalidates entries.
    assert _cache_key("berlin", "newcomer", 52.489, 13.396)[1] == _CACHE_VERSION

    # -- Tier whitelist: unknown tier values normalise to "unknown" ---
    _tainted = _shape_tile_contexts([
        {"key": "buergeramt", "tier": "green"},
        {"key": "rail_transit", "tier": "zeus"},        # malicious
        {"key": "tram_transit", "tier": None},          # missing
        {"key": "bus_transit", "tier": "info"},         # allowed alias
    ])
    _tiers = {t["key"]: t["tier"] for t in _tainted}
    assert _tiers["buergeramt"]  == "green"
    assert _tiers["rail_transit"] == "unknown", f"malicious tier not normalised: {_tiers['rail_transit']!r}"
    assert _tiers["tram_transit"] == "unknown"
    assert _tiers["bus_transit"]  == "info"

    # -- _LENS_TEMPLATES sanity: only newcomer wired today ------------
    assert "newcomer" in _LENS_TEMPLATES
    assert _LENS_TEMPLATES["newcomer"] == "lens_newcomer_insight", \
        "template name must match the row in inference/main.py::TEMPLATES"

    # -- _shape_tile_contexts drops noise + keeps schema fields -------
    _tiles = [
        {"key": "buergeramt", "label": "Bürgeramt reach",
         "tier": "green", "rule": "≥1 within 15 min", "numeric": "14 min",
         "caveat": None, "features": [{"a": 1}], "extras": "should be dropped"},
        {"tier": "green"},                  # missing key → drop
        "not-a-dict",                       # not an object → drop
        {"key": "", "tier": "green"},       # empty key → drop
    ]
    _shaped = _shape_tile_contexts(_tiles)
    assert len(_shaped) == 1, f"expected 1 shaped tile, got {len(_shaped)}"
    assert set(_shaped[0].keys()) == {"key", "label", "tier", "rule", "numeric", "caveat"}
    assert "features" not in _shaped[0], "features must be dropped from tile_context"
    assert "extras" not in _shaped[0]

    print("lens_insight.py selfcheck OK")
