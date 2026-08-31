"""Preloaded per-city data index — catchments, schools, kitas, hospitals,
fountains, connectivity, and Phase-1 killer datasets. Verbatim behaviour
port of phase3/server.py:Index, refactored in Ship B to take a
`CityConfig`.

Loaded once at boot (see app.main lifespan). Read-only after that — all
methods are pure lookups against in-memory shapely trees / lists. Only
the address geocode (`geocode()`) stays live-WFS.

Ship D step: `Index.__init__` (was 324 lines of blocking IO with 8+
near-identical polygon/point loops) is split into per-dataset private
`_load_*` methods. Boot order is preserved verbatim so `python -m
app.selfcheck`'s live phase produces the same stdout timeline. Two
shared helpers pulled out to `app.core.loaders.wfs_layer` cover the
polygon `(props, geom)` and point `(props, coords)` shapes; the
service.berlin.de Bürgeramt REST/HTML block moved out to its own
module (`loaders.buergeramt_service_portal`).
"""
import unicodedata

from shapely.geometry import Point
from shapely.strtree import STRtree

from app.cities.base import CityConfig
from app.core.geo import haversine_m
from app.core.loaders.wfs_layer import (
    load_point_layer_raw, load_polygon_layer, log_load,
)
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
    """Boot-loaded per-city data index. `__init__` runs a fixed sequence
    of private `_load_*` methods; every attribute assigned below is
    read-only after construction."""

    def __init__(self, cfg: CityConfig):
        self.cfg = cfg
        # Load order mirrors the pre-split monolith so the boot-time
        # stdout timeline is unchanged. Each `_load_*` writes its own
        # "loading X… N items" line via `log_load`.
        self._load_osm_snapshot()
        self._load_address_index()
        self._load_catchments_and_schools()
        self._load_kitas()
        self._load_fountains()
        self._load_hospitals()
        self._load_su_bahn()
        self._load_tram()
        self._load_regional_rail()
        self._load_fire()
        self._load_quiet_zones()
        self._load_protection()
        self._load_swim()
        self._load_bezirksgrenzen()
        self._load_gesix()
        self._load_buergeramts()
        self._load_tempolimits()
        self._load_arterial_roads()

    # ---- Loaders (called once, in order, from __init__) -----------------

    def _load_osm_snapshot(self) -> None:
        """Geofabrik weekly OSM snapshot — v0.1 addition. None if the
        file is missing / unreadable; callers fall back to Overpass."""
        from app.core.osm_local import load_osm_local
        self.osm_local = load_osm_local(getattr(self.cfg, "osm_local_path", None))

    def _load_address_index(self) -> None:
        """Address prefix index for /api/suggest. Same weekly snapshot
        cycle as osm_local. None if the file is missing → suggest
        returns [] gracefully; the app still functions."""
        from app.core.address_index import load_address_index
        log_load("address suggest index")
        self.address_index = load_address_index(
            getattr(self.cfg, "address_local_path", None))
        if self.address_index is None:
            print("not loaded (file missing — /api/suggest returns empty)")
        else:
            print(f"{len(self.address_index)} addresses")

    def _load_catchments_and_schools(self) -> None:
        """Catchment polygons + all schools + derived public / intl lists
        + esb→schools point-in-polygon index."""
        cfg = self.cfg
        log_load("catchment polygons")
        self.esbs = load_polygon_layer(
            cfg, cfg.catchment_wfs_url, cfg.catchment_layer, 1000)
        print(f"{len(self.esbs)} polygons")

        log_load("all schools")
        s_fm = cfg.schools_field_map
        self.schools = load_point_layer_raw(
            cfg, cfg.schools_wfs_url, cfg.schools_layer, 2000)

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
        print(f"{len(self.gs_public)} public Grundschulen · "
              f"{len(self.gs_intl)} intl/bilingual")

    def _load_kitas(self) -> None:
        cfg = self.cfg
        log_load(f"kitas ({cfg.display_name} geoportal)")
        self.kitas = load_point_layer_raw(
            cfg, cfg.kita_wfs_url, cfg.kita_layer, 5000)
        print(f"{len(self.kitas)} registered Kitas")

    def _load_fountains(self) -> None:
        """~240 fountains city-wide in Berlin; preload once,
        distance-filter per request."""
        cfg = self.cfg
        self.fountains = []
        if not (cfg.fountains_wfs_url and cfg.fountains_layer):
            return
        log_load("drinking fountains")
        self.fountains = load_point_layer_raw(
            cfg, cfg.fountains_wfs_url, cfg.fountains_layer, 1000)
        print(f"{len(self.fountains)} fountains")

    def _load_hospitals(self) -> None:
        """Berlin publishes two layers: statutory "Plankrankenhäuser" and
        specialist "weitere Krankenhäuser". Both are points, both tiny
        (~110 total city-wide) — preload once. The `_layer` kind tag on
        each props dict is used later by `_hospital_info` to pick the
        right rendering (beds vs. speciality)."""
        cfg = self.cfg
        self.hospitals = []
        if not (cfg.hospital_wfs_url and cfg.hospital_layers):
            return
        log_load(f"hospitals ({cfg.display_name} geoportal)")
        for layer, kind in cfg.hospital_layers:
            for props, coords in load_point_layer_raw(
                    cfg, cfg.hospital_wfs_url, layer, 500):
                p = dict(props)
                p["_layer"] = kind
                self.hospitals.append((p, coords))
        print(f"{len(self.hospitals)} hospitals")

    def _load_su_bahn(self) -> None:
        """S/U-Bahn from the vendored VBB CSV. "S+U" combined stations
        count for BOTH lists so nearest-S and nearest-U give the closest
        station of that mode, whether or not the interchange also has
        the other."""
        cfg = self.cfg
        self.sbahn, self.ubahn = [], []
        if not cfg.stations_data_path:
            return
        log_load("S/U-Bahn stations (VBB vendored)")
        import csv as _csv
        with open(cfg.stations_data_path, encoding="utf-8", newline="") as f:
            for row in _csv.DictReader(f):
                st = {"name": row["name"],
                      "lat": float(row["lat"]), "lon": float(row["lon"])}
                m = row["mode"]
                if m in ("S", "S+U"): self.sbahn.append(st)
                if m in ("U", "S+U"): self.ubahn.append(st)
        print(f"{len(self.sbahn)} S-Bahn · {len(self.ubahn)} U-Bahn")

    def _load_tram(self) -> None:
        """Tram from live BOD WFS. Berlin's feed uses MultiPoint one-per-
        stop; the shared point loader takes the first coord."""
        cfg = self.cfg
        self.tram = []
        if not (cfg.tram_wfs_url and cfg.tram_layer):
            return
        log_load("tram stops")
        name_f = cfg.tram_field_map["name"]
        for props, coords in load_point_layer_raw(
                cfg, cfg.tram_wfs_url, cfg.tram_layer, 2000):
            self.tram.append({
                "name": (props.get(name_f) or "").strip(),
                "lat": coords[1], "lon": coords[0],
            })
        print(f"{len(self.tram)} tram stops")

    def _load_regional_rail(self) -> None:
        """Regional rail from config (curated list — no WFS call)."""
        self.regional_rail = [
            {"name": n, "lat": la, "lon": lo}
            for n, la, lo in self.cfg.regional_rail_stations
        ]

    def _load_fire(self) -> None:
        """Fire stations + response zones. Two-layer load: zones
        (polygons) + stations (points). Point-in-polygon at lookup
        returns the regulatory-authoritative zone; nearest station is a
        straight distance search over all stations (crossing a zone
        boundary is fine — dispatch coordinates, not us)."""
        cfg = self.cfg
        self.fire_stations, self.fire_zones = [], []
        if not (cfg.fire_wfs_url and cfg.fire_stations_layer):
            return
        log_load("fire stations + response zones")
        sfm = cfg.fire_stations_field_map
        for props, coords in load_point_layer_raw(
                cfg, cfg.fire_wfs_url, cfg.fire_stations_layer, 500):
            lo, la = coords
            self.fire_stations.append({
                "name":      props.get(sfm["name"]),
                "type":      props.get(sfm["type"]),        # "BF" or "FF"
                "address":   props.get(sfm["address"]),
                "phone_bf":  props.get(sfm["phone_bf"]),
                "phone_ff":  props.get(sfm["phone_ff"]),
                "zone_code": props.get(sfm["zone_id"]),
                "lat": la, "lon": lo,
            })
        self.fire_zones = load_polygon_layer(
            cfg, cfg.fire_wfs_url, cfg.fire_zones_layer, 50)
        print(f"{len(self.fire_stations)} stations · "
              f"{len(self.fire_zones)} response zones")

    def _load_quiet_zones(self) -> None:
        cfg = self.cfg
        self.quiet_zones = []
        if not (cfg.quiet_wfs_url and cfg.quiet_layer):
            return
        log_load("quiet + recreation zones")
        self.quiet_zones = load_polygon_layer(
            cfg, cfg.quiet_wfs_url, cfg.quiet_layer, 200)
        print(f"{len(self.quiet_zones)} zones")

    def _load_protection(self) -> None:
        """Neighborhood protection (§ 172 BauGB): EM (Milieuschutz) + ES
        (character preservation)."""
        cfg = self.cfg
        self.protection_em, self.protection_es = [], []
        if not (cfg.protection_wfs_url and cfg.protection_em_layer):
            return
        log_load("neighborhood protection zones")
        self.protection_em = load_polygon_layer(
            cfg, cfg.protection_wfs_url, cfg.protection_em_layer, 500)
        self.protection_es = load_polygon_layer(
            cfg, cfg.protection_wfs_url, cfg.protection_es_layer, 500)
        print(f"{len(self.protection_em)} Milieuschutz (EM) · "
              f"{len(self.protection_es)} character (ES)")

    def _load_swim(self) -> None:
        """BBB pools + EU designated natural swim spots. Two-layer load;
        the natural-swim layer is optional per city."""
        cfg = self.cfg
        self.pools, self.natural_swim = [], []
        if not (cfg.pools_wfs_url and cfg.pools_layer):
            return
        log_load("pools + natural swim spots")
        pfm = cfg.pools_field_map
        for props, coords in load_point_layer_raw(
                cfg, cfg.pools_wfs_url, cfg.pools_layer, 500):
            lo, la = coords
            self.pools.append({
                "name":       props.get(pfm["name"]),
                "address":    props.get(pfm["address"]),
                "postcode":   props.get(pfm["postcode"]),
                "district":   props.get(pfm["district"]),
                "category":   props.get(pfm["category"]),
                "website":    props.get(pfm["website"]),
                "hours_hint": props.get(pfm["hours_hint"]),
                "lat": la, "lon": lo,
            })
        if cfg.swim_natural_wfs_url and cfg.swim_natural_layer:
            nfm = cfg.swim_natural_field_map
            for props, coords in load_point_layer_raw(
                    cfg, cfg.swim_natural_wfs_url, cfg.swim_natural_layer, 500):
                lo, la = coords
                self.natural_swim.append({
                    "name":       props.get(nfm["name"]),
                    "eu_rating":  props.get(nfm["eu_rating"]),
                    "website":    props.get(nfm["website"]),
                    "cyano":      props.get(nfm["cyano"]),
                    "lat": la, "lon": lo,
                })
        print(f"{len(self.pools)} pools · "
              f"{len(self.natural_swim)} natural swim spots")

    def _load_bezirksgrenzen(self) -> None:
        """12 polygons for point-in-polygon Bezirk assignment.
        Small (§14.6 preload rule)."""
        cfg = self.cfg
        self.bezirksgrenzen = []
        if not (cfg.bezirksgrenzen_wfs_url and cfg.bezirksgrenzen_layer):
            return
        log_load("Bezirksgrenzen")
        self.bezirksgrenzen = load_polygon_layer(
            cfg, cfg.bezirksgrenzen_wfs_url, cfg.bezirksgrenzen_layer, 50)
        print(f"{len(self.bezirksgrenzen)} Bezirke")

    def _load_gesix(self) -> None:
        """447 Planungsraum polygons + composite index (Berlin Senate
        GESIx 2022). Point-in-polygon per lookup — no per-request WFS
        call. Fails soft: absent config or WFS timeout → gesix stays
        empty and lookups return None (Young Family lens tile becomes
        tier=unknown, doesn't break /api/lookup)."""
        cfg = self.cfg
        self.gesix = []
        self._gesix_wert_sorted = []
        if not (getattr(cfg, "gesix_wfs_url", None)
                and getattr(cfg, "gesix_layer", None)):
            return
        log_load("GESIx (health + social index)")
        try:
            for props, geom in load_polygon_layer(
                    cfg, cfg.gesix_wfs_url, cfg.gesix_layer, 1000):
                if props.get("gesix_wert") is None:
                    continue                # planungsräume with no valid data
                self.gesix.append((props, geom))
            self._gesix_wert_sorted = sorted(
                p.get("gesix_wert") for p, _ in self.gesix
                if p.get("gesix_wert") is not None)
            print(f"{len(self.gesix)} Planungsräume")
        except Exception as e:
            print(f"failed ({type(e).__name__}: {e})")

    def _load_buergeramts(self) -> None:
        """Bürgerämter. Sentinel layer "_geojson" triggers the
        service.berlin.de REST/HTML loader (module
        `loaders.buergeramt_service_portal`); anything else falls through
        to the standard WFS point path."""
        cfg = self.cfg
        self.buergeramts = []
        if not (cfg.buergeramt_wfs_url and cfg.buergeramt_layer):
            return
        log_load("Bürgerämter")
        if cfg.buergeramt_layer == "_geojson":
            from app.core.loaders.buergeramt_service_portal import load as _load_bp
            self.buergeramts = _load_bp(cfg)
        else:
            bfm = cfg.buergeramt_field_map
            for props, coords in load_point_layer_raw(
                    cfg, cfg.buergeramt_wfs_url, cfg.buergeramt_layer, 200):
                lo, la = coords
                self.buergeramts.append({
                    "name":    (props.get(bfm["name"]) or "Bürgeramt").strip(),
                    "address": (props.get(bfm["address"]) or "").strip(),
                    "website": (props.get(bfm["website"]) or "").strip(),
                    "lat": la, "lon": lo,
                })
        print(f"{len(self.buergeramts)} Bürgerämter")

    def _load_tempolimits(self) -> None:
        """Berlin Tempolimits — road segments with speed exceptions to the
        general 50 km/h (Tempo-30 zones, 40, 60, Autobahn limits).

        ~30k features, small enough to preload. Stored as
        `[(props, shapely.MultiLineString), …]` plus an STRtree over the
        geometries for O(log n) nearest-segment lookup.
        """
        cfg = self.cfg
        self.tempolimits = []
        self._tempolimits_tree: STRtree | None = None
        if not (cfg.tempolimits_wfs_url and cfg.tempolimits_layer):
            return
        log_load("Tempolimits (speed exceptions)")
        # `count=100000` — headroom over the ~30k current segment count
        # so a future feed-side growth spurt doesn't silently drop
        # segments from the STRtree.
        self.tempolimits = load_polygon_layer(
            cfg, cfg.tempolimits_wfs_url, cfg.tempolimits_layer, 100000)
        if self.tempolimits:
            self._tempolimits_tree = STRtree([g for _, g in self.tempolimits])
        print(f"{len(self.tempolimits)} speed-exception segments")

    def _load_arterial_roads(self) -> None:
        """Übergeordnetes Straßennetz — LineString centrelines of the
        arterial + supra-local road network. Any address's distance to
        the nearest feature = exposure to primary traffic noise.
        Preloaded (~15-25k features) with an STRtree over the geometries."""
        cfg = self.cfg
        self.arterial_roads = []
        self._arterial_tree: STRtree | None = None
        if not (cfg.arterial_wfs_url and cfg.arterial_layer):
            return
        log_load("arterial road network")
        # `count=100000` — headroom over the current segment count.
        self.arterial_roads = load_polygon_layer(
            cfg, cfg.arterial_wfs_url, cfg.arterial_layer, 100000)
        if self.arterial_roads:
            self._arterial_tree = STRtree([g for _, g in self.arterial_roads])
        print(f"{len(self.arterial_roads)} arterial segments")

    # -------------------------------------------------------------- lookups

    def geocode(self, street, hnr, plz):
        """Look up an address via the city's WFS geocoder. Tolerates:
          - 'strasse' ↔ 'straße' spelling (retry with opposite fold);
          - letter suffix on hnr ('44A', '5c') — Berlin BOD stores the
            digits in `hnr` (integer) and the letter in `hnr_zusatz`;
            with a suffix we split + query both fields, else int compare
            against the raw digits works as string in CQL."""
        import re
        cfg = self.cfg
        gm = cfg.geocoder_field_map
        m = re.match(r"^(\d+)([A-Za-z]?)$", (hnr or "").strip())
        hnr_num, hnr_letter = (m.group(1), m.group(2).upper()) if m else (hnr, "")

        def _try(street_v):
            cql = (f"{gm['street']}='{cql_esc(street_v)}' AND "
                   f"{gm['hnr']}={cql_esc(hnr_num)} AND "
                   f"{gm['plz']}='{cql_esc(plz)}'")
            if hnr_letter:
                cql += f" AND {gm.get('hnr_zusatz','hnr_zusatz')}='{cql_esc(hnr_letter)}'"
            r = wfs(cfg.geocoder_wfs_url, typeNames=cfg.geocoder_layer,
                    CQL_FILTER=cql, count=1, outputFormat=cfg.wfs_output_format)
            return r.get("features") or []

        feats = _try(street)
        if not feats:
            # ß ↔ ss fold — Berlin BOD stores 'Sybelstraße' but many users
            # (expats especially) type 'Sybelstrasse'. Retry with the opposite
            # spelling. Symmetric: applies both directions.
            alt = None
            if "strasse" in street.lower():
                alt = street.replace("strasse", "straße").replace("Strasse", "Straße")
            elif "straße" in street.lower():
                alt = street.replace("straße", "strasse").replace("Straße", "Strasse")
            if alt and alt != street:
                feats = _try(alt)
        if not feats:
            return None
        lon, lat = feats[0]["geometry"]["coordinates"]
        return {"lon": lon, "lat": lat, "props": feats[0]["properties"]}

    def catchment(self, lon, lat):
        pt = Point(lon, lat)
        for props, geom in self.esbs:
            if geom.contains(pt):
                return props, geom, self.esb_to_gs.get(props[self.cfg.catchment_field_map["id"]], [])
        return None, None, []

    def gesix_at(self, lon, lat):
        """Point-in-polygon over the 447 GESIx planungsraum polygons.
        Returns {plr_name, plr_id, wert, rang, schicht, quintile_5} or None
        when the address falls outside any GESIx polygon (rare: Berlin
        outer edges, industrial zones without residential Planungsräume).
        quintile_5 is derived from the address's rank against the sorted
        wert distribution — 1 = top fifth, 5 = bottom fifth."""
        if not self.gesix:
            return None
        pt = Point(lon, lat)
        for props, geom in self.gesix:
            if geom.contains(pt):
                wert = props.get("gesix_wert")
                n = len(self._gesix_wert_sorted)
                # Quintile from the wert distribution — higher wert = better,
                # so quintile 1 = top of the sorted list from the top.
                if wert is None or n == 0:
                    q = None
                else:
                    # Count how many werts are strictly greater than mine.
                    higher = sum(1 for w in self._gesix_wert_sorted if w > wert)
                    q = min(5, higher * 5 // n + 1)
                return {
                    "plr_name": (props.get("plr_name") or "").strip(),
                    "plr_id":   props.get("plr_id") or props.get("plr"),
                    "wert":     wert,
                    "rang":     props.get("gesix_rang"),
                    "schicht":  props.get("gesix_schicht"),
                    "quintile_5": q,
                    "total":    n,
                }
        return None

    def nearest_gs_public(self, lon, lat, k=2):
        """Return the k nearest public Grundschulen by straight-line distance.
        Used as a fallback when an ESB polygon contains no school inside its
        geometry (small residential ESBs where the assigned school lives
        elsewhere — the geometric heuristic in esb_to_gs misses these)."""
        if not self.gs_public:
            return []
        sorted_gs = sorted(self.gs_public,
                           key=lambda pc: haversine_m(lon, lat, pc[1][0], pc[1][1]))
        return sorted_gs[:k]

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

    # -- Public-admin lookups (feed the raw-view Others tab) --------------

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

    # -- Quiet Living lens lookups ---------------------------------------

    def tempolimit_at(self, lon, lat, radius_m=100):
        """Nearest Tempolimits segment within `radius_m`. Returns
        `{"speed_kmh": float, "distance_m": int, "reason": str, "time_restriction": str|None}`
        or `None` if no exception feature is within radius (interpret as
        "default 50 km/h in effect").

        Uses the STRtree to prune candidates before running the exact
        `Point.project` on each geometry. Distance is haversine metres
        between the address and the nearest point on the LineString.
        """
        if not self.tempolimits or self._tempolimits_tree is None:
            return None
        pt = Point(lon, lat)
        # ~2×radius as a degree envelope (1° ≈ 111 km); at Berlin lat.
        deg_padding = max(0.002, (radius_m * 2) / 111_000.0)
        buf = pt.buffer(deg_padding)
        idx_candidates = self._tempolimits_tree.query(buf)
        best_idx, best_d = None, float("inf")
        for i in idx_candidates:
            _, geom = self.tempolimits[int(i)]
            try:
                near_pt = geom.interpolate(geom.project(pt))
            except Exception:
                continue
            d = haversine_m(lon, lat, near_pt.x, near_pt.y)
            if d < best_d:
                best_d, best_idx = d, int(i)
        if best_idx is None or best_d > radius_m:
            return None
        props, _ = self.tempolimits[best_idx]
        fm = self.cfg.tempolimits_field_map
        return {
            "speed_kmh":        props.get(fm["speed"]),
            "distance_m":       round(best_d),
            "reason":           (props.get(fm["reason"]) or "").strip() or None,
            "time_restriction": (props.get(fm["time_restriction"]) or "").strip() or None,
        }

    def nearest_arterial(self, lon, lat, radius_m=500):
        """Nearest arterial road within `radius_m`. Returns
        `{"name": str, "class": str, "distance_m": int}` or `None`
        if no arterial is within radius (interpret as "quiet residential
        block")."""
        if not self.arterial_roads or self._arterial_tree is None:
            return None
        pt = Point(lon, lat)
        deg_padding = max(0.005, (radius_m * 2) / 111_000.0)
        buf = pt.buffer(deg_padding)
        idx_candidates = self._arterial_tree.query(buf)
        best_idx, best_d = None, float("inf")
        for i in idx_candidates:
            _, geom = self.arterial_roads[int(i)]
            try:
                near_pt = geom.interpolate(geom.project(pt))
            except Exception:
                continue
            d = haversine_m(lon, lat, near_pt.x, near_pt.y)
            if d < best_d:
                best_d, best_idx = d, int(i)
        if best_idx is None or best_d > radius_m:
            return None
        props, _ = self.arterial_roads[best_idx]
        fm = self.cfg.arterial_field_map
        return {
            "name":       (props.get(fm["name"]) or "").strip() or "arterial road",
            "class":      (props.get(fm["class"]) or "").strip() or None,
            "distance_m": round(best_d),
        }

    def rail_track_proximity(self, lon, lat):
        """Nearest S-Bahn or U-Bahn station as a proxy for exposure to
        rail-track noise. Returns
        `{"mode": "S-Bahn"|"U-Bahn", "name": str, "distance_m": int}`
        for the closest of the two.

        ponytail: station coords are a proxy — real S-Bahn tracks extend
        kilometres beyond each station and generate the actual noise.
        A better signal would be the OSM `railway=rail` LineString,
        which we don't currently preload. Upgrade path: wire the OSM
        rail-line layer via osm_local and switch this to a real
        distance-to-track query.
        """
        best_mode, best_st, best_d = None, None, float("inf")
        for mode, stations in (("S-Bahn", self.sbahn), ("U-Bahn", self.ubahn)):
            if not stations:
                continue
            st = min(stations,
                     key=lambda s: haversine_m(lon, lat, s["lon"], s["lat"]))
            d = haversine_m(lon, lat, st["lon"], st["lat"])
            if d < best_d:
                best_mode, best_st, best_d = mode, st, d
        if best_st is None:
            return None
        return {
            "mode":       best_mode,
            "name":       best_st["name"],
            "distance_m": round(best_d),
        }


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

    # Every _load_* method exists on the class AND is invoked from
    # __init__ in the pinned order. Parsing the source keeps the
    # boot-time stdout timeline byte-exact — a future reshuffle of
    # loader calls trips this assertion instead of silently drifting
    # what ops see in the logs (CLAUDE.md §14 boot-log convention).
    _expected_loaders = [
        "_load_osm_snapshot", "_load_address_index",
        "_load_catchments_and_schools", "_load_kitas",
        "_load_fountains", "_load_hospitals",
        "_load_su_bahn", "_load_tram", "_load_regional_rail",
        "_load_fire", "_load_quiet_zones", "_load_protection",
        "_load_swim", "_load_bezirksgrenzen", "_load_gesix",
        "_load_buergeramts",
        "_load_tempolimits", "_load_arterial_roads",
    ]
    for name in _expected_loaders:
        assert callable(getattr(Index, name, None)), f"Index.{name} missing"

    import inspect as _inspect
    import re as _re
    _init_src = _inspect.getsource(Index.__init__)
    _actual_order = _re.findall(r"self\.(_load_\w+)\(\)", _init_src)
    assert _actual_order == _expected_loaders, (
        "Index.__init__ loader call order drifted from _expected_loaders.\n"
        f"expected: {_expected_loaders}\n"
        f"actual:   {_actual_order}"
    )

    print("index.py selfcheck OK (pure asserts only; live Index load in app.selfcheck)")
