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


# --- Input-validation contract (see app/routes/lookup.py Query patterns) ----

def test_lookup_rejects_oversized_address(client):
    """address is capped at max_length=200. 5 000 chars → 422."""
    r = client.get("/api/lookup", params={"address": "x" * 5000})
    assert r.status_code == 422


def test_lookup_rejects_disallowed_chars_in_address(client):
    """Address allow-list bans < > and other XSS-y punctuation."""
    r = client.get("/api/lookup",
                   params={"address": "Kastanienallee 12 <script>alert(1)</script>"})
    assert r.status_code == 422


def test_lookup_accepts_german_umlauts_and_eszett(client):
    """`Straße`, `ÄÖÜ`, `ß` must all pass the allow-list."""
    r = client.get("/api/lookup",
                   params={"address": "Konrad-Wolf-Straße 44A, 13055"})
    # Route may still 404 (fake index doesn't know this address) but must
    # NOT 422 — that would mean valid German addresses are being rejected.
    assert r.status_code != 422, r.text


def test_lookup_accepts_accented_place_names(client):
    """Real Berlin streets carry French / Spanish / Portuguese diacritics.

    Regression for the allow-list being too narrow: the initial version
    of `_ADDR_CHARS` accepted only ÄÖÜäöüß and rejected e.g.
    Renée-Sintenis-Platz (é), Courbièreplatz (è), Garbátyplatz (á),
    Léon-Jouhaux-Straße. Verified in v0.1/data/osm/berlin-amenities.json.
    """
    for street in (
        "Renée-Sintenis-Platz 1, 13187",
        "Courbièreplatz 2, 10787",
        "Léon-Jouhaux-Straße 5, 12681",
    ):
        r = client.get("/api/lookup", params={"address": street})
        assert r.status_code != 422, f"{street} was rejected: {r.text}"


def test_lookup_rejects_newline_and_null_injection(client):
    """`\\n \\r \\0` must never reach the geocoder or the log line.

    Rust regex `^…$` rejects trailing newlines out of the box — a
    future rewrite that swaps to Python `re` in non-MULTILINE mode
    would silently regress this because Python `$` also matches
    immediately before a trailing `\\n`.
    """
    for suffix in ("\n", "\r", "\r\n", "\x00"):
        r = client.get("/api/lookup",
                       params={"address": "Kastanienallee 12" + suffix})
        assert r.status_code == 422, f"suffix {suffix!r} slipped through"


def test_lookup_accepts_hnr_with_space(client):
    """BOD returns some house numbers as `12 A` (with space)."""
    r = client.get("/api/lookup",
                   params={"street": "Wilmersdorfer Straße",
                           "hnr": "12 A", "plz": "10627"})
    assert r.status_code != 422, r.text


def test_lookup_rejects_short_plz(client):
    """PLZ must be exactly 5 digits (or empty). `1043` → 422."""
    r = client.get("/api/lookup",
                   params={"street": "Kastanienallee", "hnr": "12", "plz": "1043"})
    assert r.status_code == 422


def test_lookup_rejects_hnr_over_10_chars(client):
    r = client.get("/api/lookup",
                   params={"street": "Kastanienallee", "hnr": "1" * 20, "plz": "10435"})
    assert r.status_code == 422


def test_lookup_rejects_non_digit_plz(client):
    r = client.get("/api/lookup",
                   params={"street": "Kastanienallee", "hnr": "12", "plz": "abcde"})
    assert r.status_code == 422


def test_lookup_rejects_plz_over_5_digits(client):
    r = client.get("/api/lookup",
                   params={"street": "Kastanienallee", "hnr": "12", "plz": "104350"})
    assert r.status_code == 422
