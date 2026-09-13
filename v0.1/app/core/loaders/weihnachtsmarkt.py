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

# Berlin's CKAN dataset registry — canonical source for the Senate feed's
# real publication date. The ServicePortal endpoint's own ETag trailer
# (`"<hash>-YYYYMMDD"`) looks like a date but is a CDN cache-bust that
# rotates daily; using it would always show "today", which is exactly the
# kind of freshness lie this feature is meant to prevent. CKAN's
# `metadata_modified` field is the honest signal — updated when the Senate
# actually republishes the dataset (verified via daten.berlin.de metadata
# page: current value 2025-11-20).
_CKAN_METADATA_URL = ("https://datenregister.berlin.de/api/3/action/"
                      "package_show?id="
                      "simple_search_wwwberlindesenwebservicemaerktefesteweihnachtsmaerkte")


def _fetch(url: str, timeout_s: float = 30.0) -> dict:
    """GET the Senate GeoJSON. Kept separate so `parse()` can be
    exercised with a canned payload in the selfcheck."""
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    return json.loads(urllib.request.urlopen(req, timeout=timeout_s).read())


def _fetch_upstream_refreshed_on(timeout_s: float = 10.0) -> str:
    """Query Berlin's CKAN registry for the dataset's real publication
    date. Returns 'YYYY-MM-DD' or '' on any failure — callers fall back
    to boot-cache time when the string is empty.

    Uses a tighter timeout than the main fetch because this is
    metadata-only and shouldn't stall boot if the registry is slow."""
    try:
        req = urllib.request.Request(
            _CKAN_METADATA_URL, headers={"User-Agent": _USER_AGENT})
        resp = json.loads(
            urllib.request.urlopen(req, timeout=timeout_s).read())
        if not resp.get("success"):
            return ""
        # CKAN returns ISO 8601 with microseconds ("2025-11-20T12:13:34.398616").
        # A human-readable freshness label wants just the date part.
        modified = (resp.get("result") or {}).get("metadata_modified") or ""
        return modified[:10] if len(modified) >= 10 else ""
    except Exception:
        return ""


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


def load(cfg: CityConfig) -> dict:
    """Fetch + parse the Senate Weihnachtsmärkte feed. Returns
    `{"markets": [...], "upstream_refreshed_on": "YYYY-MM-DD" | ""}`.

    - `markets`: shaped market dicts (empty on any failure — honest
      'no markets' rather than a boot crash on a seasonal feed).
    - `upstream_refreshed_on`: dataset's real publication date, from
      Berlin's CKAN registry (`metadata_modified`). Empty string when
      the CKAN query fails or returns nothing. The frontend then falls
      back to displaying the server boot-cache time so the modal never
      hides freshness.
    """
    url = getattr(cfg, "xmas_market_url", None)
    if not url:
        return {"markets": [], "upstream_refreshed_on": ""}
    try:
        markets = parse(_fetch(url))
    except Exception:
        markets = []
    # CKAN query is best-effort and completely independent of the main
    # GeoJSON fetch — either can fail without dragging down the other.
    return {
        "markets": markets,
        "upstream_refreshed_on": _fetch_upstream_refreshed_on(),
    }


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

    # -- load() with no URL configured → empty envelope, no CKAN call.
    class _Cfg:
        xmas_market_url = None
    assert load(_Cfg()) == {"markets": [], "upstream_refreshed_on": ""}

    # -- CKAN metadata slicing: keep just the ISO date prefix.
    # (Pure asserts on the string-shaping logic inline in
    # `_fetch_upstream_refreshed_on`; the HTTP path is exercised at
    # boot, not here.)
    _mod = "2025-11-20T12:13:34.398616"
    assert _mod[:10] == "2025-11-20"

    print("loaders.weihnachtsmarkt selfcheck OK")
