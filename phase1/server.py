#!/usr/bin/env python3
"""
Berlin Family Address Intelligence — Phase 1 MVP.

Single-file server: stdlib http.server + shapely + WFS + OSM Overpass.
Answers the ship criterion: "which school will my child go to?" in <10 s.

Run:  python3 server.py           # then open http://localhost:8000
Deps: shapely  (pip3 install --user shapely)

Data:
  - Geoportal Berlin: schulen_esb (catchments), schulen (all schools),
    adressen_berlin (geocoder)               [dl-de/zero-2.0 / dl-de/by-2.0]
  - OSM Overpass: kindergartens + amenities (playgrounds, pharmacies,
    supermarkets, GPs, transit stops) around a point   [ODbL]

ponytail: proto-server. Production would move polygons into PostGIS with a
          nightly refresh, put a real framework in front, and rate-limit
          Overpass calls at the edge.
"""
import http.server, socketserver, json, urllib.request, urllib.parse
import threading, math, sys, os, unicodedata
from pathlib import Path
from shapely.geometry import shape, Point, mapping

HERE          = Path(__file__).parent
WFS_SCHULEN   = "https://gdi.berlin.de/services/wfs/schulen"
WFS_ADR       = "https://gdi.berlin.de/services/wfs/adressen_berlin"
OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
PORT          = int(os.environ.get("PORT", "8000"))

# Public SESB Grundschule strands (source: berlin.de/sen/bjf/schulen/besondere-schulen/sesb).
# WFS carries no SESB attribute, so a small hand-curated list is the only path.
# Substring match against schulname (lower-cased, ß-normalised).
SESB_GRUNDSCHULEN = {
    "aziz-nesin": "German-Turkish",
    "charles-dickens": "German-English",
    "christian-morgenstern": "German-Russian",
    "finow": "German-Italian",
    "homer": "German-Greek",
    "hunsruck": "German-Turkish",
    "joan-miro": "German-Spanish",
    "judith-kerr": "German-English",
    "kastanienbaum": "German-French",
    "konrad-duden": "German-Polish",
    "markische": "German-French",
    "neumark": "German-Portuguese",
    "regenbogen": "German-Portuguese",
    "wedding-grundschule": "German-French",
}
INTL_KEYWORDS = ("international", "english", "american", "british",
                 "bilingual", "bilinguale", "jfk", "kennedy", "europa")


# -- utilities ---------------------------------------------------------------

def norm(s: str) -> str:
    """Lower-case + strip diacritics (NFD, drop combining marks) + ß → ss."""
    s = s.lower().replace("ß", "ss")
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if not unicodedata.combining(c))


def wfs(base, **kw):
    kw.setdefault("service", "WFS")
    kw.setdefault("version", "2.0.0")
    kw.setdefault("request", "GetFeature")
    kw.setdefault("outputFormat", "application/json")
    kw.setdefault("srsName", "EPSG:4326")   # always WGS84 lon,lat
    url = base + "?" + urllib.parse.urlencode(kw)
    return json.loads(urllib.request.urlopen(url, timeout=60).read())


def cql_esc(s):
    return s.replace("'", "''")


def haversine_m(lon1, lat1, lon2, lat2):
    """Great-circle distance in metres."""
    R = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2 * R * math.asin(math.sqrt(a))


# -- data index (loaded once on startup) -------------------------------------

class Index:
    def __init__(self):
        sys.stdout.write("loading catchment polygons… "); sys.stdout.flush()
        esbs = wfs(WFS_SCHULEN, typeNames="schulen:schulen_esb", count=1000)
        self.esbs = [(f["properties"], shape(f["geometry"])) for f in esbs["features"]]
        print(f"{len(self.esbs)} polygons")

        sys.stdout.write("loading all schools… "); sys.stdout.flush()
        s = wfs(WFS_SCHULEN, typeNames="schulen:schulen", count=2000)
        self.schools = [(f["properties"], f["geometry"]["coordinates"])
                        for f in s["features"] if f.get("geometry")]

        self.gs_public = [(p, c) for p, c in self.schools
                          if p.get("schulart") == "Grundschule"
                          and p.get("traeger") == "öffentlich"]
        # School types that include primary years — Grundschule + combined + community.
        primary_types = {"Grundschule", "Gemeinschaftsschule", "Kombinierte allgemein bildende Schule"}
        self.gs_intl = [(p, c) for p, c in self.schools
                        if p.get("schulart") in primary_types
                        and any(k in norm(p["schulname"]) for k in INTL_KEYWORDS)]

        self.esb_to_gs = {}
        for props, geom in self.esbs:
            self.esb_to_gs[props["esb"]] = [
                (p, c) for p, c in self.gs_public if geom.contains(Point(c))
            ]
        print(f"{len(self.gs_public)} public Grundschulen · {len(self.gs_intl)} intl/bilingual")

    def geocode(self, street, hnr, plz):
        r = wfs(WFS_ADR, typeNames="adressen_berlin:adressen_berlin",
                CQL_FILTER=f"str_name='{cql_esc(street)}' AND hnr='{cql_esc(hnr)}' AND plz='{cql_esc(plz)}'",
                count=1)
        if not r.get("features"):
            return None
        lon, lat = r["features"][0]["geometry"]["coordinates"]
        return {"lon": lon, "lat": lat, "props": r["features"][0]["properties"]}

    def catchment(self, lon, lat):
        pt = Point(lon, lat)
        for props, geom in self.esbs:
            if geom.contains(pt):
                return props, geom, self.esb_to_gs.get(props["esb"], [])
        return None, None, []

    def nearest_intl(self, lon, lat):
        if not self.gs_intl:
            return None
        best = min(self.gs_intl, key=lambda pc: haversine_m(lon, lat, pc[1][0], pc[1][1]))
        p, c = best
        return {"school": p, "lon": c[0], "lat": c[1],
                "distance_m": round(haversine_m(lon, lat, c[0], c[1]))}

    def sesb_strand(self, schulname):
        low = norm(schulname)
        for key, strand in SESB_GRUNDSCHULEN.items():
            if key in low:
                return strand
        return None


# -- OSM Overpass helper (falls back through public mirrors on failure) ------

def overpass(ql, timeout_s=60):
    """Try Overpass mirrors in order; return parsed JSON or raise last error."""
    err = None
    for url in OVERPASS_ENDPOINTS:
        try:
            req = urllib.request.Request(
                url, data=urllib.parse.urlencode({"data": ql}).encode(),
                headers={"User-Agent": "berlin-family-address-intel/0.1"})
            return json.loads(urllib.request.urlopen(req, timeout=timeout_s).read())
        except Exception as e:
            err = e
    raise err


# -- OSM Kita count (Overpass, small in-memory cache) ------------------------

_kita_cache, _kita_lock = {}, threading.Lock()

def kitas_near(lon, lat, radius_m=800):
    """Return {'count': N, 'items': [...]} — OSM childcare within radius."""
    key = (round(lon, 4), round(lat, 4), radius_m)
    with _kita_lock:
        if key in _kita_cache:
            return _kita_cache[key]
    ql = (f'[out:json][timeout:60];'
          f'(nwr["amenity"="kindergarten"](around:{radius_m},{lat},{lon}););'
          f'out center;')
    try:
        d = overpass(ql, timeout_s=75)
    except Exception as e:
        return {"count": None, "items": [], "error": str(e)}
    items = []
    for el in d.get("elements", []):
        lat_, lon_ = (el.get("lat"), el.get("lon")) if el["type"] == "node" \
                    else (el.get("center", {}).get("lat"), el.get("center", {}).get("lon"))
        if lat_ is None: continue
        items.append({"name": (el.get("tags") or {}).get("name") or "Kita",
                      "lat": lat_, "lon": lon_})
    out = {"count": len(items), "items": items}
    with _kita_lock:
        _kita_cache[key] = out
    return out


# -- OSM amenities (playgrounds, pharmacies, supermarkets, GPs, transit) -----

AMENITIES = [
    ("playgrounds",  '["leisure"="playground"]',                     "Playground"),
    ("pharmacies",   '["amenity"="pharmacy"]',                       "Pharmacy"),
    ("supermarkets", '["shop"="supermarket"]',                       "Supermarket"),
    ("gps",          '["amenity"="doctors"]',                        "Doctor's office"),
    ("transit",      '["public_transport"~"^(platform|station)$"]',  "Transit stop"),
]

_amen_cache, _amen_lock = {}, threading.Lock()

def _classify_amenity(tags):
    if tags.get("leisure") == "playground":                        return "playgrounds"
    if tags.get("amenity") == "pharmacy":                          return "pharmacies"
    if tags.get("shop") == "supermarket":                          return "supermarkets"
    if tags.get("amenity") == "doctors":                           return "gps"
    if tags.get("public_transport") in ("platform", "station"):    return "transit"
    return None

def _short_hours(oh):
    return oh if len(oh) <= 42 else oh[:39] + "…"

def _summarize(cat, tags):
    """One short human-readable line built from OSM tags. Empty = no useful data."""
    parts = []
    if cat == "transit":
        modes = []
        if tags.get("subway") == "yes" or tags.get("station") == "subway":   modes.append("U-Bahn")
        if tags.get("light_rail") == "yes" or tags.get("station") == "light_rail": modes.append("S-Bahn")
        if tags.get("tram") == "yes":  modes.append("Tram")
        if tags.get("bus") == "yes":   modes.append("Bus")
        if tags.get("train") == "yes": modes.append("Train")
        if modes: parts.append(" · ".join(modes))
        if tags.get("operator"):       parts.append(tags["operator"])
        if tags.get("wheelchair") == "yes": parts.append("Step-free")
    elif cat == "pharmacies":
        if tags.get("dispensing") == "yes":       parts.append("Prescriptions")
        if tags.get("opening_hours"):             parts.append(_short_hours(tags["opening_hours"]))
        if tags.get("phone"):                     parts.append("☎ " + tags["phone"])
        if tags.get("wheelchair") == "yes":       parts.append("Step-free")
    elif cat == "supermarkets":
        if tags.get("brand"):                     parts.append(tags["brand"])
        if tags.get("organic") == "yes":          parts.append("Organic")
        if tags.get("opening_hours"):             parts.append(_short_hours(tags["opening_hours"]))
    elif cat == "gps":
        spec = tags.get("healthcare:speciality") or tags.get("healthcare:specialty")
        if spec:                                  parts.append(spec.replace(";", ", ").replace("_", " ").title())
        if tags.get("phone"):                     parts.append("☎ " + tags["phone"])
        if tags.get("wheelchair") == "yes":       parts.append("Step-free")
    elif cat == "playgrounds":
        a_min = tags.get("min_age") or tags.get("age:min")
        a_max = tags.get("max_age") or tags.get("age:max")
        if a_min or a_max:                        parts.append(f"Ages {a_min or '?'}–{a_max or '?'}")
        if tags.get("surface"):                   parts.append("Surface: " + tags["surface"])
        if tags.get("fee") == "yes":              parts.append("Fee")
        if tags.get("wheelchair") == "yes":       parts.append("Step-free")
        if tags.get("fenced") == "yes":           parts.append("Fenced")
    return " · ".join(parts)

def amenities_near(lon, lat, radius_m=800):
    """One Overpass round-trip for all categories.
    ponytail: tried per-category parallel (5×requests) but Overpass per-IP slot
    limit made it slower + flaky. Combined query wins; frontend fetches eagerly
    so the user perceives no wait."""
    key = (round(lon, 4), round(lat, 4), radius_m)
    with _amen_lock:
        if key in _amen_cache:
            return _amen_cache[key]
    parts = "".join(f"nwr{flt}(around:{radius_m},{lat},{lon});" for _, flt, _ in AMENITIES)
    ql = f"[out:json][timeout:60];({parts});out center tags;"
    try:
        d = overpass(ql, timeout_s=75)
    except Exception as e:
        return {k: {"count": None, "items": [], "error": str(e)} for k, _, _ in AMENITIES}

    fallback = {k: lbl for k, _, lbl in AMENITIES}
    buckets  = {k: [] for k, _, _ in AMENITIES}
    seen     = {k: set() for k, _, _ in AMENITIES}
    for el in d.get("elements", []):
        tags = el.get("tags") or {}
        cat = _classify_amenity(tags)
        if not cat: continue
        lat_, lon_ = (el.get("lat"), el.get("lon")) if el["type"] == "node" \
                    else (el.get("center", {}).get("lat"), el.get("center", {}).get("lon"))
        if lat_ is None: continue
        name = tags.get("name") or fallback[cat]
        # ponytail: dedupe transit by name (platform+station nodes share names);
        # ceiling: two same-name stops within 800m collapse — rare in Berlin.
        dkey = (name,) if cat == "transit" else (name, round(lat_, 5), round(lon_, 5))
        if dkey in seen[cat]: continue
        seen[cat].add(dkey)
        buckets[cat].append({"name": name, "lat": lat_, "lon": lon_,
                             "distance_m": round(haversine_m(lon, lat, lon_, lat_)),
                             "info": _summarize(cat, tags)})
    result = {k: {"count": len(v), "items": sorted(v, key=lambda x: x["distance_m"])[:25]}
              for k, v in buckets.items()}
    with _amen_lock:
        _amen_cache[key] = result
    return result


# -- HTTP handler ------------------------------------------------------------

INDEX = None  # populated in main()

def parse_address(q: str):
    """Very loose 'Street 12, 10435' parser. Returns (street, hnr, plz) or None."""
    q = (q or "").strip()
    if not q:
        return None
    if "," in q:
        left, right = q.rsplit(",", 1)
        plz = "".join(ch for ch in right if ch.isdigit())[:5]
    else:
        parts = q.split()
        if len(parts) < 2: return None
        plz = parts[-1] if parts[-1].isdigit() and len(parts[-1]) == 5 else ""
        left = " ".join(parts[:-1]) if plz else q
    tokens = left.strip().split()
    hnr = ""
    for i in range(len(tokens) - 1, -1, -1):
        if any(ch.isdigit() for ch in tokens[i]):
            hnr = tokens[i]; street = " ".join(tokens[:i]); break
    else:
        return None
    if not street or not plz:
        return None
    return street, hnr, plz


class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"[{self.log_date_time_string()}] {fmt % args}")

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path: Path, ctype):
        try:
            body = path.read_bytes()
        except FileNotFoundError:
            self.send_error(404); return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(u.query)
        if u.path == "/":
            return self._file(HERE / "index.html", "text/html; charset=utf-8")
        if u.path == "/health":
            return self._json({"ok": True, "polygons": len(INDEX.esbs)})
        if u.path == "/api/lookup":
            return self._lookup(qs)
        if u.path == "/api/amenities":
            return self._amenities(qs)
        self.send_error(404)

    def _amenities(self, qs):
        try:
            lat = float((qs.get("lat") or [""])[0])
            lon = float((qs.get("lon") or [""])[0])
        except ValueError:
            return self._json({"error": "lat and lon required"}, 400)
        return self._json({
            "amenities": amenities_near(lon, lat, 800),
            "provenance": "© OpenStreetMap contributors (ODbL)",
        })

    def _lookup(self, qs):
        addr = (qs.get("address") or [""])[0].strip()
        street = (qs.get("street") or [""])[0].strip()
        hnr    = (qs.get("hnr")    or [""])[0].strip()
        plz    = (qs.get("plz")    or [""])[0].strip()

        if addr and not (street and hnr and plz):
            p = parse_address(addr)
            if not p:
                return self._json({"error": "Could not parse address. Try 'Kastanienallee 12, 10435'."}, 400)
            street, hnr, plz = p

        if not (street and hnr and plz):
            return self._json({"error": "Missing street/hnr/plz."}, 400)

        try:
            geo = INDEX.geocode(street, hnr, plz)
        except Exception as e:
            return self._json({"error": f"Geocoder unavailable: {e}"}, 502)
        if not geo:
            return self._json({"error": f"No Berlin address matched '{street} {hnr}, {plz}'."}, 404)

        lon, lat = geo["lon"], geo["lat"]
        esb_props, polygon, schools = INDEX.catchment(lon, lat)

        out_schools = []
        for s, c in schools:
            out_schools.append({
                "name": s["schulname"], "bsn": s["bsn"],
                "street": s.get("strasse", "").strip(),
                "hnr": s.get("hausnr", "").strip(),
                "plz": s.get("plz", ""),
                "phone": s.get("telefon"), "website": s.get("internet"),
                "sesb_strand": INDEX.sesb_strand(s["schulname"]),
                "school_year": s.get("schuljahr"),
                "lon": c[0], "lat": c[1],
            })

        intl = INDEX.nearest_intl(lon, lat)
        intl_out = None
        if intl:
            s = intl["school"]
            intl_out = {"name": s["schulname"], "bsn": s["bsn"],
                        "distance_m": intl["distance_m"],
                        "lat": intl["lat"], "lon": intl["lon"],
                        "website": s.get("internet")}

        kitas = kitas_near(lon, lat, 800)

        return self._json({
            "address": {"street": street, "hnr": hnr, "plz": plz,
                        "lon": lon, "lat": lat, "raw": geo["props"]},
            "catchment": {
                "esb": esb_props["esb"] if esb_props else None,
                "district": esb_props["bezname"] if esb_props else None,
                "polygon": mapping(polygon) if polygon is not None else None,
            },
            "schools": out_schools,
            "intl_grundschule": intl_out,
            "kitas": kitas,
            "provenance": {
                "catchment":  "Geoportal Berlin / Schulen (dl-de/zero-2.0)",
                "schools":    "Geoportal Berlin / Schulen (dl-de/zero-2.0)",
                "addresses":  "Geoportal Berlin / Adressen Berlin (dl-de/by-2.0)",
                "kitas_osm":  "© OpenStreetMap contributors (ODbL)",
            },
        })


# -- self-check (ponytail: one runnable check that fails if logic breaks) ----

def _selfcheck():
    idx = Index()
    geo = idx.geocode("Kastanienallee", "12", "10435")
    assert geo, "known Prenzlauer Berg address must geocode"
    props, poly, schools = idx.catchment(geo["lon"], geo["lat"])
    assert props and props["bezname"] == "Pankow"
    assert any("Senefelderplatz" in s["schulname"] for s, _ in schools)
    assert all(isinstance(c, list) and len(c) == 2 for _, c in schools), "schools carry [lon,lat]"
    intl = idx.nearest_intl(geo["lon"], geo["lat"])
    assert intl and intl["distance_m"] < 10_000
    assert idx.sesb_strand("Joan-Miró-Grundschule") == "German-Spanish"
    assert _classify_amenity({"amenity": "pharmacy"}) == "pharmacies"
    assert _classify_amenity({"public_transport": "platform"}) == "transit"
    assert _classify_amenity({"amenity": "restaurant"}) is None
    assert _summarize("transit", {"subway": "yes", "tram": "yes", "operator": "BVG"}) == "U-Bahn · Tram · BVG"
    assert _summarize("playgrounds", {"min_age": "3", "max_age": "12", "surface": "sand"}) == "Ages 3–12 · Surface: sand"
    assert _summarize("supermarkets", {}) == ""
    print("selfcheck: OK")


def main():
    global INDEX
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        return _selfcheck()
    INDEX = Index()
    socketserver.ThreadingTCPServer.allow_reuse_address = True  # ponytail: instant restart, no TIME_WAIT wait
    with socketserver.ThreadingTCPServer(("", PORT), H) as srv:
        print(f"→ http://localhost:{PORT}")
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            print("\nbye")


if __name__ == "__main__":
    main()
