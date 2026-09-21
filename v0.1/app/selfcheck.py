"""End-to-end selfcheck. Run: `python -m app.selfcheck` (defaults to CITY=berlin
via app.config.load_city).

Two phases:
  1. Each `app.core.*` module's own `__main__` block (fast, pure).
  2. The live-Index / live-WFS asserts that need a real network — ported
     from phase3/server.py:_selfcheck. Berlin-specific known-good addresses.

LLM template asserts (prompt shape, anti-inversion, schema) live in
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
    "app.core.cache",
    "app.core.scorer",
    # Split-out scoring primitives — each carries its own __main__ selfcheck.
    # The scorer.py regression harness still exercises them transitively, but
    # per-module asserts (added over time) only fire when we invoke them.
    "app.core.scoring.constants",
    "app.core.scoring.legends",
    "app.core.scoring.shape",
    "app.core.scoring.provenance",
    "app.core.scoring.tiers",
    "app.core.others_admin",
    "app.core.loaders.wfs_layer",
    "app.core.loaders.buergeramt_service_portal",
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


def _live_selfcheck_berlin(cfg) -> None:
    """Live-Index asserts for Berlin — Geoportal + WFS access required."""
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
    # Curated regional-rail list — count is loosened to a ≥12 lower-bound
    # rather than pinned equality. The list grows opportunistically as
    # new RE/RB stops become relevant (recently 12 → 15); a pinned assert
    # kept firing on every additive curation. Pin the FLOOR, not the head.
    assert len(idx.regional_rail) >= 12, f"expected ≥12 curated regional-rail stations, got {len(idx.regional_rail)}"
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
    assert len(lens_yf["tiles"]) >= 7, f"expected ≥7 YF tiles, got {len(lens_yf['tiles'])}"
    _keys = [t["key"] for t in lens_yf["tiles"]]
    # YF lens grew from the original 7 tiles to 10 (added transit,
    # supermarket, gesix). Assert containment of the CORE 7, not
    # equality — additive drift is not a bug, and the source of truth
    # for exact order is `app/cities/berlin.py::YF_LENS.tiles`.
    _yf_core = {"kita", "playground", "pediatrician", "noise", "heat", "air", "refuge"}
    assert _yf_core.issubset(_keys), f"YF lens missing core tiles: {_yf_core - set(_keys)} · full: {_keys}"
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
        # -- Spec D: pediatrician feature has phone + website + hours ---
        _ped_features = _by_b["pediatrician"]["features"]
        assert len(_ped_features) >= 1
        _berns = next((f for f in _ped_features if "Berns" in f.get("name", "")), None)
        assert _berns is not None, "Dr. Berns expected in pediatrician features"
        assert _berns.get("phone", "").startswith("+49"), _berns
        assert _berns.get("website", "").startswith("http"), _berns
        assert "Mo" in _berns.get("hours", ""), _berns.get("hours")
    # -- Spec D: feature arrays present ---------------------------------
    _by = {t["key"]: t for t in lens_yf["tiles"]}
    _kita_f = _by["kita"]["features"]
    assert isinstance(_kita_f, list) and len(_kita_f) >= 3, \
        f"expected ≥3 kita features in dense Pankow, got {len(_kita_f)}"
    _first = _kita_f[0]
    assert _first.get("name") and _first.get("distance_m", 0) > 0
    assert 52.3 < _first["lat"] < 52.7 and 13.0 < _first["lon"] < 13.8
    # At least one kita should carry BOD e_platz capacity (usually all do)
    assert any("capacity" in f for f in _kita_f), \
        "BOD kita records should carry e_platz capacity for most entries"
    # Aggregate tiles → []
    assert _by["noise"]["features"] == []
    assert _by["heat"]["features"]  == []
    assert _by["air"]["features"]   == []
    # Refuge metadata carries trees dict (may be empty on trees WFS outage)
    assert _by["refuge"].get("metadata", {}).get("trees") is not None
    print("  young_family lens asserts OK")

    # -- Admin-offices bundle (Others tab) ---------------------------------
    # Bureaucracy lens has been removed; the underlying cards live under
    # /api/lookup `others.bureaucracy` (legacy response-key name retained
    # for the SPA's raw-view Others tab) and are built by the pure,
    # tier-less `app.core.others_admin.build` composer.
    from app.core import others_admin as _others_admin
    bundle = _others_admin.build(cfg, idx, geo["lon"], geo["lat"])
    _admin_keys = ["buergeramt", "finanzamt", "standesamt", "lea", "arbeitsagentur"]
    assert len(bundle["tiles"]) == len(_admin_keys), \
        f"expected {len(_admin_keys)} tiles, got {len(bundle['tiles'])}"
    _bk = [t["key"] for t in bundle["tiles"]]
    assert _bk == _admin_keys, _bk
    for t in bundle["tiles"]:
        assert t["label"] and t["icon"], t
        assert set(t.keys()) == {"key", "label", "icon", "features"}, t
    _by_bur = {t["key"]: t for t in bundle["tiles"]}

    # Kastanienallee 12 is in Pankow — Standesamt feature name must contain "Pankow".
    assert idx.bezirk_for(geo["lon"], geo["lat"]) == "Pankow", \
        f"expected Pankow, got {idx.bezirk_for(geo['lon'], geo['lat'])!r}"
    assert len(_by_bur["standesamt"]["features"]) == 1
    assert "Pankow" in _by_bur["standesamt"]["features"][0]["name"], \
        _by_bur["standesamt"]["features"][0]
    # LEA: exactly 1 feature (from cfg.lea_office), name contains "LEA".
    assert len(_by_bur["lea"]["features"]) == 1
    assert "LEA" in _by_bur["lea"]["features"][0]["name"]
    # Every buergeramt feature has distance_m as int (walk_min pruned —
    # frontend now renders km via fmtDistance, no per-feature walk time
    # is emitted on the Others tab).
    for f in _by_bur["buergeramt"]["features"]:
        assert isinstance(f.get("distance_m"), int), f
        assert "walk_min" not in f, f
    # Provenance non-empty; cites at minimum Bürgerämter.
    assert "Bürgerämter" in bundle["provenance"], bundle["provenance"]
    # Determinism guard — two calls must produce equal dicts.
    bundle_2 = _others_admin.build(cfg, idx, geo["lon"], geo["lat"])
    assert bundle == bundle_2, "others_admin.build must be deterministic"

    # -- Bergmannstraße 27 (Friedrichshain-Kreuzberg Bezirk) ---------------
    berg = idx.geocode("Bergmannstraße", "27", "10961")
    if not berg:
        print("  Bergmannstraße 27 geocode failed — skipped Bezirk assignment check")
    else:
        assert idx.bezirk_for(berg["lon"], berg["lat"]) == "Friedrichshain-Kreuzberg", \
            f"expected Friedrichshain-Kreuzberg, got {idx.bezirk_for(berg['lon'], berg['lat'])!r}"
        bundle_b = _others_admin.build(cfg, idx, berg["lon"], berg["lat"])
        _by_b = {t["key"]: t for t in bundle_b["tiles"]}
        assert len(_by_b["standesamt"]["features"]) == 1
        assert "Friedrichshain-Kreuzberg" in _by_b["standesamt"]["features"][0]["name"], \
            _by_b["standesamt"]["features"][0]
        # Kreuzberg is farther from Wedding (LEA) than Pankow is — LEA distance_m >= Pankow's.
        lea_pnk = _by_bur["lea"]["features"][0]["distance_m"]
        lea_kbg = _by_b["lea"]["features"][0]["distance_m"]
        assert lea_kbg >= lea_pnk, \
            f"LEA from Kreuzberg ({lea_kbg}) should be ≥ from Pankow ({lea_pnk})"

    # -- Kaaden-Ring 22 (Marzahn-Hellersdorf outer edge) -----------------
    # Regression guard for the "outer-Berlin admin tile empty" class of
    # bug (PR #77): Kaaden-Ring 22 sits >3 km from any Bürgeramt and
    # >5 km from any Arbeitsagentur, so the pre-fix radius-only loaders
    # returned zero features. The two-tier radius fallback in
    # `Index._offices_near_with_fallback` must return the single nearest
    # office instead of empty.
    #
    # Data-drift protection: if a Bürgeramt closes and the nearest for
    # this coord shifts beyond max_radius_m=15000, this assert fires
    # loudly before users see an empty tile in prod.
    kaad = idx.geocode("Kaaden-Ring", "22", "12623")
    if not kaad:
        print("  Kaaden-Ring 22 geocode failed — skipped outer-Berlin admin regression check")
    else:
        assert idx.bezirk_for(kaad["lon"], kaad["lat"]) == "Marzahn-Hellersdorf", \
            f"expected Marzahn-Hellersdorf, got {idx.bezirk_for(kaad['lon'], kaad['lat'])!r}"
        bundle_k = _others_admin.build(cfg, idx, kaad["lon"], kaad["lat"])
        _by_k = {t["key"]: t for t in bundle_k["tiles"]}
        # Both tiles that used to render empty must now surface ≥1
        # feature via the fallback branch.
        assert len(_by_k["buergeramt"]["features"]) >= 1, \
            f"Kaaden-Ring 22 Bürgeramt empty — fallback broken or nearest >15km"
        assert len(_by_k["arbeitsagentur"]["features"]) >= 1, \
            f"Kaaden-Ring 22 Arbeitsagentur empty — fallback broken or nearest >15km"
        # Sanity: the nearest office is expected OUTSIDE the primary
        # radius cap for this coord (otherwise the fallback wasn't
        # actually exercised — either the address geocoded to a
        # different point or a new central-Berlin office landed in the
        # curated list).
        _bur_d = _by_k["buergeramt"]["features"][0]["distance_m"]
        _arb_d = _by_k["arbeitsagentur"]["features"][0]["distance_m"]
        assert _bur_d > 3000, \
            f"Kaaden-Ring 22 Bürgeramt distance {_bur_d}m ≤ 3000m — " \
            f"fallback path not exercised, test no longer regression-guards"
        assert _arb_d > 5000, \
            f"Kaaden-Ring 22 Arbeitsagentur distance {_arb_d}m ≤ 5000m — " \
            f"fallback path not exercised"
        print(f"  Kaaden-Ring 22 outer-Berlin fallback OK "
              f"(Bürgeramt {_bur_d}m, Arbeitsagentur {_arb_d}m)")

    print("  admin-offices (Others tab) asserts OK")

    # -- Newcomer lens (Spec E) -----------------------------------------------
    # Two known-good Berlin addresses exercise the lens shape and broad tier
    # expectations.  Tier assertions are intentionally soft (range checks, not
    # pinned values) to survive OSM data drift and temporary rail closures.
    #
    # Bergmannstraße 27 (Friedrichshain-Kreuzberg) — dense inner district;
    # expect mostly green on transit and food, unknown on gesix_newcomer.
    #
    # Marzahner Promenade 1 (Marzahn-Hellersdorf) — outer east; English-tagged
    # OSM medical coverage is thinner at the periphery, so english_clinic
    # skews amber or red.

    # Bergmannstraße 27 — reuse `berg` geocode result from admin-offices block.
    if not berg:
        print("  Bergmannstraße 27 geocode failed — skipped newcomer Kreuzberg assert")
    else:
        _nl_k = scorer.newcomer_lens(cfg, idx, berg["lon"], berg["lat"])
        assert _nl_k.get("slug") == "newcomer", _nl_k.get("slug")
        assert set(_nl_k) >= {"slug", "label", "audience", "tiles", "provenance"}, \
            f"newcomer envelope missing keys: {set(_nl_k)}"
        _nl_tiles_k = {t["key"]: t for t in _nl_k["tiles"]}
        # Newcomer lens has grown from the original 13 tiles (added
        # parkzone, xmas_market). Assert CONTAINMENT of the original
        # core, not equality — the source of truth for exact set is
        # `app/cities/berlin.py::NEWCOMER_LENS.tiles`. A pinned equality
        # here would fire on every additive tile addition.
        _nl_core = {
            "buergeramt",
            "rail_transit", "tram_transit", "bus_transit",
            "intl_food", "coworking", "english_clinic",
            "language_school", "library", "packstation", "wochenmarkt",
            "nightlife_density",
            "gesix_newcomer",
        }
        assert _nl_core.issubset(set(_nl_tiles_k)), \
            f"newcomer lens missing core tiles: {_nl_core - set(_nl_tiles_k)} · " \
            f"full: {set(_nl_tiles_k)}"
        for _t in _nl_k["tiles"]:
            assert _t["tier"] in {"green", "amber", "red", "unknown"}, _t
            assert _t["label"], f"tile missing label: {_t}"
            assert _t["rule"], f"tile missing rule: {_t}"
        # Rail: Kreuzberg has multiple S/U stops within walking distance.
        # Softened to green-or-amber in case of a temporary closure.
        assert _nl_tiles_k["rail_transit"]["tier"] in ("green", "amber"), \
            f"expected rail_transit green/amber at Bergmannstraße 27: {_nl_tiles_k['rail_transit']}"
        # International food: Kreuzberg is one of Berlin's most international districts.
        assert _nl_tiles_k["intl_food"]["tier"] in ("green", "amber"), \
            f"expected intl_food green/amber at Bergmannstraße 27: {_nl_tiles_k['intl_food']}"
        # GESIx tile now carries a quintile-based verdict; still must be one of
        # the four canonical tiers.  Unknown = outside a Planungsraum polygon.
        assert _nl_tiles_k["gesix_newcomer"]["tier"] in ("green", "amber", "red", "unknown"), \
            f"gesix_newcomer tier invalid: {_nl_tiles_k['gesix_newcomer']}"
        # GESIx metadata key must be present (may be empty dict when outside a Planungsraum).
        assert "gesix" in _nl_tiles_k["gesix_newcomer"].get("metadata", {}), \
            f"gesix_newcomer missing metadata.gesix: {_nl_tiles_k['gesix_newcomer']}"
        print("  newcomer lens Bergmannstraße 27 asserts OK")

    # Marzahner Promenade 1 (outer east, Marzahn-Hellersdorf).
    marz = idx.geocode("Marzahner Promenade", "1", "12679")
    if not marz:
        print("  Marzahner Promenade 1 geocode failed — skipped newcomer outer-east assert")
    else:
        _nl_m = scorer.newcomer_lens(cfg, idx, marz["lon"], marz["lat"])
        assert _nl_m.get("slug") == "newcomer", _nl_m.get("slug")
        _nl_tiles_m = {t["key"]: t for t in _nl_m["tiles"]}
        # Same containment-not-equality pattern as the Kreuzberg block
        # above — additive tile drift is not a bug, source of truth is
        # `app/cities/berlin.py::NEWCOMER_LENS.tiles`.
        assert _nl_core.issubset(set(_nl_tiles_m)), \
            f"newcomer lens missing core tiles at Marzahn: " \
            f"{_nl_core - set(_nl_tiles_m)} · full: {set(_nl_tiles_m)}"
        for _t in _nl_m["tiles"]:
            assert _t["tier"] in {"green", "amber", "red", "unknown"}, _t
        # English-tagged OSM coverage thins out in outer districts; amber or red expected.
        assert _nl_tiles_m["english_clinic"]["tier"] in ("amber", "red"), \
            f"expected english_clinic amber/red at Marzahner Promenade 1: {_nl_tiles_m['english_clinic']}"
        # GESIx tile now carries a quintile-based verdict; still must be one of
        # the four canonical tiers.
        assert _nl_tiles_m["gesix_newcomer"]["tier"] in ("green", "amber", "red", "unknown"), \
            f"gesix_newcomer tier invalid: {_nl_tiles_m['gesix_newcomer']}"
        print("  newcomer lens Marzahner Promenade 1 asserts OK")

    print("  newcomer lens asserts OK")

    print("→ live selfcheck OK")


def _live_selfcheck_hamburg(cfg) -> None:
    """Live-Index smoke test for Hamburg — exercises all Hamburg WFS loaders
    against live endpoints and validates the geocode + sozialmonitoring path.

    Rationale: any 4xx / timeout / field-name mismatch surfaces here (at CI
    / `CITY=hamburg python -m app.selfcheck` time) rather than in prod.
    """
    print(f"→ Index({cfg.slug}) build …", flush=True)
    idx = Index(cfg)

    # -- Attribution keys present -------------------------------------------
    for k in ("schools", "kitas", "hospitals", "sozialmonitoring", "ferry"):
        assert k in cfg.attribution, f"missing attribution key: {k!r}"
    print("  attribution keys OK")

    # -- Loader counts (loose lower bounds) ----------------------------------
    # gesix must be empty — Hamburg uses sozialmonitoring instead.
    assert idx.gesix == [], f"gesix must be empty for Hamburg, got {len(idx.gesix)} entries"
    print(f"  gesix empty (correct for Hamburg)")

    # S/U-Bahn: HVV CSV vendored (76 S-Bahn + 70 U-Bahn in v1 extract)
    assert len(idx.sbahn) >= 60, f"expected ≥60 S-Bahn stations (HVV), got {len(idx.sbahn)}"
    assert len(idx.ubahn) >= 60, f"expected ≥60 U-Bahn stations (HVV), got {len(idx.ubahn)}"
    print(f"  S-Bahn {len(idx.sbahn)} · U-Bahn {len(idx.ubahn)} OK")

    # Ferry piers: HADAG CSV vendored
    assert len(idx.ferry) >= 10, f"expected ≥10 HADAG ferry piers, got {len(idx.ferry)}"
    print(f"  ferry piers {len(idx.ferry)} OK")

    # Regional rail: curated list (13 from landscape §3.3)
    assert len(idx.regional_rail) >= 13, \
        f"expected ≥13 regional rail stations, got {len(idx.regional_rail)}"
    print(f"  regional rail {len(idx.regional_rail)} OK")

    # Kitas: Hamburg BAGFI WFS
    assert len(idx.kitas) >= 500, f"expected ≥500 Hamburg Kitas, got {len(idx.kitas)}"
    print(f"  kitas {len(idx.kitas)} OK")

    # Hospitals: Hamburg BWGV WFS
    assert len(idx.hospitals) >= 20, f"expected ≥20 hospitals, got {len(idx.hospitals)}"
    print(f"  hospitals {len(idx.hospitals)} OK")

    # Public Grundschulen (gs_public) — Hamburg uses kapitelbezeichnung="Grundschulen"
    # (plural) for filtering; schools WFS serves 208 Grundschulen in state schools.
    assert len(idx.gs_public) >= 150, f"expected ≥150 public primary schools, got {len(idx.gs_public)}"
    print(f"  gs_public {len(idx.gs_public)} OK")

    # Sozialmonitoring: Hamburg BSW WFS
    assert len(idx.sozialmonitoring) >= 400, \
        f"expected ≥400 Statistische Gebiete, got {len(idx.sozialmonitoring)}"
    print(f"  sozialmonitoring {len(idx.sozialmonitoring)} Statistische Gebiete OK")

    # -- Geocode Lange Reihe 1, 20099 Hamburg (St. Georg) ----------------------
    # Note: Rathausmarkt / government-zone statgebs are excluded from
    # Hamburg's BSW Sozialmonitoring (commercial-core Statistische Gebiete have
    # no residential population to monitor). Lange Reihe 1 (St. Georg) is a
    # well-known residential address in Hamburg-Mitte with confirmed coverage.
    geo = idx.geocode("Lange Reihe", "1", "20099")
    assert geo, "Lange Reihe 1, 20099 Hamburg must geocode via OAF GAGES endpoint"
    lon, lat = geo["lon"], geo["lat"]
    # Sanity check: must be in central Hamburg bounding box
    assert 53.54 < lat < 53.57, f"lat {lat} outside central Hamburg range"
    assert 9.98 < lon < 10.02, f"lon {lon} outside central Hamburg range"
    print(f"  geocode Lange Reihe 1 → ({lon:.5f}, {lat:.5f}) OK")

    # -- Sozialmonitoring lookup at St. Georg --------------------------------
    sm = idx.sozialmonitoring_at(lon, lat)
    assert sm is not None, "sozialmonitoring_at must return a result for Lange Reihe 1 (St. Georg)"
    assert sm.get("statusindex"), f"statusindex must be non-empty: {sm}"
    assert sm.get("stadtteil"), f"stadtteil must be non-empty: {sm}"
    print(f"  sozialmonitoring_at → stadtteil={sm['stadtteil']!r} "
          f"statusindex={sm['statusindex']!r} OK")

    # -- Nearest school (Hamburg-simple distance-only path) ------------------
    school_res = idx.nearest_school_km_only(lon, lat)
    assert school_res is not None, "nearest_school_km_only must return a result"
    assert "distance_km" in school_res, f"result shape wrong: {school_res}"
    assert 0 < school_res["distance_km"] < 5, \
        f"nearest school from Lange Reihe 1 should be <5 km, got {school_res}"
    print(f"  nearest_school_km_only → {school_res['distance_km']} km OK")

    # -- Nearest ferry pier --------------------------------------------------
    ferry_res = idx.nearest_ferry(lon, lat)
    assert ferry_res is not None, "nearest_ferry must return a result"
    assert ferry_res.get("distance_m", 0) < 5000, \
        f"nearest ferry from Lange Reihe 1 should be <5 km, got {ferry_res}"
    print(f"  nearest_ferry → {ferry_res['name']!r} {ferry_res['distance_m']} m OK")

    # -- Bezirk lookup -------------------------------------------------------
    bezirk = idx.bezirk_for(lon, lat)
    assert bezirk, f"bezirk_for must return a name for Lange Reihe 1, got {bezirk!r}"
    print(f"  bezirk_for → {bezirk!r} OK")

    # -- Standesamt for St. Georg (Hamburg-Mitte) ----------------------------
    sa = idx.standesamt_for(lon, lat)
    assert sa is not None, "standesamt_for must return a result for Lange Reihe 1"
    assert "Mitte" in sa.get("name", ""), f"expected Standesamt Mitte (Hamburg-Mitte), got {sa}"
    print(f"  standesamt_for → {sa['name']!r} OK")

    # -- Newcomer + Commuter lens composers ----------------------------------
    # Exercises the conditional-guard refactor from PR #81 fix wave.
    # Before the fix: both called threw KeyError on Hamburg config (Berlin-only
    # tile keys e.g. 'xmas_market', 'commuter_tram_transit' were hardcoded).
    nl = scorer.newcomer_lens(cfg, idx, lon, lat, amenities={})
    assert nl.get("slug") == "newcomer", f"newcomer slug wrong: {nl.get('slug')}"
    _nl_keys = {t["key"] for t in nl["tiles"]}
    for _req in ("ferry_transit", "sozialmonitoring_status", "sozialmonitoring_gesamt"):
        assert _req in _nl_keys, f"Hamburg newcomer tile {_req!r} missing: {_nl_keys}"
    for _banned in ("xmas_market", "tram_transit", "gesix_newcomer"):
        assert _banned not in _nl_keys, f"Berlin tile {_banned!r} leaked into Hamburg newcomer: {_nl_keys}"
    for _t in nl["tiles"]:
        assert _t.get("tier") in {"green", "amber", "red", "unknown"}, \
            f"newcomer tile {_t.get('key')!r} has invalid tier: {_t.get('tier')!r}"
    print(f"  newcomer_lens → {len(nl['tiles'])} tiles, slug={nl['slug']!r} OK")

    cl = scorer.commuter_lens(cfg, idx, lon, lat, amenities={})
    assert cl.get("slug") == "commuter", f"commuter slug wrong: {cl.get('slug')}"
    _cl_keys = {t["key"] for t in cl["tiles"]}
    for _req in ("commuter_ferry_transit", "sozialmonitoring_status_commuter", "sozialmonitoring_gesamt_commuter"):
        assert _req in _cl_keys, f"Hamburg commuter tile {_req!r} missing: {_cl_keys}"
    for _banned in ("commuter_tram_transit", "gesix_commuter"):
        assert _banned not in _cl_keys, f"Berlin tile {_banned!r} leaked into Hamburg commuter: {_cl_keys}"
    for _t in cl["tiles"]:
        assert _t.get("tier") in {"green", "amber", "red", "unknown"}, \
            f"commuter tile {_t.get('key')!r} has invalid tier: {_t.get('tier')!r}"
    print(f"  commuter_lens → {len(cl['tiles'])} tiles, slug={cl['slug']!r} OK")

    print("→ live selfcheck OK")


def run_live_selfcheck() -> None:
    """Dispatch to the city-specific live selfcheck path."""
    cfg = load_city()
    if cfg.slug == "berlin":
        _live_selfcheck_berlin(cfg)
    elif cfg.slug == "hamburg":
        _live_selfcheck_hamburg(cfg)
    else:
        print(f"live selfcheck: no smoke path for CITY={cfg.slug!r}")


def main() -> None:
    run_cities_isolation()
    print("\n=== pure module selfchecks ===")
    run_pure_selfchecks()
    print("\n=== live selfcheck (network) ===")
    run_live_selfcheck()
    print("\nselfcheck: OK")


if __name__ == "__main__":
    main()
