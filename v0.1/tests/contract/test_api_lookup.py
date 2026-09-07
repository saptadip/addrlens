"""Contract tests for `/api/lookup` — aggregating endpoint.

The fake index shipped in `tests/conftest.py` returns Alexanderplatz
coords for any address; every downstream method returns empty state so
the route runs its full aggregation without touching the network.
"""


def test_lookup_missing_address_returns_400(client):
    # No address, no street/hnr/plz → 400.
    r = client.get("/api/lookup")
    assert r.status_code == 400


def test_lookup_unparseable_address_returns_400(client):
    r = client.get("/api/lookup", params={"address": "asdf"})
    assert r.status_code == 400


def test_lookup_happy_path_returns_200(client):
    r = client.get("/api/lookup", params={"address": "Kastanienallee 12, 10435"})
    # /api/lookup is an aggregating endpoint — per-category failures are
    # tolerated behind an `_error` pattern, so the request itself must
    # succeed even with an empty fake index.
    assert r.status_code == 200


def test_lookup_response_carries_address_and_provenance(client):
    body = client.get("/api/lookup",
                       params={"address": "Kastanienallee 12, 10435"}).json()
    assert "address" in body
    assert body["address"]["street"] == "Kastanienallee"
    assert body["address"]["hnr"] == "12"
    assert body["address"]["plz"] == "10435"
    assert "provenance" in body
    assert isinstance(body["provenance"], dict)
    # A representative sample of provenance keys the frontend footer expects.
    for key in ("catchment", "schools", "addresses", "kitas"):
        assert key in body["provenance"], f"provenance missing key: {key}"


def test_lookup_carries_lens_envelope(client):
    body = client.get("/api/lookup",
                       params={"address": "Kastanienallee 12, 10435"}).json()
    assert "lens" in body
    for slug in ("young_family", "newcomer", "quiet_living", "commuter"):
        assert slug in body["lens"], f"missing lens: {slug}"
