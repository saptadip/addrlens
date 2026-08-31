"""/api/lookup — geocode + catchment + assigned schools + intl school + kitas.
Byte-for-byte parity with phase3/server.py:_lookup."""
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.core.rate_limit import limiter
from shapely.geometry import mapping

from app.cities.base import CityConfig
from app.core.addr import parse_address
from app.core.amenities import amenities_near, kitas_near
from app.core.geo import haversine_m
from app.core.index import Index
from app.core.wfs import air_quality_at, noise_at, summer_heat_at
from app.core import others_admin as others_admin_mod
from app.core import scorer
from app.deps import get_city, get_index

router = APIRouter()


@router.get("/api/lookup")
@limiter.limit("60/minute")
def lookup(
    request: Request,
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
        # Common cause: BOD WFS 400 when a field type mismatches — surface
        # a short user-facing message instead of the raw HTTP error.
        msg = str(e)
        if "HTTP Error 400" in msg or "Bad Request" in msg:
            raise HTTPException(404, f"Address '{street} {hnr}, {plz}' not recognised — check street number.")
        raise HTTPException(502, f"Geocoder unavailable, please retry.")
    if not geo:
        raise HTTPException(404, f"Address '{street} {hnr}, {plz}' not found in Berlin.")

    lon, lat = geo["lon"], geo["lat"]
    esb_props, polygon, schools = index.catchment(lon, lat)

    s_fm = cfg.schools_field_map
    c_fm = cfg.catchment_field_map
    # If no Grundschule sits inside this ESB's polygon, fall back to the two
    # nearest public Grundschulen — small residential ESBs where the assigned
    # school lives outside the polygon (the geometric esb_to_gs mapping misses
    # them). Frontend renders an "outside-catchment" caveat when this fires.
    schools_source = "esb" if schools else ("nearest" if polygon is not None else None)
    if not schools and polygon is not None:
        schools = index.nearest_gs_public(lon, lat, k=2)
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
            "_fallback": schools_source == "nearest",
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

    # Phase-1 killer cards — five per-address blocks derived from Berlin BOD.
    fire_rescue  = index.fire_rescue(lon, lat)
    quiet_zone   = index.nearest_quiet_zone(lon, lat)
    protection   = index.neighborhood_protection(lon, lat)
    swim_pools   = index.pools_within(lon, lat, 3000)
    swim_natural = index.natural_swim_within(lon, lat, 3000)
    trees_summary = index.trees_bbox(lon, lat)
    air          = air_quality_at(cfg, lon, lat)
    heat         = summer_heat_at(cfg, lon, lat)

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

    # -- Young Family lens (Spec A) ----------------------------------------
    # The lens needs playgrounds + gps (pediatricians) + noise, none of
    # which /api/lookup exposes today. We fetch them here purely for the
    # lens — they do NOT leak into the /api/lookup response shape (the
    # frontend still calls /api/amenities and /api/noise for the raw
    # views; both helpers are cache-backed so second calls are ~ms).
    try:
        _amen  = amenities_near(index, cfg, lon, lat, 800)
        _noise = noise_at(cfg, lon, lat)
    except Exception:
        _amen, _noise = {}, {"unavailable": True}
    try:
        lens_yf = scorer.young_family_lens(
            cfg, index, lon, lat,
            air=air, heat=heat, noise=_noise,
            amenities=_amen or {},
            trees=trees_summary, quiet_zone=quiet_zone,
        )
    except Exception as e:
        # The lens is additive. Never break /api/lookup for it (§14.7).
        lens_yf = {"slug": "young_family",
                   "error": f"{type(e).__name__}: {e}"}

    # --- Admin-offices bundle (raw view "Others" tab) --------------------
    # Ordered card metadata comes from `cfg.others_admin_cards`; features
    # per card come from Index preloads (Bürgerämter, Standesamt-by-Bezirk,
    # Arbeitsagenturs) or curated CityConfig directories (Finanzamts, LEA).
    # Deterministic — no external fetches on the hot path. Wrapped in
    # try/except so a bug here never breaks /api/lookup for other
    # consumers (§14.7). Response key stays `others.bureaucracy` for
    # frontend compatibility.
    try:
        others_admin = others_admin_mod.build(cfg, index, lon, lat)
    except Exception as e:
        others_admin = {"tiles": [], "provenance": "",
                        "error": f"{type(e).__name__}: {e}"}

    # --- Newcomer lens (Spec E) -------------------------------------------
    # Pure Python — reads only pre-loaded Index state, no live-fetch on
    # hot path. Wrapped in try/except so a bug here never breaks /api/lookup
    # for users not using the Newcomer lens (§14.7).
    try:
        lens_newcomer = scorer.newcomer_lens(cfg, index, lon, lat,
                                             amenities=_amen or {})
    except Exception as e:
        lens_newcomer = {"slug": "newcomer",
                         "error": f"{type(e).__name__}: {e}"}

    # --- Quiet Living lens ------------------------------------------------
    # Reuses the same air / noise / quiet_zone / trees values computed
    # once above so the raw view and the lens can never disagree.
    # Additive — wrapped in try/except like every other lens.
    try:
        from app.core.lenses.quiet_living import quiet_living_lens
        lens_quiet = quiet_living_lens(
            cfg, index, lon, lat,
            air=air, noise=_noise,
            quiet_zone=quiet_zone, trees=trees_summary,
        )
    except Exception as e:
        lens_quiet = {"slug": "quiet_living",
                      "error": f"{type(e).__name__}: {e}"}

    return {
        "address": {"street": street, "hnr": hnr, "plz": plz,
                    "lon": lon, "lat": lat, "raw": geo["props"]},
        "catchment": {
            "esb": esb_props[c_fm["id"]] if esb_props else None,
            "district": esb_props[c_fm["district"]] if esb_props else None,
            "polygon": mapping(polygon) if polygon is not None else None,
            "schools_source": schools_source,   # "esb" | "nearest" | None
        },
        "schools": out_schools,
        "intl_grundschule": intl_out,
        "kitas": kitas,
        "connectivity": conn,
        "fire_rescue":  fire_rescue,
        "quiet_zone":   quiet_zone,
        "protection":   protection,
        "swim":         {"pools": swim_pools, "natural": swim_natural},
        "trees":        trees_summary,
        "air":          air,
        "heat":         heat,
        "lens":         {"young_family":  lens_yf,
                         "newcomer":      lens_newcomer,
                         "quiet_living":  lens_quiet},
        "others":       {"bureaucracy": others_admin},
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
            "fire":          cfg.attribution.get("fire", ""),
            "trees":         cfg.attribution.get("trees", ""),
            "quiet_zone":    cfg.attribution.get("quiet_zone", ""),
            "protection":    cfg.attribution.get("protection", ""),
            "pools":         cfg.attribution.get("pools", ""),
            "natural_swim":  cfg.attribution.get("natural_swim", ""),
            "air":           cfg.attribution.get("air", ""),
            "heat":          cfg.attribution.get("heat", ""),
            "tempolimits":   cfg.attribution.get("tempolimits", ""),
            "arterial_road": cfg.attribution.get("arterial_road", ""),
        },
    }
