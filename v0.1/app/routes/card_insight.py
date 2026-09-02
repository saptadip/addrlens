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
from app.core.rate_limit import limiter
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
    # Fall back the `lens` field from the tile key when the caller
    # didn't set it explicitly: `gesix_newcomer` → newcomer,
    # `gesix_quiet` → quiet_living, everything else → young_family.
    card = (payload.get("card") or "").strip()
    default_lens = {
        "gesix_newcomer": "newcomer",
        "gesix_quiet":    "quiet_living",
        "gesix_commuter": "commuter",
    }.get(card, "young_family")
    return {
        "plr_name":   g.get("plr_name"),
        "quintile_5": g.get("quintile_5"),
        "rang":       g.get("rang"),
        "total":      g.get("total"),
        "lens":       payload.get("lens", default_lens),
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


# -- Quiet Living lens context builders ------------------------------------
# These tiles' AI-insight prompts pull structured facts from tile.metadata
# rather than tile.features. The composer at
# `app/core/lenses/quiet_living.py` populates the metadata payloads to
# match — keep the two files in sync when adding fields.


def _ctx_quiet_zone(payload: dict) -> dict:
    """Reuses the standard tier+features shape — the composer plots the
    nearest quiet-zone anchor as a single feature."""
    return _ctx_features(payload)


def _ctx_street_trees(payload: dict) -> dict:
    """Aggregate reading: count / crown % / age / species."""
    t = _tile(payload)
    md = t.get("metadata") or {}
    trees = md.get("trees") or {}
    return {
        "tier":               t.get("tier"),
        "rule":               t.get("rule"),
        "numeric":            t.get("numeric"),
        "count":              trees.get("count"),
        "crown_coverage_pct": trees.get("crown_coverage_pct"),
        "avg_age_yr":         trees.get("avg_age_yr"),
        "tallest_m":          trees.get("tallest_m"),
        "top_species":        trees.get("top_species") or [],
    }


def _ctx_tempo30(payload: dict) -> dict:
    """Aggregate reading: nearest speed exception with distance + reason."""
    t = _tile(payload)
    md = t.get("metadata") or {}
    tempo = md.get("tempolimit") or {}
    return {
        "tier":              t.get("tier"),
        "rule":              t.get("rule"),
        "numeric":           t.get("numeric"),
        "speed_kmh":         tempo.get("speed_kmh"),
        "distance_m":        tempo.get("distance_m"),
        "reason":            tempo.get("reason"),
        "time_restriction": tempo.get("time_restriction"),
    }


def _ctx_arterial_road(payload: dict) -> dict:
    """Single-anchor readout: nearest arterial's name / class / distance."""
    t = _tile(payload)
    md = t.get("metadata") or {}
    arterial = md.get("arterial") or {}
    return {
        "tier":       t.get("tier"),
        "rule":       t.get("rule"),
        "numeric":    t.get("numeric"),
        "name":       arterial.get("name"),
        "class":      arterial.get("class"),
        "distance_m": arterial.get("distance_m"),
    }


def _ctx_rail_noise(payload: dict) -> dict:
    """Single-anchor readout: mode / name / distance."""
    t = _tile(payload)
    md = t.get("metadata") or {}
    rail = md.get("rail") or {}
    return {
        "tier":       t.get("tier"),
        "rule":       t.get("rule"),
        "numeric":    t.get("numeric"),
        "mode":       rail.get("mode"),
        "name":       rail.get("name"),
        "distance_m": rail.get("distance_m"),
    }


def _ctx_nightlife_inverted(payload: dict) -> dict:
    """Standard tier+features shape — composer populates the feature list
    from the OSM `nightlife` bucket."""
    return _ctx_features(payload)


# -- Commuter lens context builders ----------------------------------------

def _ctx_airport(payload: dict) -> dict:
    """Aggregate reading: single-point airport distance from tile.metadata.
    Bounces the airport object straight into the template context so the
    prompt can reference `distance_m` and (if present) `name`."""
    t = _tile(payload)
    md = t.get("metadata") or {}
    airport = md.get("airport") or {}
    return {
        "tier":    t.get("tier"),
        "rule":    t.get("rule"),
        "numeric": t.get("numeric"),
        "airport": airport,
    }


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
    "rail_transit":    _ctx_features,
    "tram_transit":    _ctx_features,
    "bus_transit":     _ctx_features,
    "intl_food":        _ctx_features,
    "coworking":        _ctx_features,
    "english_clinic":   _ctx_features,
    "language_school":  _ctx_features,
    "library":          _ctx_features,
    "packstation":      _ctx_features,
    "wochenmarkt":      _ctx_features,
    "gesix_newcomer":   _ctx_gesix,
    # Quiet Living lens cards
    "quiet_zone":         _ctx_quiet_zone,
    "street_trees":       _ctx_street_trees,
    "tempo30":            _ctx_tempo30,
    "arterial_road":      _ctx_arterial_road,
    "rail_noise":         _ctx_rail_noise,
    "nightlife_inverted": _ctx_nightlife_inverted,
    "gesix_quiet":        _ctx_gesix,
    # Commuter lens cards
    "commuter_rail_transit": _ctx_features,
    "commuter_tram_transit": _ctx_features,
    "commuter_bus_transit":  _ctx_features,
    "regional_rail_reach":   _ctx_features,
    "cycling_network":       _ctx_features,
    "car_sharing_reach":     _ctx_features,
    "ev_charging_reach":     _ctx_features,
    "airport_reach":         _ctx_airport,
    "gesix_commuter":        _ctx_gesix,
}


@router.post("/api/card_insight")
@limiter.limit("30/minute")
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
    # Verify all newcomer-lens card keys are registered (6 original + 4 additions)
    expected_new_keys = {"buergeramt",
                         "rail_transit", "tram_transit", "bus_transit",
                         "intl_food", "coworking", "english_clinic",
                         "language_school", "library", "packstation", "wochenmarkt",
                         "gesix_newcomer"}
    actual_keys = set(_CARD_CONTEXT_BUILDERS.keys())
    for key in expected_new_keys:
        assert key in actual_keys, f"missing card key {key!r}"

    # Verify context builders are assigned correctly
    assert _CARD_CONTEXT_BUILDERS["buergeramt"] is _ctx_features
    assert _CARD_CONTEXT_BUILDERS["rail_transit"] is _ctx_features
    assert _CARD_CONTEXT_BUILDERS["tram_transit"] is _ctx_features
    assert _CARD_CONTEXT_BUILDERS["bus_transit"]  is _ctx_features
    assert _CARD_CONTEXT_BUILDERS["intl_food"] is _ctx_features
    assert _CARD_CONTEXT_BUILDERS["coworking"] is _ctx_features
    assert _CARD_CONTEXT_BUILDERS["english_clinic"] is _ctx_features
    assert _CARD_CONTEXT_BUILDERS["language_school"] is _ctx_features
    assert _CARD_CONTEXT_BUILDERS["library"] is _ctx_features
    assert _CARD_CONTEXT_BUILDERS["packstation"] is _ctx_features
    assert _CARD_CONTEXT_BUILDERS["wochenmarkt"] is _ctx_features
    assert _CARD_CONTEXT_BUILDERS["gesix_newcomer"] is _ctx_gesix

    # -- Lens-tile-keys iteration guard (prevention for the class of gap
    # -- the reviewer flagged in PR #9): every LensTileConfig.key across
    # -- every lens on the Berlin CityConfig must have a matching entry
    # -- in _CARD_CONTEXT_BUILDERS. This is what would have caught the
    # -- Quiet Living gap at selfcheck time.
    # --
    # -- Frontend sibling: `web/static/app.js::_INSIGHT_VINTAGE` also
    # -- lists every non-numeric-only tile key. When adding a new tile,
    # -- update BOTH this dict AND the frontend map — the "Get Insight"
    # -- button is gated on the frontend map, so a missing frontend row
    # -- silently hides the button even with the backend row present.
    from app.cities.berlin import BERLIN as _BERLIN
    _lenses = (_BERLIN.young_family_lens,
               _BERLIN.newcomer_lens,
               _BERLIN.quiet_living_lens,
               _BERLIN.commuter_lens)
    # Numeric-only tiles (tier=unknown by design) have no insight
    # paragraph — the frontend hides the Get-insight button on them.
    # They're allowed to sit outside `_CARD_CONTEXT_BUILDERS`.
    _INSIGHTLESS_KEYS = {"nightlife_density"}
    _missing = []
    for _lens in _lenses:
        for _tile_cfg in _lens.tiles:
            if _tile_cfg.key in _INSIGHTLESS_KEYS:
                continue
            if _tile_cfg.key not in _CARD_CONTEXT_BUILDERS:
                _missing.append(f"{_lens.slug}::{_tile_cfg.key}")
    assert not _missing, (
        "Every non-numeric-only LensTileConfig.key must have a "
        "_CARD_CONTEXT_BUILDERS row. Missing: " + str(_missing)
    )

    # Quiet Living cards registered explicitly.
    for _k in ("quiet_zone", "street_trees", "tempo30", "arterial_road",
               "rail_noise", "nightlife_inverted", "gesix_quiet"):
        assert _k in _CARD_CONTEXT_BUILDERS, _k
    assert _CARD_CONTEXT_BUILDERS["gesix_quiet"] is _ctx_gesix

    # Commuter cards registered explicitly.
    for _k in ("commuter_rail_transit", "commuter_tram_transit",
               "commuter_bus_transit",  "regional_rail_reach",
               "cycling_network",       "car_sharing_reach",
               "ev_charging_reach",     "airport_reach",
               "gesix_commuter"):
        assert _k in _CARD_CONTEXT_BUILDERS, _k
    assert _CARD_CONTEXT_BUILDERS["airport_reach"] is _ctx_airport
    assert _CARD_CONTEXT_BUILDERS["gesix_commuter"] is _ctx_gesix

    # `_ctx_gesix` picks the right default lens from the card key.
    for _card, _expected_lens in (("gesix",          "young_family"),
                                   ("gesix_newcomer", "newcomer"),
                                   ("gesix_quiet",    "quiet_living"),
                                   ("gesix_commuter", "commuter")):
        _ctx = _ctx_gesix({"card": _card,
                            "tile": {"metadata": {"gesix": {"quintile_5": 2}}}})
        assert _ctx["lens"] == _expected_lens, (_card, _ctx["lens"])

    print("selfcheck ok: all lens tile keys registered in _CARD_CONTEXT_BUILDERS")
