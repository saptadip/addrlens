"""OGC API Features geocoder — Hamburg's api.hamburg.de DOG service.

Berlin uses classic WFS (Index.geocode → wfs()); Hamburg's DOG address
service is GML-only on WFS, so we route through the OGC API Features
endpoint which returns JSON directly. Same return shape as
Index.geocode so app.routes.lookup doesn't branch on city.

The ss ↔ ß fold retry mirrors Index.geocode's Berlin path (see
app/core/index.py:534) — expat users type 'Sybelstrasse', LGV stores
'Sybelstraße'."""
from __future__ import annotations

from typing import Optional

import httpx


def _ss_fold(street: str) -> Optional[str]:
    if "strasse" in street.lower():
        return street.replace("strasse", "straße").replace("Strasse", "Straße")
    if "straße" in street.lower():
        return street.replace("straße", "strasse").replace("Straße", "Strasse")
    return None


def geocode_oaf(cfg, street: str, hnr: str, plz: str) -> Optional[dict]:
    """Look up a Hamburg address via OGC API Features. Returns
    {"lon": float, "lat": float, "props": dict} on hit, None on miss."""
    fm = cfg.geocoder_oaf_field_map
    base_url = cfg.geocoder_oaf_url.rstrip("/")

    def _query(street_v: str):
        params = {
            fm["street"]: street_v,
            fm["hnr"]:    hnr,
            fm["plz"]:    plz,
            "limit":      1,
            "f":          "json",
        }
        r = httpx.get(base_url, params=params, timeout=10.0)
        r.raise_for_status()
        return (r.json() or {}).get("features") or []

    feats = _query(street)
    if not feats:
        alt = _ss_fold(street)
        if alt and alt != street:
            feats = _query(alt)
    if not feats:
        return None
    lon, lat = feats[0]["geometry"]["coordinates"]
    props = feats[0].get("properties") or {}
    # Hamburg's DOG OAF exposes `ortsteil` as a numeric code ("117") and the
    # human name lives in `postOrtsteil` ("Hammerbrook"). The frontend AI
    # panel reads `raw.ortsteil` for the summary chip; if it finds the raw
    # numeric code the chip renders "117" instead of the neighbourhood
    # name. Remap in place so `raw.ortsteil` is always human-readable when
    # OAF returns both. Same story for `bezirke` (plural, human) vs the
    # frontend-expected `bezirk` fallback — alias it when only the plural
    # form is present.
    if props.get("postOrtsteil"):
        props["ortsteil"] = props["postOrtsteil"]
    if props.get("bezirke") and not props.get("bezirk"):
        props["bezirk"] = props["bezirke"]
    return {"lon": lon, "lat": lat, "props": props}
