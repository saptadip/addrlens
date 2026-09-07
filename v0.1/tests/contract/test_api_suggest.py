"""Contract tests for `GET /api/suggest`.

Address autocomplete — pure in-memory prefix lookup against the
AddressIndex the route reads from `Index.address_index`. The fake index
shipped in `tests/conftest.py` leaves this attribute unset (getattr
default = None) so we install a small AddressIndex per test.
"""
from app.core.address_index import AddressIndex


def _build_addr_index() -> AddressIndex:
    """Small fixture-scoped AddressIndex — deterministic, ~4 rows so the
    binary-search prefix path is exercised, not the empty-index short
    circuit."""
    return AddressIndex([
        {"street": "Kastanienallee", "hnr": "12", "plz": "10435",
         "lat": 52.53555, "lon": 13.40587},
        {"street": "Kastanienallee", "hnr": "14", "plz": "10435",
         "lat": 52.53556, "lon": 13.40590},
        {"street": "Bergmannstraße", "hnr": "27", "plz": "10961",
         "lat": 52.48864, "lon": 13.39631},
        {"street": "Sybelstraße", "hnr": "59", "plz": "10629",
         "lat": 52.50632, "lon": 13.31069},
    ])


# --- Contract tests -----------------------------------------------


def test_suggest_returns_empty_when_query_below_min_length(client, fake_index):
    fake_index.address_index = _build_addr_index()
    r = client.get("/api/suggest", params={"q": "K"})
    assert r.status_code == 200
    assert r.json() == {"hits": []}


def test_suggest_returns_matching_prefix(client, fake_index):
    fake_index.address_index = _build_addr_index()
    body = client.get("/api/suggest", params={"q": "Kast"}).json()
    hits = body["hits"]
    assert len(hits) == 2
    # Every hit carries the full label + coord tuple the SPA needs.
    for h in hits:
        assert set(h.keys()) == {"label", "street", "hnr", "plz", "lat", "lon"}
        assert h["street"] == "Kastanienallee"
        assert h["plz"] == "10435"
    # Sorted by house number (via normalised key).
    assert hits[0]["hnr"] == "12"
    assert hits[1]["hnr"] == "14"


def test_suggest_respects_limit_parameter(client, fake_index):
    fake_index.address_index = _build_addr_index()
    body = client.get("/api/suggest",
                      params={"q": "Kast", "limit": 1}).json()
    assert len(body["hits"]) == 1


def test_suggest_never_returns_more_than_max_limit(client, fake_index):
    # Route caps the `limit` query param at 10 via `Query(le=_MAX_LIMIT)`;
    # anything over that must 422, not silently overflow.
    fake_index.address_index = _build_addr_index()
    r = client.get("/api/suggest", params={"q": "Kast", "limit": 99})
    assert r.status_code == 422


def test_suggest_returns_empty_when_address_index_missing(client, fake_index):
    # Deployment without the address snapshot on disk → autocomplete
    # gracefully returns []; the SPA's dropdown just stays empty.
    fake_index.address_index = None
    r = client.get("/api/suggest", params={"q": "Kast"})
    assert r.status_code == 200
    assert r.json() == {"hits": []}


def test_suggest_no_match_returns_empty_hits(client, fake_index):
    fake_index.address_index = _build_addr_index()
    body = client.get("/api/suggest", params={"q": "zzz"}).json()
    assert body == {"hits": []}
