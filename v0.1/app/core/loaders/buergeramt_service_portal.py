"""service.berlin.de Bürgerämter loader.

Berlin doesn't publish Bürgerämter via WFS on gdi.berlin.de — the
canonical dataset lives on the ServicePortal at service.berlin.de as a
JSON envelope wrapping a GeoJSON `features` array. Each feature carries
an HTML `description` field that in turn holds the street address and
the per-location detail URL.

Isolated in its own module so the rest of `Index.__init__` stays a
list of straightforward WFS loads. The REST/HTML/dedup/skip-list
logic here is genuinely bespoke to this endpoint and doesn't belong
inline with the generic WFS pipeline.

Public API:

    from app.core.loaders.buergeramt_service_portal import load
    self.buergeramts = load(cfg)

Returns a list of `{"name", "address", "website", "lat", "lon"}` dicts.

Response shape (as at 2026-02):

    {
      "buergeramt": {
        "data": {
          "features": [
            {"geometry": {"coordinates": [lon, lat, ...]},
             "properties": {"name": "…", "description": "<html…>"}}
          ]
        }
      }
    }

Skip / dedup rules preserved verbatim from the pre-split
`Index.__init__:352-396`:

- Deduplicate by rounded (lon,lat) coordinate — the feed lists
  ~50 unique buildings but ~200 service-appointment sub-entries all
  sharing the same coord. Keep the first hit per coord bucket.
- Drop training-only / document-pickup / appointment-only entries
  matched by keyword against the name (case-insensitive).
- Address is the first `<p>…<br>` block inside `description`
  (HTML tags stripped).
- Website is the first `service.berlin.de/standort/…` link.

`ponytail:` the HTML scrape is brittle by design — the ServicePortal
publishes description strings that are stable enough to parse but
not standardised. If the format ever changes, this module is the one
place to update. Upgrade path: consume the ServicePortal's structured
JSON detail endpoint per-location once it exposes address as a
first-class field.
"""

import json
import re
import urllib.request

from app.cities.base import CityConfig


_SKIP_KEYWORDS = (
    "ausbildung", "abholung", "vorzugstermin", "terminfreis",
    "ausbildungsplatz", "mobiles",
)
_ADDRESS_RE = re.compile(r"<p>(.*?)<br", re.DOTALL)
_WEBSITE_RE = re.compile(r'href="(https://service\.berlin\.de/standort/[^"]+)"')
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_USER_AGENT = "berlin-family-address-intel/0.1"


def _fetch(url: str, timeout_s: float = 60.0) -> dict:
    """GET the ServicePortal JSON envelope. Kept separate so the parser
    is testable with a canned payload."""
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    return json.loads(urllib.request.urlopen(req, timeout=timeout_s).read())


def _parse_address(description_html: str) -> str:
    """Extract the first `<p>…<br>` chunk, strip HTML, return the
    trimmed text. Empty string if no match."""
    m = _ADDRESS_RE.search(description_html or "")
    if not m:
        return ""
    return _HTML_TAG_RE.sub("", m.group(1)).strip()


def _parse_website(description_html: str) -> str:
    """Extract the first service.berlin.de/standort/ URL, else empty."""
    m = _WEBSITE_RE.search(description_html or "")
    return m.group(1) if m else ""


def parse(raw: dict) -> list:
    """Pure parser — turn the ServicePortal JSON envelope into the same
    list of dicts `Index` used to build inline. Exposed so the module
    selfcheck can pin the dedup + skip-keyword rules without live HTTP.
    """
    features = (raw.get("buergeramt", {})
                   .get("data", {})
                   .get("features", []))
    out = []
    seen_coords = set()
    for f in features:
        g = f.get("geometry")
        if not g:
            continue
        coords = g.get("coordinates") or []
        if len(coords) < 2:
            continue
        try:
            lo, la = float(coords[0]), float(coords[1])
        except (ValueError, TypeError):
            continue
        # Dedup by rounded coord — many service variants share one building.
        coord_key = (round(lo, 4), round(la, 4))
        if coord_key in seen_coords:
            continue
        p = f.get("properties") or {}
        name = (p.get("name") or "Bürgeramt").strip()
        if any(kw in name.lower() for kw in _SKIP_KEYWORDS):
            continue
        seen_coords.add(coord_key)
        desc = p.get("description") or ""
        out.append({
            "name":    name,
            "address": _parse_address(desc),
            "website": _parse_website(desc),
            "lat":     la,
            "lon":     lo,
        })
    return out


def load(cfg: CityConfig) -> list:
    """Fetch + parse the ServicePortal Bürgerämter feed for `cfg`.

    `cfg.buergeramt_wfs_url` holds the REST URL (not a WFS URL — the
    naming is legacy from when it was going to be a WFS). Returns a
    list of `{"name", "address", "website", "lat", "lon"}` dicts.
    """
    raw = _fetch(cfg.buergeramt_wfs_url)
    return parse(raw)


if __name__ == "__main__":
    # -- Address + website extraction on realistic HTML.
    _desc = (
        "<div class='wrapper'>"
        "<p>Musterstraße 12<br>"
        "10115 Berlin</p>"
        "<a href=\"https://service.berlin.de/standort/122211/\">Details</a>"
        "</div>"
    )
    assert _parse_address(_desc) == "Musterstraße 12", _parse_address(_desc)
    assert _parse_website(_desc) == "https://service.berlin.de/standort/122211/"
    # Empty description → empty strings, not exceptions.
    assert _parse_address("") == ""
    assert _parse_website("") == ""
    assert _parse_address(None) == ""

    # -- parse(): dedup + skip-keyword logic on a synthetic envelope.
    _raw = {"buergeramt": {"data": {"features": [
        {"geometry": {"coordinates": [13.4, 52.5]},
         "properties": {"name": "Bürgeramt Mitte",
                        "description": "<p>Alpha 1<br>10115 Berlin</p>"
                                       "<a href=\"https://service.berlin.de/standort/1/\">x</a>"}},
        # Same coord (rounded to 4 dp) → dropped.
        {"geometry": {"coordinates": [13.40004, 52.50004]},
         "properties": {"name": "Bürgeramt Mitte — Zusatztermine",
                        "description": "…"}},
        # Skip-keyword (Abholung) → dropped even at a new coord.
        {"geometry": {"coordinates": [13.5, 52.6]},
         "properties": {"name": "Abholung Standort 12",
                        "description": "…"}},
        # No geometry → dropped.
        {"geometry": None,
         "properties": {"name": "Bürgeramt Wedding"}},
        # Coordinates too short → dropped.
        {"geometry": {"coordinates": [13.5]},
         "properties": {"name": "Bürgeramt Neukölln"}},
        # Non-numeric coordinate → dropped.
        {"geometry": {"coordinates": ["oops", 52.5]},
         "properties": {"name": "Broken"}},
        # New coord, valid — kept.
        {"geometry": {"coordinates": [13.42, 52.52]},
         "properties": {"name": "Bürgeramt Kreuzberg",
                        "description": "<p>Beta 5<br>10999 Berlin</p>"}},
    ]}}}

    _got = parse(_raw)
    assert [b["name"] for b in _got] == ["Bürgeramt Mitte", "Bürgeramt Kreuzberg"], _got
    assert _got[0]["address"] == "Alpha 1", _got[0]
    assert _got[0]["website"].endswith("/standort/1/")
    assert _got[0]["lat"] == 52.5 and _got[0]["lon"] == 13.4
    # Missing website + address handled gracefully.
    assert _got[1]["website"] == ""
    assert _got[1]["address"] == "Beta 5"

    # -- Skip keyword match is case-insensitive.
    _raw_case = {"buergeramt": {"data": {"features": [
        {"geometry": {"coordinates": [13.60, 52.60]},
         "properties": {"name": "Vorzugstermin Sonderfall",
                        "description": ""}},
    ]}}}
    assert parse(_raw_case) == []

    # -- Empty envelope → empty list.
    assert parse({}) == []
    assert parse({"buergeramt": {}}) == []

    print("loaders.buergeramt_service_portal selfcheck OK")
