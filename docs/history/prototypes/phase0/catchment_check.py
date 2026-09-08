#!/usr/bin/env python3
"""
Phase 0 validation: Berlin address → assigned public Grundschule (catchment).
Answers the single most important question in the product doc:
  "Does the Schulen WFS return usable Einschulbereich polygons?" → YES.

Data sources (Geoportal Berlin, dl-de/by-2.0):
  - schulen:schulen_esb (394 MultiPolygon Einschulbereiche)
  - schulen:schulen (~930 school points; 385 public Grundschulen)
  - adressen_berlin:adressen_berlin (address geocoder, EPSG:25833)

Run:  python3 catchment_check.py
Deps: shapely  (pip3 install --user shapely)

ponytail: pure stdlib + shapely; production version moves polygons into PostGIS
          with a nightly WFS refresh and does the point-in-polygon in SQL.
"""
import urllib.request
import urllib.parse
import json
import sys
from collections import Counter
from shapely.geometry import shape, Point

WFS_SCHULEN = "https://gdi.berlin.de/services/wfs/schulen"
WFS_ADR     = "https://gdi.berlin.de/services/wfs/adressen_berlin"


def wfs(base, **kw):
    kw.setdefault("service", "WFS")
    kw.setdefault("version", "2.0.0")
    kw.setdefault("request", "GetFeature")
    kw.setdefault("outputFormat", "application/json")
    url = base + "?" + urllib.parse.urlencode(kw)
    return json.loads(urllib.request.urlopen(url, timeout=60).read())


def esc(s):
    return s.replace("'", "''")


def load_index():
    """Fetch and cache all polygons + Grundschulen."""
    esbs = wfs(WFS_SCHULEN, typeNames="schulen:schulen_esb", count=1000)
    esb_shapes = [(f["properties"], shape(f["geometry"])) for f in esbs["features"]]

    gs = wfs(
        WFS_SCHULEN,
        typeNames="schulen:schulen",
        CQL_FILTER="schulart='Grundschule' AND traeger='öffentlich'",
        count=2000,
    )
    gs_pts = [(f["properties"], Point(f["geometry"]["coordinates"])) for f in gs["features"]]

    esb_to_schools = {}
    for props, geom in esb_shapes:
        esb_to_schools[props["esb"]] = [p for p, pt in gs_pts if geom.contains(pt)]

    return esb_shapes, esb_to_schools


def geocode(street, hnr, plz):
    r = wfs(
        WFS_ADR,
        typeNames="adressen_berlin:adressen_berlin",
        CQL_FILTER=f"str_name='{esc(street)}' AND hnr='{hnr}' AND plz='{plz}'",
        count=1,
    )
    if not r.get("features"):
        return None
    lon, lat = r["features"][0]["geometry"]["coordinates"]
    return lon, lat, r["features"][0]["properties"]


def catchment_for(lon, lat, esb_shapes, esb_to_schools):
    pt = Point(lon, lat)
    for props, geom in esb_shapes:
        if geom.contains(pt):
            return props, esb_to_schools.get(props["esb"], [])
    return None, []


def main():
    esb_shapes, esb_to_schools = load_index()
    counts = Counter(len(v) for v in esb_to_schools.values())
    total = len(esb_shapes)
    print(f"Loaded {total} Einschulbereich polygons, "
          f"{sum(len(v) for v in esb_to_schools.values())} school assignments.")
    for n, cnt in sorted(counts.items()):
        pct = cnt * 100 / total
        print(f"  {cnt:3d} polygons ({pct:4.1f}%) contain {n} Grundschule(n)")

    tests = [
        ("Kastanienallee", "12", "10435"),
        ("Bergmannstraße", "27", "10961"),
        ("Boxhagener Straße", "15", "10245"),
        ("Sonnenallee", "100", "12045"),
        ("Kurfürstendamm", "195", "10707"),
    ]
    for street, hnr, plz in tests:
        print(f"\n{street} {hnr}, {plz}")
        g = geocode(street, hnr, plz)
        if not g:
            print("  address not found"); continue
        lon, lat, props = g
        esb_props, schools = catchment_for(lon, lat, esb_shapes, esb_to_schools)
        if not esb_props:
            print("  no ESB polygon contains address"); continue
        print(f"  esb={esb_props['esb']} ({esb_props['bezname']})")
        for s in schools or []:
            print(f"    → {s['schulname']} — {s['strasse']} {s['hausnr']}, {s['plz']} (bsn {s['bsn']})")
        if not schools:
            print("    ⚠ no public Grundschule inside polygon — needs district-office fallback")


# assert-based self-check: the smallest test that fails if the logic breaks
def _selfcheck():
    esb_shapes, esb_to_schools = load_index()
    assert len(esb_shapes) >= 300, "expected many polygons; got few"
    g = geocode("Kastanienallee", "12", "10435")
    assert g, "known Prenzlauer Berg address must geocode"
    lon, lat, _ = g
    esb_props, schools = catchment_for(lon, lat, esb_shapes, esb_to_schools)
    assert esb_props and esb_props["bezname"] == "Pankow"
    assert any("Senefelderplatz" in s["schulname"] for s in schools), \
        "Kastanienallee 12 must resolve to Schule am Senefelderplatz"
    print("selfcheck: OK")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        _selfcheck()
    else:
        main()
