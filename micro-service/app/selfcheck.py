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
from app.core.geo import haversine_m
from app.core.index import Index
from app.core.wfs import bod_polygon_features, noise_at

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
