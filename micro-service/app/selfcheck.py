"""End-to-end selfcheck. Run: `python -m app.selfcheck` (defaults to CITY=berlin
via app.config.load_city).

Two phases:
  1. Each `app.core.*` module's own `__main__` block (fast, pure).
  2. The live-Index / live-WFS asserts that need a real network — ported
     from phase3/server.py:_selfcheck. Berlin-specific known-good addresses.

LLM asserts (`_build_impression_messages`, model output shape) live in
`inference/selfcheck.py`.
"""
import subprocess
import sys

from app.config import load_city
from app.core.amenities import amenities_near
from app.core.geo import haversine_m
from app.core.index import Index
from app.core import scorer
from app.core.wfs import air_quality_at, bod_polygon_features, noise_at, summer_heat_at

CORE_MODULES = [
    "app.core.geo",
    "app.core.scorer",
    "app.core.merge",
    "app.core.wfs",
    "app.core.overpass",
    "app.core.gloss",
    "app.core.addr",
    "app.core.amenities",
    "app.core.index",
]


def run_cities_isolation() -> None:
    """Boot each city module in a fresh subprocess. A bad city module must
    not affect any other city's import — that's the code-layer promise the
    per-process deployment model (plan §0) rests on. A missing dataclass
    field will raise at construction; a syntax error at import; either way
    the failure is scoped to that subprocess.

    Discovers cities dynamically — every new `app/cities/<slug>.py` is
    picked up without touching this file.
    """
    import pkgutil
    from app import cities as _cities_pkg

    print("=== cities isolation ===")
    names = sorted(
        m.name for m in pkgutil.iter_modules(_cities_pkg.__path__)
        if m.name != "base" and not m.name.startswith("_")
    )
    if not names:
        print("(no city modules found)")
        return

    # Child probe: import one city, verify shape. Pass slug through argv so
    # the -c string stays free of nested-quote escaping.
    child = (
        "import sys; slug=sys.argv[1]; "
        "from app.cities.base import CityConfig; "
        "mod=__import__('app.cities.'+slug, fromlist=['*']); "
        "cfg=getattr(mod, slug.upper()); "
        "assert isinstance(cfg, CityConfig), 'must export a CityConfig'; "
        "assert cfg.slug == slug, 'slug mismatch: module='+slug+' cfg.slug='+repr(cfg.slug); "
        "print('OK')"
    )

    failed = []
    for slug in names:
        print(f"→ {slug} …", end=" ", flush=True)
        r = subprocess.run(
            [sys.executable, "-c", child, slug],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            print("FAIL")
            print(r.stdout, r.stderr)
            failed.append(slug)
        else:
            print(r.stdout.strip())

    if failed:
        print(f"\ncities isolation FAIL: {failed}")
        sys.exit(1)


def run_pure_selfchecks() -> None:
    """Runs each core module's __main__ block via subprocess. Bails on first failure."""
    for mod in CORE_MODULES:
        print(f"→ {mod} …", end=" ", flush=True)
        r = subprocess.run([sys.executable, "-m", mod], capture_output=True, text=True)
        if r.returncode != 0:
            print("FAIL")
            print(r.stdout, r.stderr)
            sys.exit(1)
        # Print the last line of the module's output (its "OK" line).
        print(r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "OK")


def run_live_selfcheck() -> None:
    """Live-Index asserts — need real Berlin Geoportal + WFS access. The
    known-good addresses (Kastanienallee 12, Kurfürstendamm 195) are Berlin-
    specific; when Hamburg lands in Ship C, add its own addresses behind a
    `if cfg.slug == "berlin":` branch or split into per-city selfchecks."""
    cfg = load_city()
    if cfg.slug != "berlin":
        print(f"live selfcheck: no known-good asserts for CITY={cfg.slug!r} yet (Berlin-only for now)")
        return
    print(f"→ Index({cfg.slug}) build …", flush=True)
    idx = Index(cfg)

    # -- Geocode + catchment ------------------------------------------------
    geo = idx.geocode("Kastanienallee", "12", "10435")
    assert geo, "known Prenzlauer Berg address must geocode"
    props, poly, schools = idx.catchment(geo["lon"], geo["lat"])
    assert props and props[cfg.catchment_field_map["district"]] == "Pankow"
    name_field = cfg.schools_field_map["name"]
    assert any("Senefelderplatz" in s[name_field] for s, _ in schools)
    assert all(isinstance(c, list) and len(c) == 2 for _, c in schools), \
        "schools carry [lon,lat]"

    intl = idx.nearest_intl(geo["lon"], geo["lat"])
    assert intl and intl["distance_m"] < 10_000
    assert idx.sesb_strand("Joan-Miró-Grundschule") == "German-Spanish"

    # -- Kitas --------------------------------------------------------------
    assert len(idx.kitas) >= 2500, f"expected ≥2500 BOD Kitas, got {len(idx.kitas)}"
    ks = idx.kitas_near_bod(geo["lon"], geo["lat"], 800)
    assert len(ks) >= 3, f"expected ≥3 BOD Kitas near Kastanienallee 12, got {len(ks)}"
    assert all(k["source"] == "bod" and k["distance_m"] <= 800 for k in ks)

    # -- Hospitals ----------------------------------------------------------
    assert len(idx.hospitals) >= 80, f"expected ≥80 hospitals city-wide, got {len(idx.hospitals)}"
    hs = idx.hospitals_near_bod(geo["lon"], geo["lat"], 2000)
    assert len(hs) >= 1, f"expected ≥1 hospital within 2km of Kastanienallee 12, got {len(hs)}"
    assert all(h["source"] == "bod" and h["distance_m"] <= 2000 for h in hs)
    hs_wide = idx.hospitals_near_bod(geo["lon"], geo["lat"], 5000)
    assert len(hs_wide) >= 5, f"expected ≥5 hospitals within 5km, got {len(hs_wide)}"
    assert any("Hedwig" in h["name"] or "Charité" in h["name"] for h in hs_wide), \
        "Charité or St. Hedwig should be within 5km of Prenzlauer Berg"

    # OSM hospital match-radius sanity: within-match_m match wins, farther is dropped.
    _bod = {"lat": 52.500, "lon": 13.400}
    _near = {"lat": 52.5025, "lon": 13.4025}   # ~330 m
    _far  = {"lat": 52.510,  "lon": 13.410}    # ~1300 m
    assert haversine_m(_bod["lon"], _bod["lat"], _near["lon"], _near["lat"]) < cfg.hospital_match_m
    assert haversine_m(_bod["lon"], _bod["lat"], _far["lon"],  _far["lat"])  > cfg.hospital_match_m

    # -- Fountains ----------------------------------------------------------
    assert len(idx.fountains) >= 150, f"expected ≥150 fountains, got {len(idx.fountains)}"
    fs = idx.fountains_near_bod(geo["lon"], geo["lat"], 800)
    assert all(f["source"] == "bod" and f["distance_m"] <= 800 for f in fs)
    fs_wide = idx.fountains_near_bod(geo["lon"], geo["lat"], 3000)
    assert len(fs_wide) >= 3, f"expected ≥3 fountains within 3km of Kastanienallee 12, got {len(fs_wide)}"

    # -- BOD polygon fetch --------------------------------------------------
    parks = bod_polygon_features(cfg.green_wfs_url, cfg.parks_layer,
                                 geo["lon"], geo["lat"], 800)
    parks = [p for p in parks if not p.get("_error")]
    assert len(parks) >= 1, "expected ≥1 BOD park within 800m of Kastanienallee 12"
    assert all(p["source"] == "bod" and 0 < p["distance_m"] <= 800 for p in parks)

    # -- Phase 1 killer cards -----------------------------------------------
    fr = idx.fire_rescue(geo["lon"], geo["lat"])
    assert fr and fr["nearest"]["distance_m"] < 2000, \
        f"expected fire station within 2km, got {fr}"
    assert fr["zone_name"], "fire response zone must be identified"
    assert len(fr["top3"]) >= 3, "expected 3 nearest stations returned"

    pr = idx.neighborhood_protection(geo["lon"], geo["lat"])
    # Kastanienallee 12 is inside Teutoburger Platz Milieuschutz zone (EM0313).
    assert pr["milieuschutz"]["inside"] is True, \
        f"expected Kastanienallee 12 inside Milieuschutz zone, got {pr}"
    assert "Teutoburger" in (pr["milieuschutz"]["area_name"] or "")

    qz = idx.nearest_quiet_zone(geo["lon"], geo["lat"])
    assert qz and qz["distance_m"] < 5000, f"quiet zone too far or missing: {qz}"

    pools = idx.pools_within(geo["lon"], geo["lat"], 3000)
    assert len(pools) >= 1, "expected ≥1 BBB pool within 3km of Kastanienallee 12"
    natural = idx.natural_swim_within(geo["lon"], geo["lat"], 15000)
    assert len(natural) >= 3, "expected ≥3 natural swim spots within 15km"

    trees = idx.trees_bbox(geo["lon"], geo["lat"], 200)
    assert trees and trees.get("count", 0) >= 20, \
        f"expected ≥20 street trees within 200m of Kastanienallee 12, got {trees}"
    assert trees.get("top_species"), "trees summary must carry species breakdown"

    # -- Phase 2: Umweltatlas Air Quality + Summer Heat ---------------------
    air = air_quality_at(cfg, geo["lon"], geo["lat"])
    assert air and not air.get("unavailable"), f"expected air-quality reading, got {air}"
    assert 5 < (air.get("no2_ugm3") or 0) < 100, f"NO2 out of sanity range: {air}"
    assert air.get("street"), "air block must carry street name"
    heat = summer_heat_at(cfg, geo["lon"], geo["lat"])
    assert heat and not heat.get("unavailable"), f"expected heat classification, got {heat}"
    assert heat.get("day_class"), "heat block must carry day_class string"
    assert "belastung" in heat["day_class"].lower(), \
        f"heat day_class should include Belastung tier tag, got {heat['day_class']!r}"

    # -- Connectivity -------------------------------------------------------
    assert len(idx.sbahn) >= 150, f"expected ≥150 S-Bahn stations, got {len(idx.sbahn)}"
    assert len(idx.ubahn) >= 200, f"expected ≥200 U-Bahn stations (incl. S+U), got {len(idx.ubahn)}"
    assert len(idx.tram) >= 300, f"expected ≥300 tram stops, got {len(idx.tram)}"
    assert len(idx.regional_rail) == 12, f"expected 12 curated regional-rail stations, got {len(idx.regional_rail)}"
    # Kastanienallee 12 is walking distance from U Eberswalder (~250 m).
    ub = idx.nearest_station(idx.ubahn, geo["lon"], geo["lat"])
    assert ub and ub["distance_m"] < 500, f"expected U-Bahn <500m of Kastanienallee 12, got {ub}"
    # Airport is a Berlin-fixed landmark; every inside-Berlin address should be
    # >5 km and <40 km from BER (BER is ~18 km from Alexanderplatz).
    airport = cfg.airport
    assert airport, "Berlin config must define airport"
    from app.core.geo import haversine_m as _hav
    d_ber = _hav(geo["lon"], geo["lat"], airport["lon"], airport["lat"])
    assert 5000 < d_ber < 40000, f"BER distance outside sanity range: {d_ber:.0f} m"

    # -- Noise lookup on a known-loud address -------------------------------
    kurf = idx.geocode("Kurfürstendamm", "195", "10707")
    assert kurf, "Kurfürstendamm 195 must geocode"
    n = noise_at(cfg, kurf["lon"], kurf["lat"])
    if n.get("unavailable"):
        print(f"  noise WFS unavailable ({n.get('error') or n.get('reason')}) — skipped assertion")
    else:
        assert n["l_den"]["total"] and n["l_den"]["total"] > 55, \
            f"expected L_DEN > 55 on Kurfürstendamm 195, got {n['l_den']}"
        assert n["distance_m"] < 60, f"nearest façade point should be close; got {n['distance_m']} m"

    # -- Young Family lens ---------------------------------------------------
    # Two known-good addresses cover two very different lens shapes:
    #   Kastanienallee 12 (Prenzlauer Berg) — dense, family-heavy inner city.
    #   Bergmannstraße 27 (Kreuzberg)      — the user-verified pediatrician anchor.
    def _compute_lens(lon_, lat_):
        _amen  = amenities_near(idx, cfg, lon_, lat_, 800) or {}
        _noise = noise_at(cfg, lon_, lat_)
        _air   = air_quality_at(cfg, lon_, lat_)
        _heat  = summer_heat_at(cfg, lon_, lat_)
        _trees = idx.trees_bbox(lon_, lat_)
        _qz    = idx.nearest_quiet_zone(lon_, lat_)
        _lens  = scorer.young_family_lens(cfg, idx, lon_, lat_,
                                          air=_air, heat=_heat, noise=_noise,
                                          amenities=_amen, trees=_trees,
                                          quiet_zone=_qz)
        return _lens, _amen, _noise, _heat, _air

    lens_yf, _amen, n_raw, h_raw, a_raw = _compute_lens(geo["lon"], geo["lat"])
    assert len(lens_yf["tiles"]) == 7, f"expected 7 tiles, got {len(lens_yf['tiles'])}"
    _keys = [t["key"] for t in lens_yf["tiles"]]
    assert _keys == ["kita","playground","pediatrician","noise","heat","air","refuge"], _keys
    for t in lens_yf["tiles"]:
        assert t["label"] and t["rule"], t
        assert t["tier"] in {"green","amber","red","unknown"}, t
    _by = {t["key"]: t for t in lens_yf["tiles"]}
    # Dense Prenzlauer Berg → kita must be green.
    assert _by["kita"]["tier"] == "green", \
        f"expected kita green at Kastanienallee 12: {_by['kita']}"
    # Defensive: at least one tile must be green.
    assert any(t["tier"] == "green" for t in lens_yf["tiles"]), \
        "the lens must produce some positive signal in dense inner Berlin"
    # kita cited in provenance (kita is green).
    assert "Kindertagesstätten" in lens_yf["provenance"], lens_yf["provenance"]
    # Consistency invariant: no tile is unknown unless the matching raw block
    # is also unavailable in the same lookup.
    if n_raw.get("unavailable"):
        assert _by["noise"]["tier"] == "unknown"
    else:
        assert _by["noise"]["tier"] != "unknown", _by["noise"]
    if h_raw.get("unavailable"):
        assert _by["heat"]["tier"] == "unknown"
    else:
        assert _by["heat"]["tier"] != "unknown", _by["heat"]
    if a_raw.get("unavailable"):
        assert _by["air"]["tier"] == "unknown"
    else:
        assert _by["air"]["tier"] != "unknown", _by["air"]

    # -- Bergmannstraße 27 (pediatrician anchor) -----------------------------
    berg = idx.geocode("Bergmannstraße", "27", "10961")
    if not berg:
        print("  Bergmannstraße 27 geocode failed — skipped pediatrician anchor")
    else:
        lens_b, _, _, _, _ = _compute_lens(berg["lon"], berg["lat"])
        _by_b = {t["key"]: t for t in lens_b["tiles"]}
        assert _by_b["pediatrician"]["tier"] == "green", \
            f"expected paediatric green at Bergmannstraße 27: {_by_b['pediatrician']}"
        assert "m" in _by_b["pediatrician"]["numeric"], _by_b["pediatrician"]
        assert "OSM community-tagged" in _by_b["pediatrician"]["caveat"], \
            _by_b["pediatrician"]["caveat"]
        # Marheinekeplatz Spielplatz is ~75m; playground must be green.
        assert _by_b["playground"]["tier"] == "green", \
            f"expected playground green at Bergmannstraße 27: {_by_b['playground']}"
    print("  young_family lens asserts OK")

    print("→ live selfcheck OK")


def main() -> None:
    run_cities_isolation()
    print("\n=== pure module selfchecks ===")
    run_pure_selfchecks()
    print("\n=== live selfcheck (network) ===")
    run_live_selfcheck()
    print("\nselfcheck: OK")


if __name__ == "__main__":
    main()
