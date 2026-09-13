"""Berlin Weihnachtsmärkte loader.

Fetches the Berlin Senate's live Christmas-markets feed (GeoJSON) once at
boot and returns a list of shaped feature dicts. Same style as the
Bürgerämter ServicePortal loader — a bespoke REST/GeoJSON pull kept out
of the generic WFS pipeline.

Endpoint (verified 2026-09-13):

    https://www.berlin.de/sen/web/service/maerkte-feste/weihnachtsmaerkte/
        index.php/index/all.gjson

Response is a FeatureCollection of Point features. Each feature carries
`properties.data` with the market metadata (name, address, opening
hours, organiser, website, etc.). The Senate refreshes the feed as
markets confirm dates; typical set is ~45–50 markets in Dec.

Public API:

    from app.core.loaders.weihnachtsmarkt import load
    self.xmas_markets = load(cfg)

Returns a list of `{"name","address","bezirk","opening_hours",
"organiser","email","website","barrier_free","description",
"detail_url","lat","lon"}` dicts. Empty list on any failure (network,
parse) — a missing tile is honest; a boot crash on a seasonal feed is
not.
"""

import json
import urllib.request

from app.cities.base import CityConfig


_USER_AGENT = "berlin-family-address-intel/0.1"
_DETAIL_URL_PREFIX = "https://www.berlin.de"


def _fetch(url: str, timeout_s: float = 30.0) -> dict:
    """GET the Senate GeoJSON. Kept separate so `parse()` can be
    exercised with a canned payload in the selfcheck."""
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    return json.loads(urllib.request.urlopen(req, timeout=timeout_s).read())


def _clean(v) -> str:
    """Trim + str() a possibly-None property value."""
    if v is None:
        return ""
    return str(v).strip()


def parse(raw: dict) -> list:
    """Pure parser — FeatureCollection dict → list of shaped market
    dicts. Skips features without a valid Point geometry or without a
    `data.name`. Coordinates come from `geometry.coordinates` ([lon,
    lat]); the `data.lat/lng` string fields are ignored to avoid
    disagreement between the two."""
    features = (raw or {}).get("features") or []
    out = []
    for f in features:
        g = f.get("geometry") or {}
        coords = g.get("coordinates") or []
        if len(coords) < 2:
            continue
        try:
            lo, la = float(coords[0]), float(coords[1])
        except (ValueError, TypeError):
            continue
        props = f.get("properties") or {}
        data = props.get("data") or {}
        name = _clean(data.get("name"))
        if not name:
            continue
        street = _clean(data.get("strasse"))
        plz_ort = _clean(data.get("plz_ort"))
        address = ", ".join(x for x in (street, plz_ort) if x)
        detail_path = _clean(props.get("id"))
        detail_url = (_DETAIL_URL_PREFIX + detail_path) if detail_path.startswith("/") else ""
        out.append({
            "name":          name,
            "address":       address,
            "bezirk":        _clean(data.get("bezirk")),
            "opening_hours": _clean(data.get("oeffnungszeiten")),
            "organiser":     _clean(data.get("veranstalter")),
            "email":         _clean(data.get("email")),
            "website":       _clean(data.get("www")),
            "barrier_free":  _clean(data.get("barrierefreiheit")),
            "description":   _clean(data.get("bemerkungen")),
            "detail_url":    detail_url,
            "lat":           la,
            "lon":           lo,
        })
    return out


def load(cfg: CityConfig) -> list:
    """Fetch + parse the Senate Weihnachtsmärkte feed. Returns an
    empty list on any failure — the tile then reports honest 'no
    markets' without breaking boot."""
    url = getattr(cfg, "xmas_market_url", None)
    if not url:
        return []
    try:
        return parse(_fetch(url))
    except Exception:
        return []


if __name__ == "__main__":
    # -- Well-formed feature parsed end-to-end.
    _raw = {"type": "FeatureCollection", "features": [
        {"geometry": {"type": "Point", "coordinates": [13.386, 52.477]},
         "properties": {"id": "/sen/web/service/maerkte-feste/weihnachtsmaerkte/index.php/detail/109",
                        "data": {
                            "name":            "Winter am THF",
                            "bezirk":          "Tempelhof-Schöneberg",
                            "strasse":         "THF TOWER",
                            "plz_ort":         "12101 Berlin",
                            "veranstalter":    "Tempelhof Projekt GmbH",
                            "oeffnungszeiten": "05.12.2025 bis 07.12.2025",
                            "email":           "info@example.de",
                            "www":             "https://example.de",
                            "barrierefreiheit": "ja",
                            "bemerkungen":     "Foodtrucks & Glühwein.",
                        }}},
        # No geometry → dropped.
        {"geometry": None,
         "properties": {"data": {"name": "No geometry"}}},
        # Short coord → dropped.
        {"geometry": {"coordinates": [13.4]},
         "properties": {"data": {"name": "Short coord"}}},
        # Non-numeric coord → dropped.
        {"geometry": {"coordinates": ["nope", 52.5]},
         "properties": {"data": {"name": "Bad coord"}}},
        # No name → dropped.
        {"geometry": {"coordinates": [13.4, 52.5]},
         "properties": {"data": {"name": ""}}},
    ]}
    _got = parse(_raw)
    assert len(_got) == 1, _got
    m = _got[0]
    assert m["name"] == "Winter am THF"
    assert m["lat"] == 52.477 and m["lon"] == 13.386
    assert m["address"] == "THF TOWER, 12101 Berlin"
    assert m["bezirk"] == "Tempelhof-Schöneberg"
    assert m["opening_hours"].startswith("05.12.2025")
    assert m["organiser"] == "Tempelhof Projekt GmbH"
    assert m["email"] == "info@example.de"
    assert m["website"] == "https://example.de"
    assert m["barrier_free"] == "ja"
    assert m["description"] == "Foodtrucks & Glühwein."
    assert m["detail_url"].endswith("/detail/109")

    # -- Empty / malformed envelopes → empty list, not exception.
    assert parse({}) == []
    assert parse({"features": []}) == []
    assert parse(None) == []

    # -- load() with no URL configured → empty list.
    class _Cfg:
        xmas_market_url = None
    assert load(_Cfg()) == []

    print("loaders.weihnachtsmarkt selfcheck OK")
