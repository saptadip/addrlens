"""Amenities near an address — Overpass query + BOD supplement for playgrounds
and parks. Ship B: takes a `CityConfig` so nothing Berlin-specific remains.

The Overpass tag filters (AMENITIES) stay hard-coded here: they're OSM
schema, not city-specific.
"""
import threading

from app.cities.base import CityConfig
from app.core.geo import haversine_m
from app.core.index import Index
from app.core.merge import merge_bod_and_osm
from app.core.overpass import overpass
from app.core.wfs import bod_polygon_features

AMENITIES = [
    ("playgrounds",  '["leisure"="playground"]',                     "Playground"),
    ("parks",        '["leisure"="park"]',                           "Park"),
    ("pharmacies",   '["amenity"="pharmacy"]',                       "Pharmacy"),
    ("supermarkets", '["shop"="supermarket"]',                       "Supermarket"),
    ("gps",          '["amenity"="doctors"]',                        "Doctor's office"),
    ("transit",      '["public_transport"~"^(platform|station)$"]',  "Transit stop"),
]

_amen_cache, _amen_lock = {}, threading.Lock()


def _bod_layers(cfg: CityConfig) -> dict:
    """BOD-first categories per plan §Ship B (parks + playgrounds). Empty tuple
    entry = "OSM only", used when a city doesn't publish that layer."""
    out = {}
    if cfg.green_wfs_url and cfg.playgrounds_layer:
        out["playgrounds"] = (cfg.green_wfs_url, cfg.playgrounds_layer)
    if cfg.green_wfs_url and cfg.parks_layer:
        out["parks"] = (cfg.green_wfs_url, cfg.parks_layer)
    return out


def _classify_amenity(tags):
    if tags.get("leisure") == "playground":                        return "playgrounds"
    if tags.get("leisure") == "park":                              return "parks"
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
    elif cat == "parks":
        if tags.get("access") and tags["access"] != "yes":  parts.append(tags["access"].title())
        if tags.get("dog") == "leashed":         parts.append("Dogs on leash")
        if tags.get("wheelchair") == "yes":      parts.append("Step-free")
    return " · ".join(parts)


def _mixed_provenance(cfg: CityConfig, cat, n_bod, n_osm, bod_err):
    """Human-readable provenance string reflecting what actually contributed."""
    bod_name = cfg.attribution.get(cat, "")
    osm_name = "© OpenStreetMap contributors (ODbL)"
    if bod_err:
        return f"{osm_name} · BOD unavailable ({bod_err[:60]})"
    if n_bod and n_osm:  return f"{bod_name} + {osm_name} supplement"
    if n_bod:            return bod_name
    return osm_name


def amenities_near(index: Index, cfg: CityConfig, lon, lat, radius_m=800):
    """One Overpass round-trip for all categories, then per-BOD-category WFS
    supplement for playgrounds and parks (BOD-first, OSM fills known gaps).

    ponytail: kept the combined Overpass query (per-category parallel was slower
    thanks to Overpass per-IP slot limits). BOD calls run sequentially after —
    each is a small bbox WFS and typically <300 ms."""
    key = (cfg.slug, round(lon, 4), round(lat, 4), radius_m)
    with _amen_lock:
        if key in _amen_cache:
            return _amen_cache[key]

    hospital_radius = cfg.hospital_radius_m
    hospital_match_m = cfg.hospital_match_m
    bod_layers = _bod_layers(cfg)

    # --- OSM round-trip -----------------------------------------------------
    # Extra hospital query at the wider hospital radius; not part of AMENITIES
    # because hospitals are BOD-first and OSM only supplies contact fields.
    hosp_ql = (f'nwr["amenity"="hospital"](around:{hospital_radius},{lat},{lon});'
               f'nwr["healthcare"="hospital"](around:{hospital_radius},{lat},{lon});')
    parts = hosp_ql + "".join(f"nwr{flt}(around:{radius_m},{lat},{lon});" for _, flt, _ in AMENITIES)
    ql = f"[out:json][timeout:60];({parts});out center tags;"
    osm_err = None
    try:
        d = overpass(ql, timeout_s=75)
        osm_ok = True
    except Exception as e:
        d = {"elements": []}
        osm_ok = False
        osm_err = str(e)

    fallback = {k: lbl for k, _, lbl in AMENITIES}
    buckets  = {k: [] for k, _, _ in AMENITIES}
    seen     = {k: set() for k, _, _ in AMENITIES}
    osm_hospitals = []                                  # for BOD-hospital enrichment below
    for el in d.get("elements", []):
        tags = el.get("tags") or {}
        lat_, lon_ = (el.get("lat"), el.get("lon")) if el["type"] == "node" \
                    else (el.get("center", {}).get("lat"), el.get("center", {}).get("lon"))
        if lat_ is None: continue
        if tags.get("amenity") == "hospital" or tags.get("healthcare") == "hospital":
            osm_hospitals.append({"lat": lat_, "lon": lon_, "tags": tags})
            continue
        cat = _classify_amenity(tags)
        if not cat: continue
        name = tags.get("name") or fallback[cat]
        dkey = (name,) if cat == "transit" else (name, round(lat_, 5), round(lon_, 5))
        if dkey in seen[cat]: continue
        seen[cat].add(dkey)
        buckets[cat].append({"name": name, "lat": lat_, "lon": lon_,
                             "distance_m": round(haversine_m(lon, lat, lon_, lat_)),
                             "info": _summarize(cat, tags), "source": "osm",
                             "tags": tags})

    # --- BOD supplement (playgrounds, parks) --------------------------------
    result = {}
    for cat, _, _ in AMENITIES:
        osm_items = sorted(buckets[cat], key=lambda x: x["distance_m"])
        if cat in bod_layers:
            base, layer = bod_layers[cat]
            bod_items = bod_polygon_features(base, layer, lon, lat, radius_m)
            bod_err = next((b["_error"] for b in bod_items if b.get("_error")), None)
            bod_items = [b for b in bod_items if not b.get("_error")]
            merged = merge_bod_and_osm(bod_items, osm_items, radius_m)
            n_bod, n_osm = sum(1 for x in merged if x["source"] == "bod"), sum(1 for x in merged if x["source"] == "osm")
            prov = _mixed_provenance(cfg, cat, n_bod, n_osm, bod_err)
            result[cat] = {"count": len(merged), "items": merged[:25],
                           "bod_count": n_bod, "osm_count": n_osm, "provenance": prov}
        else:
            result[cat] = {"count": len(osm_items), "items": osm_items[:25],
                           "provenance": "© OpenStreetMap contributors (ODbL)"}
    if not osm_ok:
        # OSM completely failed — still return BOD-backed categories; mark OSM-only ones as errored.
        for cat, _, _ in AMENITIES:
            if cat not in bod_layers:
                result[cat] = {"count": None, "items": [], "error": osm_err}

    # Hospitals: BOD-first for identity (name, beds, Träger) with OSM overlay
    # for contact fields the city doesn't publish (emergency, phone, website,
    # wheelchair). Match by nearest OSM within hospital_match_m — campuses in
    # OSM are usually ways, so their `center` may sit up to a few hundred metres
    # from the BOD entrance point.
    hosp = index.hospitals_near_bod(lon, lat, hospital_radius)
    n_enriched = 0
    if osm_hospitals:
        for h in hosp:
            match, best = None, hospital_match_m
            for o in osm_hospitals:
                d = haversine_m(h["lon"], h["lat"], o["lon"], o["lat"])
                if d <= best: match, best = o, d
            if match:
                t = match["tags"]
                h["osm"] = {
                    "emergency":  t.get("emergency"),
                    "phone":      t.get("phone") or t.get("contact:phone"),
                    "website":    t.get("website") or t.get("contact:website"),
                    "wheelchair": t.get("wheelchair"),
                    "match_m":    round(best),
                }
                n_enriched += 1
    prov = cfg.attribution.get("hospitals", "")
    if n_enriched:
        prov += f" + © OpenStreetMap contributors (ODbL) — contact/ER for {n_enriched}/{len(hosp)}"
    elif not osm_ok:
        prov += " · OSM overlay unavailable"
    result["hospitals"] = {
        "count": len(hosp), "items": hosp[:25],
        "radius_m": hospital_radius, "osm_enriched": n_enriched,
        "provenance": prov,
    }

    # Public drinking fountains (BOD-only, walkable stroller amenity).
    fountains = index.fountains_near_bod(lon, lat, radius_m)
    result["fountains"] = {
        "count": len(fountains), "items": fountains[:25],
        "provenance": cfg.attribution.get("fountains", ""),
    }

    with _amen_lock:
        _amen_cache[key] = result
    return result


def kitas_near(index: Index, cfg: CityConfig, lon, lat, radius_m=800):
    """Return {'count', 'items', 'source', 'provenance'} — geoportal Kitas."""
    items = index.kitas_near_bod(lon, lat, radius_m)
    return {"count": len(items), "items": items, "source": "bod",
            "provenance": cfg.attribution.get("kitas", "")}


if __name__ == "__main__":
    # Pure asserts only (network paths exercised in app.selfcheck).
    assert _classify_amenity({"leisure": "playground"}) == "playgrounds"
    assert _classify_amenity({"public_transport": "station"}) == "transit"
    assert _classify_amenity({"random": "tag"}) is None
    assert _short_hours("Mo-Fr 08:00-20:00") == "Mo-Fr 08:00-20:00"
    long = "Mo-Fr 08:00-20:00; Sa 09:00-18:00; Su 10:00-16:00"
    assert _short_hours(long).endswith("…")
    # Copied verbatim from phase3/server.py:_selfcheck.
    assert _summarize("transit", {"subway": "yes", "operator": "BVG"}) == "U-Bahn · BVG"
    assert _summarize("playgrounds", {"min_age": "3", "max_age": "12", "surface": "sand"}) == "Ages 3–12 · Surface: sand"
    assert _summarize("supermarkets", {}) == ""
    assert _summarize("parks", {"dog": "leashed", "wheelchair": "yes"}) == "Dogs on leash · Step-free"

    # Ship B: provenance composition + bod_layers derivation come from CityConfig.
    from app.cities.berlin import BERLIN as _CFG
    layers = _bod_layers(_CFG)
    assert set(layers) == {"playgrounds", "parks"}
    assert _mixed_provenance(_CFG, "parks", 3, 0, None).startswith("Geoportal Berlin")
    assert "supplement" in _mixed_provenance(_CFG, "parks", 3, 2, None)
    assert _mixed_provenance(_CFG, "parks", 0, 2, None) == "© OpenStreetMap contributors (ODbL)"
    print("amenities.py selfcheck OK")
