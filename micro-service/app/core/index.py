"""Preloaded per-city data index — catchments, schools, kitas, hospitals,
fountains. Verbatim behaviour port of phase3/server.py:Index, refactored in
Ship B to take a `CityConfig` so nothing Berlin-specific lives in `core/`.

Loaded once at boot (see app.main lifespan). Read-only after that — all methods
are pure lookups against in-memory shapely trees / lists. Only the address
geocode (`geocode()`) stays live-WFS.
"""
import sys
import unicodedata

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
        esbs = wfs(cfg.catchment_wfs_url, typeNames=cfg.catchment_layer, count=1000)
        self.esbs = [(f["properties"], shape(f["geometry"])) for f in esbs["features"]]
        print(f"{len(self.esbs)} polygons")

        sys.stdout.write("loading all schools… "); sys.stdout.flush()
        s_fm = cfg.schools_field_map
        s = wfs(cfg.schools_wfs_url, typeNames=cfg.schools_layer, count=2000)
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
        k = wfs(cfg.kita_wfs_url, typeNames=cfg.kita_layer, count=5000)
        self.kitas = [(f["properties"], f["geometry"]["coordinates"])
                      for f in k["features"] if f.get("geometry")]
        print(f"{len(self.kitas)} registered Kitas")

        self.fountains = []
        if cfg.fountains_wfs_url and cfg.fountains_layer:
            sys.stdout.write("loading drinking fountains… "); sys.stdout.flush()
            # ~240 fountains city-wide in Berlin; preload once, distance-filter per request.
            r = wfs(cfg.fountains_wfs_url, typeNames=cfg.fountains_layer, count=1000)
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
                r = wfs(cfg.hospital_wfs_url, typeNames=layer, count=500)
                for f in r.get("features", []):
                    if not f.get("geometry"): continue
                    p = dict(f["properties"]); p["_layer"] = kind
                    self.hospitals.append((p, f["geometry"]["coordinates"]))
            print(f"{len(self.hospitals)} hospitals")

    # -------------------------------------------------------------- lookups

    def geocode(self, street, hnr, plz):
        cfg = self.cfg
        gm = cfg.geocoder_field_map
        cql = (f"{gm['street']}='{cql_esc(street)}' AND "
               f"{gm['hnr']}='{cql_esc(hnr)}' AND "
               f"{gm['plz']}='{cql_esc(plz)}'")
        r = wfs(cfg.geocoder_wfs_url, typeNames=cfg.geocoder_layer,
                CQL_FILTER=cql, count=1)
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
