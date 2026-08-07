"""/api/lookup — geocode + catchment + assigned schools + intl school + kitas.
Byte-for-byte parity with phase3/server.py:_lookup."""
from fastapi import APIRouter, Depends, HTTPException, Query
from shapely.geometry import mapping

from app.cities.base import CityConfig
from app.core.addr import parse_address
from app.core.amenities import kitas_near
from app.core.geo import haversine_m
from app.core.index import Index
from app.deps import get_city, get_index

router = APIRouter()


@router.get("/api/lookup")
def lookup(
    index: Index = Depends(get_index),
    cfg: CityConfig = Depends(get_city),
    address: str = Query("", description="Free-text address; ignored if street/hnr/plz all given."),
    street: str = Query(""),
    hnr: str = Query(""),
    plz: str = Query(""),
):
    addr = address.strip()
    street = street.strip()
    hnr = hnr.strip()
    plz = plz.strip()

    if addr and not (street and hnr and plz):
        p = parse_address(addr)
        if not p:
            raise HTTPException(400, "Could not parse address. Try 'Kastanienallee 12, 10435'.")
        street, hnr, plz = p

    if not (street and hnr and plz):
        raise HTTPException(400, "Missing street/hnr/plz.")

    try:
        geo = index.geocode(street, hnr, plz)
    except Exception as e:
        raise HTTPException(502, f"Geocoder unavailable: {e}")
    if not geo:
        raise HTTPException(404, f"No {cfg.display_name} address matched '{street} {hnr}, {plz}'.")

    lon, lat = geo["lon"], geo["lat"]
    esb_props, polygon, schools = index.catchment(lon, lat)

    s_fm = cfg.schools_field_map
    c_fm = cfg.catchment_field_map
    out_schools = []
    for s, c in schools:
        out_schools.append({
            "name": s[s_fm["name"]], "bsn": s[s_fm["id"]],
            "street": s.get(s_fm["street"], "").strip(),
            "hnr": s.get(s_fm["hnr"], "").strip(),
            "plz": s.get(s_fm["plz"], ""),
            "phone": s.get(s_fm["phone"]), "website": s.get(s_fm["website"]),
            "sesb_strand": index.sesb_strand(s[s_fm["name"]]),
            "school_year": s.get(s_fm["school_year"]),
            "lon": c[0], "lat": c[1],
        })

    intl = index.nearest_intl(lon, lat)
    intl_out = None
    if intl:
        s = intl["school"]
        intl_out = {"name": s[s_fm["name"]], "bsn": s[s_fm["id"]],
                    "distance_m": intl["distance_m"],
                    "lat": intl["lat"], "lon": intl["lon"],
                    "website": s.get(s_fm["website"])}

    kitas = kitas_near(index, cfg, lon, lat, 800)

    # Connectivity — nearest S-Bahn / U-Bahn / Tram / Regional rail + Airport.
    # Airport is a single point (per-city fixed landmark), so we compute its
    # distance directly rather than "nearest".
    conn = {
        "sbahn":         index.nearest_station(index.sbahn, lon, lat),
        "ubahn":         index.nearest_station(index.ubahn, lon, lat),
        "tram":          index.nearest_station(index.tram, lon, lat),
        "regional_rail": index.nearest_station(index.regional_rail, lon, lat),
        "airport":       None,
    }
    if cfg.airport:
        conn["airport"] = {
            **cfg.airport,
            "distance_m": round(haversine_m(lon, lat, cfg.airport["lon"], cfg.airport["lat"])),
        }

    return {
        "address": {"street": street, "hnr": hnr, "plz": plz,
                    "lon": lon, "lat": lat, "raw": geo["props"]},
        "catchment": {
            "esb": esb_props[c_fm["id"]] if esb_props else None,
            "district": esb_props[c_fm["district"]] if esb_props else None,
            "polygon": mapping(polygon) if polygon is not None else None,
        },
        "schools": out_schools,
        "intl_grundschule": intl_out,
        "kitas": kitas,
        "connectivity": conn,
        "provenance": {
            "catchment":     cfg.attribution["catchment"],
            "schools":       cfg.attribution["schools"],
            "addresses":     cfg.attribution["addresses"],
            "kitas":         cfg.attribution["kitas"],
            "sbahn":         cfg.attribution.get("sbahn", ""),
            "ubahn":         cfg.attribution.get("ubahn", ""),
            "tram":          cfg.attribution.get("tram", ""),
            "regional_rail": cfg.attribution.get("regional_rail", ""),
            "airport":       cfg.attribution.get("airport", ""),
        },
    }
