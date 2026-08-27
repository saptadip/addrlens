"""/api/suggest — address autocomplete for the search input.

The endpoint is a pure in-memory prefix lookup against the AddressIndex
that Index built at boot. No external calls, no LLM, no OSM fetch on the
hot path — a match costs a few microseconds. Rate-limit is generous
(5 req/second per IP) since typing debounced at ~130 ms produces roughly
one request per 200 ms per active user.

Response shape (small on purpose so autocomplete doesn't ship data the
caller will not use):

    { "hits": [ {"label", "street", "hnr", "plz", "lat", "lon"}, ... ] }

When the address index is not loaded (missing snapshot on disk), the
endpoint responds with an empty list — the caller's dropdown just stays
empty. The app itself keeps functioning.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from app.core.rate_limit import limiter
from app.deps import get_index

router = APIRouter()

_MIN_QUERY_LEN = 2
_MAX_LIMIT     = 10


@router.get("/api/suggest")
@limiter.limit("5/second")
def suggest(
    request: Request,
    q: str = Query("", description="Partial address, at least 2 characters."),
    limit: int = Query(8, ge=1, le=_MAX_LIMIT),
    index=Depends(get_index),
):
    idx = getattr(index, "address_index", None)
    if idx is None or len(q) < _MIN_QUERY_LEN:
        return {"hits": []}
    hits = idx.search(q, limit=limit)
    return {"hits": [
        {"label":  h.label,
         "street": h.street,
         "hnr":    h.hnr,
         "plz":    h.plz,
         "lat":    h.lat,
         "lon":    h.lon}
        for h in hits
    ]}
