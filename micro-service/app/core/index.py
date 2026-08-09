"""Preloaded per-city data index — catchments, schools, kitas, hospitals,
fountains. Verbatim behaviour port of phase3/server.py:Index, refactored in
Ship B to take a `CityConfig` so nothing Berlin-specific lives in `core/`.

Loaded once at boot (see app.main lifespan). Read-only after that — all methods
are pure lookups against in-memory shapely trees / lists. Only the address
geocode (`geocode()`) stays live-WFS.
"""
import json
import re
import sys
import unicodedata
import urllib.request

from shapely.geometry import Point, shape

from app.cities.base import CityConfig
from app.core.geo import haversine_m
from app.core.wfs import cql_esc, wfs


# ------------------------------------------------------------------ utilities

def norm(s: str) -> str:
    """Lower-case + strip diacritics (NFD, drop combining marks) + ß → ss."""
    s = s.lower().replace("ß", "ss")
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if not unicodedata.combining(c))


# ------------------------------------------------------------- info formatters

def _fountain_info(p, cfg: CityConfig):
    """One short line for a drinking fountain — flags out-of-service and season."""
    fm = cfg.fountains_field_map
    parts = []
    einschr = (p.get(fm["seasonal"]) or "").strip()
    if einschr:
        parts.append(f"⚠ {einschr}")
    bezirk = (p.get(fm["bezirk"]) or "").strip()
    if bezirk: parts.append(bezirk)
    ftype = (p.get(fm["type"]) or "").strip()
    if ftype:
        parts.append(f"Type: {ftype}")
    # ponytail: season is buried in a free-text 'informationen' field;
    # a regex extract keeps it out of the summary and in the tooltip.
    return " · ".join(parts)


def _hospital_info(p, cfg: CityConfig):
    """One short line from a hospital feature's properties. 'Plan' hospitals
    show bed count + Träger; specialist 'weitere' clinics show speciality."""
    fm = cfg.hospital_field_map
    parts = []
    if p.get("_layer") == "weitere":
        fach = (p.get(fm["fachabteilungen"]) or "").strip()
        if fach: parts.append(fach)
        if p.get(fm["beds_alt"]): parts.append(f"{p[fm['beds_alt']]} beds")
    else:
        beds = (p.get(fm["beds"]) or "").strip()
        if beds: parts.append(f"{beds} beds")
        traeger = (p.get(fm["traeger"]) or "").strip()
        if traeger and traeger != (p.get(fm["name_primary"]) or "").strip():
            parts.append(traeger)
    ort = (p.get(fm["ortsteil"]) or "").strip()
    if ort: parts.append(ort)
    return " · ".join(parts)


def _kita_info(p, cfg: CityConfig):
    """One short line from a BOD Kita feature's properties."""
    fm = cfg.kita_field_map
    parts = []
    cap = p.get(fm["capacity"])
    if cap:
        try:
            parts.append(f"{int(cap)} places")
        except (ValueError, TypeError): pass
    op_type = (p.get(fm["operator_type"]) or "").strip()
    if op_type:                     parts.append(op_type)       # e.g. "freie Träger", "Eigenbetrieb"
    ang = (p.get(fm["approach"]) or "").strip()
    if ang and ang != "":           parts.append(ang)
    return " · ".join(parts)


# ------------------------------------------------------------------ Index

class Index:
    def __init__(self, cfg: CityConfig):
        self.cfg = cfg

        sys.stdout.write("loading catchment polygons… "); sys.stdout.flush()
        esbs = wfs(cfg.catchment_wfs_url, typeNames=cfg.catchment_layer, count=1000,
                   outputFormat=cfg.wfs_output_format)
        self.esbs = [(f["properties"], shape(f["geometry"])) for f in esbs["features"]]
        print(f"{len(self.esbs)} polygons")

        sys.stdout.write("loading all schools… "); sys.stdout.flush()
        s_fm = cfg.schools_field_map
        s = wfs(cfg.schools_wfs_url, typeNames=cfg.schools_layer, count=2000,
                outputFormat=cfg.wfs_output_format)
        self.schools = [(f["properties"], f["geometry"]["coordinates"])
                        for f in s["features"] if f.get("geometry")]

        self.gs_public = [(p, c) for p, c in self.schools
                          if p.get(s_fm["type"]) == "Grundschule"
                          and p.get(s_fm["public_flag"]) == cfg.schools_public_value]
        self.gs_intl = [(p, c) for p, c in self.schools
                        if p.get(s_fm["type"]) in cfg.schools_primary_types
                        and any(k in norm(p[s_fm["name"]]) for k in cfg.schools_intl_keywords)]

        c_fm = cfg.catchment_field_map
        self.esb_to_gs = {}
        for props, geom in self.esbs:
            self.esb_to_gs[props[c_fm["id"]]] = [
                (p, c) for p, c in self.gs_public if geom.contains(Point(c))
            ]
        print(f"{len(self.gs_public)} public Grundschulen · {len(self.gs_intl)} intl/bilingual")

        sys.stdout.write(f"loading kitas ({cfg.display_name} geoportal)… "); sys.stdout.flush()
        k = wfs(cfg.kita_wfs_url, typeNames=cfg.kita_layer, count=5000,
                outputFormat=cfg.wfs_output_format)
        self.kitas = [(f["properties"], f["geometry"]["coordinates"])
                      for f in k["features"] if f.get("geometry")]
        print(f"{len(self.kitas)} registered Kitas")

        self.fountains = []
        if cfg.fountains_wfs_url and cfg.fountains_layer:
            sys.stdout.write("loading drinking fountains… "); sys.stdout.flush()
            # ~240 fountains city-wide in Berlin; preload once, distance-filter per request.
            r = wfs(cfg.fountains_wfs_url, typeNames=cfg.fountains_layer, count=1000,
                    outputFormat=cfg.wfs_output_format)
            self.fountains = [(f["properties"], f["geometry"]["coordinates"])
                              for f in r.get("features", []) if f.get("geometry")]
            print(f"{len(self.fountains)} fountains")

        self.hospitals = []
        if cfg.hospital_wfs_url and cfg.hospital_layers:
            sys.stdout.write(f"loading hospitals ({cfg.display_name} geoportal)… "); sys.stdout.flush()
            # Berlin publishes two layers: statutory "Plankrankenhäuser" and
            # specialist "weitere Krankenhäuser". Both are points, both tiny
            # (~110 total city-wide) — preload once.
            for layer, kind in cfg.hospital_layers:
                r = wfs(cfg.hospital_wfs_url, typeNames=layer, count=500,
                        outputFormat=cfg.wfs_output_format)
                for f in r.get("features", []):
                    if not f.get("geometry"): continue
                    p = dict(f["properties"]); p["_layer"] = kind
                    self.hospitals.append((p, f["geometry"]["coordinates"]))
            print(f"{len(self.hospitals)} hospitals")

        # -- Connectivity ---------------------------------------------------
        # S/U-Bahn from the vendored VBB CSV. "S+U" combined stations count
        # for BOTH lists so nearest-S and nearest-U give the closest station
        # of that mode, whether or not the interchange also has the other.
        self.sbahn, self.ubahn = [], []
        if cfg.stations_data_path:
            sys.stdout.write("loading S/U-Bahn stations (VBB vendored)… "); sys.stdout.flush()
            import csv as _csv
            with open(cfg.stations_data_path, encoding="utf-8", newline="") as f:
                for row in _csv.DictReader(f):
                    st = {"name": row["name"],
                          "lat": float(row["lat"]), "lon": float(row["lon"])}
                    m = row["mode"]
                    if m in ("S", "S+U"): self.sbahn.append(st)
                    if m in ("U", "S+U"): self.ubahn.append(st)
            print(f"{len(self.sbahn)} S-Bahn · {len(self.ubahn)} U-Bahn")

        # Tram from live BOD WFS.
        self.tram = []
        if cfg.tram_wfs_url and cfg.tram_layer:
            sys.stdout.write("loading tram stops… "); sys.stdout.flush()
            r = wfs(cfg.tram_wfs_url, typeNames=cfg.tram_layer, count=2000,
                    outputFormat=cfg.wfs_output_format)
            name_f = cfg.tram_field_map["name"]
            for f in r.get("features", []):
                g = f.get("geometry")
                if not g: continue
                # MultiPoint in Berlin's feed; take the first coord.
                c = g["coordinates"][0] if g["type"] == "MultiPoint" else g["coordinates"]
                self.tram.append({"name": (f["properties"].get(name_f) or "").strip(),
                                  "lat": c[1], "lon": c[0]})
            print(f"{len(self.tram)} tram stops")

        # Regional rail from config (curated list).
        self.regional_rail = [{"name": n, "lat": la, "lon": lo}
                              for n, la, lo in cfg.regional_rail_stations]

        # -- Phase 1: five killer datasets --------------------------------
        # All are small enough (39–102 features) to preload once; per-request
        # lookups are then in-memory. Baumbestand (~435k) stays per-request
        # bbox via trees_bbox() — not preloaded.

        # Fire stations + response zones. Two-layer load: zones (polygons)
        # + stations (points). Point-in-polygon at lookup returns the
        # regulatory-authoritative zone; nearest station is a straight
        # distance search over all stations (crossing a zone boundary is
        # fine — dispatch coordinates, not us).
        self.fire_stations, self.fire_zones = [], []
        if cfg.fire_wfs_url and cfg.fire_stations_layer:
            sys.stdout.write("loading fire stations + response zones… "); sys.stdout.flush()
            sfm = cfg.fire_stations_field_map
            r = wfs(cfg.fire_wfs_url, typeNames=cfg.fire_stations_layer, count=500,
                    outputFormat=cfg.wfs_output_format)
            for f in r.get("features", []):
                g = f.get("geometry")
                if not g: continue
                lo, la = g["coordinates"]
                p = f["properties"] or {}
                self.fire_stations.append({
                    "name":      p.get(sfm["name"]),
                    "type":      p.get(sfm["type"]),        # "BF" (professional) or "FF" (volunteer)
                    "address":   p.get(sfm["address"]),
                    "phone_bf":  p.get(sfm["phone_bf"]),
                    "phone_ff":  p.get(sfm["phone_ff"]),
                    "zone_code": p.get(sfm["zone_id"]),
                    "lat": la, "lon": lo,
                })
            zfm = cfg.fire_zones_field_map
            r = wfs(cfg.fire_wfs_url, typeNames=cfg.fire_zones_layer, count=50,
                    outputFormat=cfg.wfs_output_format)
            for f in r.get("features", []):
                if not f.get("geometry"): continue
                self.fire_zones.append((f["properties"], shape(f["geometry"])))
            print(f"{len(self.fire_stations)} stations · {len(self.fire_zones)} response zones")

        # Ruhige Gebiete (quiet zones + inner-city recreation).
        self.quiet_zones = []
        if cfg.quiet_wfs_url and cfg.quiet_layer:
            sys.stdout.write("loading quiet + recreation zones… "); sys.stdout.flush()
            r = wfs(cfg.quiet_wfs_url, typeNames=cfg.quiet_layer, count=200,
                    outputFormat=cfg.wfs_output_format)
            for f in r.get("features", []):
                if not f.get("geometry"): continue
                self.quiet_zones.append((f["properties"], shape(f["geometry"])))
            print(f"{len(self.quiet_zones)} zones")

        # Neighborhood protection (§ 172 BauGB): EM (Milieuschutz) + ES (character).
        self.protection_em, self.protection_es = [], []
        if cfg.protection_wfs_url and cfg.protection_em_layer:
            sys.stdout.write("loading neighborhood protection zones… "); sys.stdout.flush()
            for lyr, bucket in ((cfg.protection_em_layer, self.protection_em),
                                (cfg.protection_es_layer, self.protection_es)):
                r = wfs(cfg.protection_wfs_url, typeNames=lyr, count=500,
                        outputFormat=cfg.wfs_output_format)
                for f in r.get("features", []):
                    if not f.get("geometry"): continue
                    bucket.append((f["properties"], shape(f["geometry"])))
            print(f"{len(self.protection_em)} Milieuschutz (EM) · {len(self.protection_es)} character (ES)")

        # Swim spots — BBB pools + EU designated natural swim spots.
        self.pools, self.natural_swim = [], []
        if cfg.pools_wfs_url and cfg.pools_layer:
            sys.stdout.write("loading pools + natural swim spots… "); sys.stdout.flush()
            pfm = cfg.pools_field_map
            r = wfs(cfg.pools_wfs_url, typeNames=cfg.pools_layer, count=500,
                    outputFormat=cfg.wfs_output_format)
            for f in r.get("features", []):
                g = f.get("geometry")
                if not g: continue
                lo, la = g["coordinates"]
                p = f["properties"] or {}
                self.pools.append({
                    "name":       p.get(pfm["name"]),
                    "address":    p.get(pfm["address"]),
                    "postcode":   p.get(pfm["postcode"]),
                    "district":   p.get(pfm["district"]),
                    "category":   p.get(pfm["category"]),
                    "website":    p.get(pfm["website"]),
                    "hours_hint": p.get(pfm["hours_hint"]),
                    "lat": la, "lon": lo,
                })
            if cfg.swim_natural_wfs_url and cfg.swim_natural_layer:
                nfm = cfg.swim_natural_field_map
                r = wfs(cfg.swim_natural_wfs_url, typeNames=cfg.swim_natural_layer, count=500,
                        outputFormat=cfg.wfs_output_format)
                for f in r.get("features", []):
                    g = f.get("geometry")
                    if not g: continue
                    lo, la = g["coordinates"]
                    p = f["properties"] or {}
                    self.natural_swim.append({
                        "name":       p.get(nfm["name"]),
                        "eu_rating":  p.get(nfm["eu_rating"]),
                        "website":    p.get(nfm["website"]),
                        "cyano":      p.get(nfm["cyano"]),
                        "lat": la, "lon": lo,
                    })
            print(f"{len(self.pools)} pools · {len(self.natural_swim)} natural swim spots")

        # -- Spec B: Bureaucracy lens preloads -----------------------------
        # Bezirksgrenzen — 12 polygons, small (§14.6 preload rule).
        self.bezirksgrenzen = []
        if cfg.bezirksgrenzen_wfs_url and cfg.bezirksgrenzen_layer:
            sys.stdout.write("loading Bezirksgrenzen… "); sys.stdout.flush()
            r = wfs(cfg.bezirksgrenzen_wfs_url, typeNames=cfg.bezirksgrenzen_layer,
                    count=50, outputFormat=cfg.wfs_output_format)
            for f in r.get("features", []):
                if not f.get("geometry"): continue
                self.bezirksgrenzen.append((f["properties"], shape(f["geometry"])))
            print(f"{len(self.bezirksgrenzen)} Bezirke")

        # Bürgerämter — service.berlin.de GeoJSON (~50 unique locations city-wide);
        # sentinel layer "_geojson" triggers custom REST loader instead of WFS.
        self.buergeramts = []
        if cfg.buergeramt_wfs_url and cfg.buergeramt_layer:
            sys.stdout.write("loading Bürgerämter… "); sys.stdout.flush()
            bfm = cfg.buergeramt_field_map
            if cfg.buergeramt_layer == "_geojson":
                # service.berlin.de REST GeoJSON (no WFS available for this dataset)
                raw = json.loads(urllib.request.urlopen(
                    cfg.buergeramt_wfs_url, timeout=30).read())
                # response shape: {"buergeramt": {"data": {"features": [...]}}}
                features = (raw.get("buergeramt", {})
                               .get("data", {})
                               .get("features", []))
                seen_coords = set()
                for f in features:
                    g = f.get("geometry")
                    if not g: continue
                    coords = g.get("coordinates") or []
                    if len(coords) < 2: continue
                    try:
                        lo, la = float(coords[0]), float(coords[1])
                    except (ValueError, TypeError):
                        continue
                    # Deduplicate by coordinate: multiple service variants share one location
                    coord_key = (round(lo, 4), round(la, 4))
                    if coord_key in seen_coords:
                        continue
                    p = f.get("properties") or {}
                    name = (p.get("name") or "Bürgeramt").strip()
                    # Skip training / document-pickup / appointment-only sub-entries
                    skip_kw = ("ausbildung", "abholung", "vorzugstermin", "terminfreis",
                               "ausbildungsplatz", "mobiles")
                    if any(kw in name.lower() for kw in skip_kw):
                        continue
                    seen_coords.add(coord_key)
                    # Extract address from HTML description field
                    desc = p.get("description") or ""
                    addr_match = re.search(r"<p>(.*?)<br", desc, re.DOTALL)
                    address = re.sub("<[^>]+>", "", addr_match.group(1)).strip() if addr_match else ""
                    # Extract website URL from description
                    url_match = re.search(r'href="(https://service\.berlin\.de/standort/[^"]+)"', desc)
                    website = url_match.group(1) if url_match else ""
                    self.buergeramts.append({
                        "name": name,
                        "address": address,
                        "website": website,
                        "lat": la, "lon": lo,
                    })
            else:
                # Standard WFS path (for future cities that publish a WFS)
                r = wfs(cfg.buergeramt_wfs_url, typeNames=cfg.buergeramt_layer,
                        count=200, outputFormat=cfg.wfs_output_format)
                for f in r.get("features", []):
                    g = f.get("geometry")
                    if not g: continue
                    lo, la = g["coordinates"]
                    p = f["properties"] or {}
                    self.buergeramts.append({
                        "name":    (p.get(bfm["name"]) or "Bürgeramt").strip(),
                        "address": (p.get(bfm["address"]) or "").strip(),
                        "website": (p.get(bfm["website"]) or "").strip(),
                        "lat": la, "lon": lo,
                    })
            print(f"{len(self.buergeramts)} Bürgerämter")

    # -------------------------------------------------------------- lookups

    def geocode(self, street, hnr, plz):
        cfg = self.cfg
        gm = cfg.geocoder_field_map
        cql = (f"{gm['street']}='{cql_esc(street)}' AND "
               f"{gm['hnr']}='{cql_esc(hnr)}' AND "
               f"{gm['plz']}='{cql_esc(plz)}'")
        r = wfs(cfg.geocoder_wfs_url, typeNames=cfg.geocoder_layer,
                CQL_FILTER=cql, count=1, outputFormat=cfg.wfs_output_format)
        if not r.get("features"):
            return None
        lon, lat = r["features"][0]["geometry"]["coordinates"]
        return {"lon": lon, "lat": lat, "props": r["features"][0]["properties"]}

    def catchment(self, lon, lat):
        pt = Point(lon, lat)
        for props, geom in self.esbs:
            if geom.contains(pt):
                return props, geom, self.esb_to_gs.get(props[self.cfg.catchment_field_map["id"]], [])
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
        for key, strand in self.cfg.bilingual_schools.items():
            if key in low:
                return strand
        return None

    def fountains_near_bod(self, lon, lat, radius_m=800):
        """Public drinking fountains within radius. Seasonal: most run
        May–October only; the seasonal-restriction field flags out-of-service units."""
        loc_field = self.cfg.fountains_field_map["location"]
        hits = []
        for p, c in self.fountains:
            d = haversine_m(lon, lat, c[0], c[1])
            if d <= radius_m:
                loc = (p.get(loc_field) or "").strip() or "Trinkbrunnen"
                # Prepend "Trinkbrunnen" so list items scan the same as other categories.
                name = loc if loc.lower().startswith(("trinkbrunnen", "brunnen")) else f"Trinkbrunnen · {loc}"
                hits.append({
                    "name": name,
                    "lat": c[1], "lon": c[0], "distance_m": round(d),
                    "info": _fountain_info(p, self.cfg),
                    "props": p, "source": "bod",
                })
        hits.sort(key=lambda x: x["distance_m"])
        return hits

    def hospitals_near_bod(self, lon, lat, radius_m=None):
        """Hospitals within radius, from the configured Krankenhäuser layers.
        Filters preloaded points by haversine — no per-request WFS."""
        cfg = self.cfg
        if radius_m is None:
            radius_m = cfg.hospital_radius_m
        fm = cfg.hospital_field_map
        hits = []
        for p, c in self.hospitals:
            d = haversine_m(lon, lat, c[0], c[1])
            if d <= radius_m:
                name = ((p.get(fm["name_primary"]) or p.get(fm["name_alt1"])
                         or p.get(fm["name_alt2"]) or "Krankenhaus").strip())
                hits.append({
                    "name": name,
                    "lat": c[1], "lon": c[0], "distance_m": round(d),
                    "info": _hospital_info(p, cfg),
                    "props": p, "source": "bod",
                })
        hits.sort(key=lambda x: x["distance_m"])
        return hits

    def nearest_station(self, points, lon, lat):
        """Return the nearest {name, lat, lon} from `points` with distance_m
        added, or None if the list is empty. Used for every connectivity mode."""
        if not points:
            return None
        best = min(points, key=lambda p: haversine_m(lon, lat, p["lon"], p["lat"]))
        return {**best, "distance_m": round(haversine_m(lon, lat, best["lon"], best["lat"]))}

    # -- Phase 1 lookups (Fire, Quiet, Protection, Pools, Trees) -----------

    def fire_rescue(self, lon, lat):
        """Nearest fire station + which response zone (Einsatzbereich) covers
        this address. Response TIME is deliberately NOT computed — see UX-skill
        finding: distance is a raw open-data fact; response time is inference
        we can't underwrite with real dispatch data."""
        if not self.fire_stations:
            return None
        nearest = min(self.fire_stations,
                      key=lambda s: haversine_m(lon, lat, s["lon"], s["lat"]))
        d = round(haversine_m(lon, lat, nearest["lon"], nearest["lat"]))
        zone_name = None; zone_code = None
        pt = Point(lon, lat)
        zfm = self.cfg.fire_zones_field_map
        for props, geom in self.fire_zones:
            if geom.contains(pt):
                zone_name = props.get(zfm["name"])
                zone_code = props.get(zfm["code"])
                break
        # Also collect the three nearest for the modal list.
        top3 = sorted(self.fire_stations,
                      key=lambda s: haversine_m(lon, lat, s["lon"], s["lat"]))[:3]
        top3 = [{**s, "distance_m": round(haversine_m(lon, lat, s["lon"], s["lat"]))}
                for s in top3]
        return {
            "nearest": {**nearest, "distance_m": d},
            "zone_name": zone_name, "zone_code": zone_code,
            "top3": top3,
        }

    def neighborhood_protection(self, lon, lat):
        """Point-in-polygon check on §172 BauGB layers. Two overlapping status
        badges (Milieuschutz + character preservation)."""
        pfm = self.cfg.protection_field_map
        pt = Point(lon, lat)
        def _hit(bucket):
            for props, geom in bucket:
                if geom.contains(pt):
                    return {
                        "inside":    True,
                        "area_name": props.get(pfm["name"]),
                        "code":      props.get(pfm["code"]),
                        "in_force":  props.get(pfm["in_force"]),
                        "district":  props.get(pfm["district"]),
                        # `es` layer uses fl_in_ha; fall back if the primary key is missing.
                        "size_ha":   props.get(pfm["size_ha"]) or props.get("fl_in_ha"),
                    }
            return {"inside": False}
        return {"milieuschutz": _hit(self.protection_em),
                "heritage":     _hit(self.protection_es)}

    def nearest_quiet_zone(self, lon, lat):
        """Nearest official quiet-recreation zone by shapely-distance to the
        polygon edge (in degrees, then convert to metres via haversine on the
        nearest boundary point). Cheaper than reprojecting for the ~50 polygons."""
        if not self.quiet_zones:
            return None
        pt = Point(lon, lat)
        qfm = self.cfg.quiet_field_map
        best_props, best_geom, best_d = None, None, float("inf")
        for props, geom in self.quiet_zones:
            # Point-in-polygon fast-path — distance 0 wins.
            if geom.contains(pt):
                nearest_pt_on_edge = pt
                d = 0.0
            else:
                # Nearest point on the polygon boundary.
                nearest_pt_on_edge = geom.boundary.interpolate(geom.boundary.project(pt))
                d = haversine_m(lon, lat, nearest_pt_on_edge.x, nearest_pt_on_edge.y)
            if d < best_d:
                best_props, best_geom, best_d = props, geom, d
        if best_props is None: return None
        c = best_geom.centroid
        return {
            "name":       (best_props.get(qfm["name"]) or "").strip(),
            "kind":       best_props.get(qfm["kind"]),
            "size_ha":    best_props.get(qfm["size_ha"]),
            "distance_m": round(best_d),
            "lat": c.y, "lon": c.x,
            "inside":     best_d < 1.0,
        }

    def pools_within(self, lon, lat, radius_m=3000):
        """BBB pools within radius, sorted by distance. Kept generous (~3 km)
        because families reasonably travel to pools they don't have in walking
        distance. Strandbäder (open-water beach baths) are registered in BOTH
        the BBB pool dataset AND the EU natural-swim dataset — we merge the
        EU water-quality rating onto the pool entry so a user sees one item
        with all the info, not two visually-identical rows."""
        natural_by_name = {n["name"]: n for n in self.natural_swim if n.get("name")}
        hits = []
        for p in self.pools:
            d = haversine_m(lon, lat, p["lon"], p["lat"])
            if d <= radius_m:
                entry = {**p, "distance_m": round(d)}
                match = natural_by_name.get(p.get("name"))
                if match:
                    entry["eu_rating"] = match.get("eu_rating")
                    entry["natural_link"] = match.get("website")
                hits.append(entry)
        hits.sort(key=lambda x: x["distance_m"])
        return hits

    def natural_swim_within(self, lon, lat, radius_m=15000):
        """EU-designated natural swim spots (lakes/canals). Skips any spot
        whose name also appears in the pool list — those Strandbäder are
        already covered by pools_within() with the EU rating merged in."""
        pool_names = {p["name"] for p in self.pools if p.get("name")}
        hits = []
        for p in self.natural_swim:
            if p.get("name") in pool_names:
                continue                                # dedupe with pools list
            d = haversine_m(lon, lat, p["lon"], p["lat"])
            if d <= radius_m:
                hits.append({**p, "distance_m": round(d)})
        hits.sort(key=lambda x: x["distance_m"])
        return hits

    def trees_bbox(self, lon, lat, radius_m=None):
        """Baumbestand — 435 k records city-wide, too big to preload. Live bbox
        WFS query around the address, then summarise: count, average age,
        tallest, top species. No caller sees individual trees; only aggregates."""
        cfg = self.cfg
        if not (cfg.trees_wfs_url and cfg.trees_layer):
            return None
        if radius_m is None:
            radius_m = cfg.trees_radius_m
        from app.core.geo import bbox_around
        minx, miny, maxx, maxy = bbox_around(lon, lat, radius_m)
        tfm = cfg.trees_field_map
        try:
            d = wfs(cfg.trees_wfs_url, typeNames=cfg.trees_layer, count=2000,
                    bbox=f"{minx},{miny},{maxx},{maxy},EPSG:4326",
                    outputFormat=cfg.wfs_output_format)
        except Exception as e:
            return {"error": str(e)[:200]}
        feats = d.get("features") or []
        # Second pass: filter to the actual radius (bbox is looser).
        kept = []
        for f in feats:
            g = f.get("geometry")
            if not g: continue
            lo, la = g["coordinates"]
            if haversine_m(lon, lat, lo, la) <= radius_m:
                kept.append(f["properties"] or {})
        if not kept:
            return {"count": 0, "radius_m": radius_m}
        heights = [p.get(tfm["height"]) for p in kept if p.get(tfm["height"]) not in (None, "")]
        heights = [float(h) for h in heights]
        ages = [p.get(tfm["age"]) for p in kept if p.get(tfm["age"]) not in (None, "")]
        ages = [int(a) for a in ages]
        planting_years = [p.get(tfm["planting_year"]) for p in kept if p.get(tfm["planting_year"]) not in (None, "")]
        planting_years = [int(y) for y in planting_years]
        species_counts = {}
        genera = set()
        group_counts = {}
        for p in kept:
            sp = (p.get(tfm["species_de"]) or "").strip()
            if sp:
                species_counts[sp] = species_counts.get(sp, 0) + 1
            g = (p.get(tfm["genus_de"]) or "").strip()
            if g:
                genera.add(g)
            gr = (p.get(tfm["group"]) or "").strip()
            if gr:
                group_counts[gr] = group_counts.get(gr, 0) + 1
        top_species = sorted(species_counts.items(), key=lambda x: -x[1])[:5]
        age_bands = {"young": 0, "mature": 0, "old": 0}
        for a in ages:
            if a < 20:    age_bands["young"] += 1
            elif a < 60:  age_bands["mature"] += 1
            else:         age_bands["old"] += 1
        # Crown coverage: sum of individual crown-disk areas (π·(d/2)²) as a
        # rough shade proxy; expressed as m² since the query area itself is a
        # circle of area π·radius². "% of query area" = coverage / query_area.
        crowns = [p.get("kronedurch") for p in kept if p.get("kronedurch") not in (None, "")]
        crowns = [float(c) for c in crowns]
        crown_area_m2 = round(sum(3.14159 * (c/2)**2 for c in crowns))
        query_area_m2 = round(3.14159 * radius_m**2)
        return {
            "count":            len(kept),
            "radius_m":         radius_m,
            "avg_age_yr":       round(sum(ages) / len(ages)) if ages else None,
            "tallest_m":        round(max(heights), 1) if heights else None,
            "avg_height_m":     round(sum(heights) / len(heights), 1) if heights else None,
            "top_species":      [{"name": n, "n": c} for n, c in top_species],
            "unique_species":   len(species_counts),
            "unique_genera":    len(genera),
            "age_bands":        age_bands,
            "group_mix":        group_counts,        # "Laubbäume" (deciduous) vs "Nadelbäume" (conifer)
            "planting_range":   [min(planting_years), max(planting_years)] if planting_years else None,
            "crown_coverage_m2": crown_area_m2,
            "crown_coverage_pct": round(100 * crown_area_m2 / query_area_m2, 1) if query_area_m2 else None,
        }

    def kitas_near_bod(self, lon, lat, radius_m=800):
        """Registered Kitas within radius. Filters preloaded points by
        haversine — no per-request WFS call."""
        name_field = self.cfg.kita_field_map["name"]
        hits = []
        for p, c in self.kitas:
            d = haversine_m(lon, lat, c[0], c[1])
            if d <= radius_m:
                hits.append({
                    "name": (p.get(name_field) or "Kita").strip(),
                    "lat": c[1], "lon": c[0], "distance_m": round(d),
                    "info": _kita_info(p, self.cfg),
                    "props": p, "source": "bod",
                })
        hits.sort(key=lambda x: x["distance_m"])
        return hits

    # -- Spec B lookups ---------------------------------------------------

    def bezirk_for(self, lon, lat):
        """Point-in-polygon over 12 Bezirksgrenzen. Returns Bezirk name or None
        for addresses outside Berlin's official Bezirke."""
        fm = self.cfg.bezirksgrenzen_field_map
        pt = Point(lon, lat)
        for props, geom in self.bezirksgrenzen:
            if geom.contains(pt):
                return (props.get(fm["name"]) or "").strip() or None
        return None

    def buergeramt_near(self, lon, lat, radius_m=3000):
        """All Bürgerämter within radius, sorted ascending by distance.
        Each returned dict has `distance_m` added."""
        hits = []
        for o in self.buergeramts:
            d = haversine_m(lon, lat, o["lon"], o["lat"])
            if d <= radius_m:
                hits.append({**o, "distance_m": round(d)})
        hits.sort(key=lambda x: x["distance_m"])
        return hits

    def arbeitsagentur_near(self, lon, lat, radius_m=5000):
        """All curated Arbeitsagentur branches within radius, sorted asc."""
        hits = []
        for o in self.cfg.arbeitsagenturs:
            d = haversine_m(lon, lat, o["lon"], o["lat"])
            if d <= radius_m:
                hits.append({**o, "distance_m": round(d)})
        hits.sort(key=lambda x: x["distance_m"])
        return hits

    def finanzamt_nearest(self, lon, lat):
        """Nearest Finanzamt from the curated list. Returns None if the list
        is empty (config bug)."""
        if not self.cfg.finanzamts:
            return None
        best = min(self.cfg.finanzamts,
                   key=lambda o: haversine_m(lon, lat, o["lon"], o["lat"]))
        d = haversine_m(lon, lat, best["lon"], best["lat"])
        return {**best, "distance_m": round(d)}

    def standesamt_for(self, lon, lat):
        """Address's Bezirk → its assigned Standesamt. Point-in-polygon
        lookup + directory read. Returns None if bezirk_for() returns None
        (address outside Berlin) or if the Bezirk isn't in the dict."""
        bezirk = self.bezirk_for(lon, lat)
        if not bezirk:
            return None
        office = self.cfg.standesamts_by_bezirk.get(bezirk)
        if not office:
            return None
        d = haversine_m(lon, lat, office["lon"], office["lat"])
        return {**office, "distance_m": round(d)}


if __name__ == "__main__":
    # Pure-only asserts (network Index construction is exercised in the live
    # selfcheck). Formatter asserts copied verbatim from phase3/server.py:_selfcheck,
    # now parameterised on Berlin's CityConfig.
    from app.cities.berlin import BERLIN as _CFG

    assert "65 places" in _kita_info(
        {"e_platz": "65", "t_art": "freie Träger", "ang_1": ""}, _CFG)

    plan = _hospital_info({"_layer": "plan", "betten_insgesamt": "415",
                           "kkh": "Alexianer", "kkh_standort": "St. Hedwig",
                           "gc_ortsteil": "Mitte"}, _CFG)
    assert "415 beds" in plan and "Mitte" in plan and "Alexianer" in plan
    weit = _hospital_info({"_layer": "weitere", "fachabteilungen": "Augenheilkunde",
                           "betten": 4, "gc_ortsteil": "Schöneberg"}, _CFG)
    assert "Augenheilkunde" in weit and "4 beds" in weit

    off = _fountain_info({"einschraenkungen": "zur Zeit wegen Reparatur außer Betrieb",
                          "bezirk": "Mitte", "trinkbrunnenart": "Kaiser"}, _CFG)
    assert "⚠" in off and "Reparatur" in off
    ok = _fountain_info({"einschraenkungen": None, "bezirk": "Mitte",
                         "trinkbrunnenart": "Kaiser"}, _CFG)
    assert "⚠" not in ok and "Mitte" in ok and "Kaiser" in ok

    # norm() drops diacritics + folds ß → ss.
    assert norm("Straße") == "strasse"
    assert norm("Schöneberg") == "schoneberg"
    print("index.py selfcheck OK (pure asserts only; live Index load in app.selfcheck)")
