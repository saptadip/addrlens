"""Historical monolith — split into `app.core.scoring` + `app.core.lenses`
in Ship D step 2. Kept as a re-export shim so existing callers
(`app.routes.lookup`, `app.routes.noise`, `app.selfcheck`) don't have to
learn the new layout in one PR, and to host the load-bearing regression
selfcheck that exercises every submodule together.

New code should import from the split modules directly:

- `from app.core.lenses.young_family import young_family_lens`
- `from app.core.lenses.newcomer     import newcomer_lens`
- `from app.core.scoring.tiers       import noise_tier, stroller_score, ...`
- `from app.core.scoring.shape       import _shape_kita, ...`

The `_tier_*` and `_shape_*` names re-exported here are intended for
the __main__ selfcheck below and for the (few) existing callers that
still address them via the `scorer` namespace. New code should not
grow that surface.
"""

# ------------------------- Public API -------------------------
from app.core.lenses.commuter import commuter_lens                     # noqa: F401
from app.core.lenses.newcomer import newcomer_lens                     # noqa: F401
from app.core.lenses.quiet_living import quiet_living_lens             # noqa: F401
from app.core.lenses.young_family import young_family_lens             # noqa: F401
from app.core.scoring.tiers import noise_tier, stroller_score          # noqa: F401

# ------------------------- Internals re-exported for selfcheck ------
from app.core.scoring.constants import (                                # noqa: F401
    TIER_AMBER, TIER_GREEN, TIER_RED, TIER_UNKNOWN,
    _fmt_dist, _walk_minutes,
)
from app.core.scoring.legends import _legend_for                        # noqa: F401
from app.core.scoring.provenance import _lens_provenance, _sources_for  # noqa: F401
from app.core.scoring.shape import (                                    # noqa: F401
    _int_or_none, _prune, _shape_gesix, _shape_kita, _shape_office,
    _shape_osm_feature, _shape_paediatric_gp, _shape_playground,
    _shape_refuge_quiet, _shape_refuge_trees, _shape_supermarket,
    _shape_transit_stop, _tile, _valid_latlon,
)
from app.core.scoring.tiers import (                                    # noqa: F401
    _tier_air, _tier_buergeramt_newcomer, _tier_bus_transit,
    _tier_coworking, _tier_english_clinic, _tier_from_walk, _tier_gesix,
    _tier_heat, _tier_intl_food, _tier_kita, _tier_language_school,
    _tier_library, _tier_nightlife_density, _tier_noise, _tier_packstation,
    _tier_pediatrician, _tier_playground, _tier_rail_transit,
    _tier_refuge, _tier_supermarket, _tier_tram_transit, _tier_transit,
    _tier_wochenmarkt,
)


if __name__ == "__main__":
    # ==============================================================
    # Regression selfcheck. Every assertion below is preserved verbatim
    # from the pre-split scorer.py and exercises the split modules
    # through their re-exported names. If a module is refactored again
    # in future, this block is the single source of truth for the
    # response shapes the SPA and Life Mode depend on.
    # ==============================================================

    # noise_tier — thresholds copied verbatim from phase3/server.py:_selfcheck.
    assert noise_tier(50)   == "green"
    assert noise_tier(60)   == "amber"
    assert noise_tier(68)   == "orange"
    assert noise_tier(75)   == "red"
    assert noise_tier(None) == "unknown"

    # stroller_score — rule-based, must stay in sync with the JS mirror.
    assert stroller_score(None, True, False, 300)["tier"] == "unknown"
    assert stroller_score(0, False, False, 300)["tier"] == "green"
    assert stroller_score(3, True,  False, 300)["tier"] == "green"
    assert stroller_score(2, False, False, 300)["tier"] == "amber"
    assert stroller_score(4, False, False, 300)["tier"] == "red"
    assert stroller_score(4, False, True,  300)["tier"] == "amber", \
        "Kinderwagenraum should rescue a 4th-floor walk-up from red to amber"
    assert stroller_score(2, False, True,  300)["tier"] == "green", \
        "Kinderwagenraum should lift a 2nd-floor walk-up from amber to green"
    assert stroller_score(0, True, False, 1200)["tier"] == "amber", \
        "no playground within 800m should downgrade an otherwise green flat"
    r = stroller_score(3, False, False, 300)
    assert any("hard no" in x["text"] for x in r["reasons"])
    print("scorer.py selfcheck OK")

    # -- Young Family lens: boundary sweeps (Spec A pure selfcheck) ----------
    from app.cities.berlin import BERLIN as _CFG_YF
    _T = {t.key: t.thresholds for t in _CFG_YF.young_family_lens.tiles}

    # Kita — inclusive on greener side.
    at_400 = [{"distance_m": 400}, {"distance_m": 350}, {"distance_m": 100}]
    at_401 = [{"distance_m": 401}, {"distance_m": 402}, {"distance_m": 403}]
    assert _tier_kita(at_400, _T["kita"])["tier"] == TIER_GREEN
    assert _tier_kita(at_401, _T["kita"])["tier"] == TIER_AMBER
    assert _tier_kita([{"distance_m": 800}], _T["kita"])["tier"] == TIER_AMBER
    assert _tier_kita([{"distance_m": 801}], _T["kita"])["tier"] == TIER_RED
    assert _tier_kita([], _T["kita"])["tier"] == TIER_RED

    # Playground.
    assert _tier_playground([{"distance_m": 400}], False, _T["playground"])["tier"] == TIER_GREEN
    assert _tier_playground([{"distance_m": 401}], False, _T["playground"])["tier"] == TIER_AMBER
    assert _tier_playground([{"distance_m": 801}], False, _T["playground"])["tier"] == TIER_RED
    assert _tier_playground([], True, _T["playground"])["tier"] == TIER_UNKNOWN

    # Pediatrician.
    P800 = [{"distance_m": 800, "name": "Dr. X"}]
    P801 = [{"distance_m": 801, "name": "Dr. Y"}]
    P1500 = [{"distance_m": 1500, "name": "Dr. Z"}]
    P1501 = [{"distance_m": 1501, "name": "Dr. W"}]
    assert _tier_pediatrician(P800, False, _T["pediatrician"])["tier"] == TIER_GREEN
    assert _tier_pediatrician(P801, False, _T["pediatrician"])["tier"] == TIER_AMBER
    assert _tier_pediatrician(P1500, False, _T["pediatrician"])["tier"] == TIER_AMBER
    assert _tier_pediatrician(P1501, False, _T["pediatrician"])["tier"] == TIER_RED
    assert _tier_pediatrician([], True, _T["pediatrician"])["tier"] == TIER_UNKNOWN

    # Noise — inclusive on greener side (55 is green, 55.01 is amber).
    assert _tier_noise({"l_den": {"total": 55}}, _T["noise"])["tier"] == TIER_GREEN
    assert _tier_noise({"l_den": {"total": 55.01}}, _T["noise"])["tier"] == TIER_AMBER
    assert _tier_noise({"l_den": {"total": 60}}, _T["noise"])["tier"] == TIER_AMBER
    assert _tier_noise({"l_den": {"total": 60.01}}, _T["noise"])["tier"] == TIER_RED
    assert _tier_noise({"unavailable": True}, _T["noise"])["tier"] == TIER_UNKNOWN

    # Heat — bare class labels.
    assert _tier_heat({"day_class": "geringe Belastung"}, _T["heat"])["tier"] == TIER_GREEN
    assert _tier_heat({"day_class": "starke Belastung"}, _T["heat"])["tier"] == TIER_AMBER
    assert _tier_heat({"day_class": "sehr starke Belastung"}, _T["heat"])["tier"] == TIER_RED
    assert _tier_heat({"day_class": "extreme Belastung"}, _T["heat"])["tier"] == TIER_RED
    assert _tier_heat({"unavailable": True}, _T["heat"])["tier"] == TIER_UNKNOWN

    # Heat — real Umweltatlas prefix format.
    assert _tier_heat({"day_class": "> 33 °C - <= 35 °C - mäßige Belastung"}, _T["heat"])["tier"] == TIER_AMBER
    assert _tier_heat({"day_class": "<= 33 °C - geringe Belastung"}, _T["heat"])["tier"] == TIER_GREEN
    assert _tier_heat({"day_class": "> 35 °C - sehr starke Belastung"}, _T["heat"])["tier"] == TIER_RED

    # Air — inclusive on greener side.
    assert _tier_air({"no2_ugm3": 20}, _T["air"])["tier"] == TIER_GREEN
    assert _tier_air({"no2_ugm3": 20.01}, _T["air"])["tier"] == TIER_AMBER
    assert _tier_air({"no2_ugm3": 40}, _T["air"])["tier"] == TIER_AMBER
    assert _tier_air({"no2_ugm3": 40.01}, _T["air"])["tier"] == TIER_RED
    assert _tier_air({"unavailable": True}, _T["air"])["tier"] == TIER_UNKNOWN

    # Refuge — composite OR. Threshold anchors retuned to Straßenbäume
    # physics (green_crown_pct=10, amber_crown_pct=5) so both legs of
    # the OR-composite are actually reachable in Berlin.
    #
    # Quiet-zone green rescues low canopy.
    assert _tier_refuge({"distance_m": 400, "name": "Volkspark"},
                        {"crown_coverage_pct": 3},
                        _T["refuge"])["tier"] == TIER_GREEN
    # Canopy green rescues distant quiet zone.
    assert _tier_refuge({"distance_m": 2000},
                        {"crown_coverage_pct": 12},
                        _T["refuge"])["tier"] == TIER_GREEN
    # Canopy pinned at green boundary (10%) with quiet-zone red.
    assert _tier_refuge({"distance_m": 2000},
                        {"crown_coverage_pct": 10},
                        _T["refuge"])["tier"] == TIER_GREEN
    # Canopy amber-band (5–9%) with quiet-zone red → composite amber.
    assert _tier_refuge({"distance_m": 2000},
                        {"crown_coverage_pct": 7},
                        _T["refuge"])["tier"] == TIER_AMBER
    # Canopy pinned at amber boundary (5%) with quiet-zone red → amber.
    assert _tier_refuge({"distance_m": 2000},
                        {"crown_coverage_pct": 5},
                        _T["refuge"])["tier"] == TIER_AMBER
    # Canopy below amber (4%) with quiet-zone red → composite red.
    assert _tier_refuge({"distance_m": 2000},
                        {"crown_coverage_pct": 4},
                        _T["refuge"])["tier"] == TIER_RED
    # Quiet-zone amber (400–1000 m) with canopy red → composite amber.
    assert _tier_refuge({"distance_m": 800},
                        {"crown_coverage_pct": 4},
                        _T["refuge"])["tier"] == TIER_AMBER
    assert _tier_refuge(None, None, _T["refuge"])["tier"] == TIER_UNKNOWN
    print("scorer.py: young_family tier boundary sweeps OK")

    # -- Sources composition + de-dup order --------------------------------
    _fake_tiles = [
        {"sources": ["A", "B"]},
        {"sources": []},
        {"sources": ["B", "C", "A"]},
        {"sources": None},
    ]
    assert _lens_provenance(_CFG_YF, _fake_tiles) == "A · B · C"
    assert _lens_provenance(_CFG_YF, [{"sources": []}, {"sources": None}]) == ""

    # -- Caveat pass-through -----------------------------------------------
    _caveats = {t.key: t.caveat for t in _CFG_YF.young_family_lens.tiles}
    assert _caveats["pediatrician"], "pediatrician tile must carry a caveat"
    assert _caveats["kita"] == "" and _caveats["noise"] == ""

    # -- Empty-but-available inputs → red.
    class _StubIndex:
        sbahn = ubahn = tram = []
        def kitas_near_bod(self, lon, lat, r): return []
        def nearest_station(self, points, lon, lat): return None
        def gesix_at(self, lon, lat): return None
    _empty_result = young_family_lens(
        _CFG_YF, _StubIndex(), 13.4, 52.5,
        air={"no2_ugm3": 60}, heat={"day_class": "extreme Belastung"},
        noise={"l_den": {"total": 70}},
        amenities={"playgrounds": {"items": []}, "gps": {"items": []}},
        # `crown_coverage_pct=2` sits below the retuned amber_crown_pct=5
        # threshold so this "empty-but-available" case still yields RED on
        # the refuge composite (both quiet-leg and canopy-leg fail).
        trees={"crown_coverage_pct": 2},
        quiet_zone={"distance_m": 5000},
    )
    _tiers = {t["key"]: t["tier"] for t in _empty_result["tiles"]}
    assert _tiers.pop("transit") == TIER_UNKNOWN, _tiers
    assert _tiers.pop("gesix")   == TIER_UNKNOWN, _tiers
    assert all(v == TIER_RED for v in _tiers.values()), _tiers

    # -- Unavailable inputs → unknown where possible.
    _unavail_result = young_family_lens(
        _CFG_YF, _StubIndex(), 13.4, 52.5,
        air={"unavailable": True}, heat={"unavailable": True},
        noise={"unavailable": True},
        amenities={"playgrounds": {"items": [], "error": "overpass timeout"},
                   "gps":         {"items": [], "error": "overpass timeout"}},
        trees=None, quiet_zone=None,
    )
    _u = {t["key"]: t["tier"] for t in _unavail_result["tiles"]}
    assert _u["noise"]        == TIER_UNKNOWN
    assert _u["heat"]         == TIER_UNKNOWN
    assert _u["air"]          == TIER_UNKNOWN
    assert _u["playground"]   == TIER_UNKNOWN
    assert _u["pediatrician"] == TIER_UNKNOWN
    assert _u["refuge"]       == TIER_UNKNOWN
    assert _u["kita"]         == TIER_RED

    _base_keys = {"key","label","icon","tier","rule","numeric","caveat","sources","features"}
    for t in _unavail_result["tiles"]:
        assert _base_keys <= set(t.keys()), t
    _refuge_u = next(t for t in _unavail_result["tiles"] if t["key"] == "refuge")
    assert "metadata" in _refuge_u and "trees" in _refuge_u["metadata"]
    assert _unavail_result["slug"]     == "young_family"
    assert _unavail_result["label"]    == "Young Family (0–6)"
    assert _unavail_result["audience"] == "For a family with kids under 6"
    assert "Kindertagesstätten" in _unavail_result["provenance"], _unavail_result["provenance"]

    # -- Spec D: features on young_family output.
    _r_full = young_family_lens(
        _CFG_YF, _StubIndex(), 13.4, 52.5,
        air={"no2_ugm3": 15}, heat={"day_class": "geringe Belastung"},
        noise={"l_den": {"total": 50}},
        amenities={"playgrounds": {"items": [
            {"name": "P1", "lat": 52.5, "lon": 13.4, "distance_m": 350,
             "props": {"katasterfl": 500}}]},
                   "gps": {"items": []}},
        trees={"count": 40, "crown_coverage_pct": 30,
               "top_species": [{"name":"Silberlinde","n":10}]},
        quiet_zone={"name": "Q", "lat": 52.5, "lon": 13.4, "distance_m": 380},
    )
    _by = {t["key"]: t for t in _r_full["tiles"]}
    for k in ["kita","playground","pediatrician","noise","heat","air","refuge"]:
        assert "features" in _by[k], f"{k} missing features"
    assert _by["noise"]["features"] == []
    assert _by["heat"]["features"]  == []
    assert _by["air"]["features"]   == []
    assert "metadata" in _by["refuge"]
    assert "trees" in _by["refuge"]["metadata"]
    assert _by["playground"]["features"] == [
        {"name":"P1","lat":52.5,"lon":13.4,"distance_m":350,"area_m2":500}]
    assert len(_by["refuge"]["features"]) == 1
    assert _by["refuge"]["features"][0]["name"] == "Q"

    _r_no_quiet = young_family_lens(
        _CFG_YF, _StubIndex(), 13.4, 52.5,
        air={"no2_ugm3": 15}, heat={"day_class": "geringe Belastung"},
        noise={"l_den": {"total": 50}},
        amenities={"playgrounds": {"items": []}, "gps": {"items": []}},
        trees={"count": 40, "crown_coverage_pct": 30},
        quiet_zone={"name":"Far","lat":52.6,"lon":13.5,"distance_m":5000},
    )
    _rf = next(t for t in _r_no_quiet["tiles"] if t["key"] == "refuge")
    assert _rf["features"] == []
    assert _rf["metadata"]["trees"]["crown_coverage_pct"] == 30

    print("scorer.py: young_family composer + provenance OK")

    # -- _walk_minutes sanity.
    assert _walk_minutes(0)   == 0.0
    assert _walk_minutes(62)  == 1.0
    assert abs(_walk_minutes(930) - 15.0) < 1e-9

    # -- Spec D shape helpers.
    assert _prune({"a":"x","b":None,"c":"","d":0,"e":False,"f":[],"g":{}}) \
        == {"a":"x","d":0,"e":False,"f":[],"g":{}}
    assert _int_or_none("65") == 65
    assert _int_or_none(65)   == 65
    assert _int_or_none(None) is None
    assert _int_or_none("")   is None
    assert _int_or_none("abc") is None
    assert _valid_latlon({"lat": 52.5, "lon": 13.4}) is True
    assert _valid_latlon({"lat": 100.0, "lon": 13.4}) is False
    assert _valid_latlon({"lat": None, "lon": 13.4})  is False
    assert _valid_latlon({"lat": 52.5})                is False

    _fm_k = _CFG_YF.kita_field_map
    _raw = {"name": "Kita Sonnenschein",
            "lat": 52.5388, "lon": 13.3948, "distance_m": 180,
            "props": {_fm_k["capacity"]: "65",
                      _fm_k["operator_type"]: "freie Träger",
                      _fm_k["approach"]: "Situationsansatz"}}
    assert _shape_kita(_raw, _fm_k) == {
        "name": "Kita Sonnenschein",
        "lat": 52.5388, "lon": 13.3948, "distance_m": 180,
        "capacity": 65, "operator_type": "freie Träger",
        "approach": "Situationsansatz"}
    assert _shape_kita({"name": "", "lat": 52.5, "lon": 13.4,
                        "distance_m": 100, "props": {}}, _fm_k) is None
    assert _shape_kita({"name": "X", "distance_m": 100, "props": {}}, _fm_k) is None

    _pg = {"name": "Marheinekeplatz, Spiel", "lat": 52.489, "lon": 13.396,
           "distance_m": 75, "props": {"katasterfl": 446, "sanierjahr": "2018"}}
    assert _shape_playground(_pg) == {
        "name": "Marheinekeplatz, Spiel",
        "lat": 52.489, "lon": 13.396, "distance_m": 75,
        "area_m2": 446, "renovated_year": 2018}
    _pg_bare = {"name": "P2", "lat": 52.5, "lon": 13.4, "distance_m": 200,
                "props": {}}
    assert _shape_playground(_pg_bare) == {
        "name": "P2", "lat": 52.5, "lon": 13.4, "distance_m": 200}

    _gp = {"name": "Praxis für Kinderheilkunde Dr. Berns",
           "lat": 52.4893, "lon": 13.3889, "distance_m": 430,
           "tags": {"addr:street": "Bergmannstraße", "addr:housenumber": "5",
                    "addr:postcode": "10961", "addr:city": "Berlin",
                    "phone": "+49 30 693 80 05",
                    "website": "https://kinderarztpraxis-berns.de",
                    "opening_hours": "Mo-Fr 09:00-12:00; Mo,Tu,Th 15:00-18:00",
                    "wheelchair": "yes"}}
    _rgp = _shape_paediatric_gp(_gp)
    assert _rgp["address"] == "Bergmannstraße 5, 10961 Berlin"
    assert _rgp["phone"]   == "+49 30 693 80 05"
    assert _rgp["website"] == "https://kinderarztpraxis-berns.de"
    assert _rgp["hours"].startswith("Mo-Fr")
    assert _rgp["wheelchair"] is True
    _gp2 = {**_gp, "tags": {**_gp["tags"], "wheelchair": "limited"}}
    assert "wheelchair" not in _shape_paediatric_gp(_gp2)

    _off = {"name": "Bürgeramt X",
            "address": "Y-Str. 1, 10000 Berlin",
            "lat": 52.5, "lon": 13.4, "distance_m": 620,
            "website": "https://x.example/"}
    _roff = _shape_office(_off)
    assert _roff["walk_min"] == 10
    assert _roff["website"]  == "https://x.example/"

    _q_within = {"name": "Volkspark", "lat": 52.53, "lon": 13.42,
                 "distance_m": 350, "size_ha": 29, "kind": "Erholungsgebiet"}
    assert _shape_refuge_quiet(_q_within, 1000) == [{
        "name": "Volkspark", "lat": 52.53, "lon": 13.42,
        "distance_m": 350, "size_ha": 29, "kind": "Erholungsgebiet"}]
    assert _shape_refuge_quiet({"name": "Far", "lat": 52.6, "lon": 13.5,
                                "distance_m": 5000}, 1000) == []
    assert _shape_refuge_quiet(None, 1000) == []

    _tr = {"count": 42, "avg_age_yr": 35, "tallest_m": 22,
           "crown_coverage_pct": 27,
           "top_species": [{"name":"Silberlinde","n":12},
                           {"name":"Winterlinde","n":8},
                           {"name":"","n":0}]}
    _rtr = _shape_refuge_trees(_tr)
    assert _rtr["count"] == 42
    assert _rtr["top_species"] == [{"name":"Silberlinde","n":12},
                                    {"name":"Winterlinde","n":8}]
    assert _shape_refuge_trees({"error": "trees down"}) == {}
    assert _shape_refuge_trees(None) == {}

    print("scorer.py: Spec D shape helpers OK")

    # -- _shape_gesix.
    class _StubCfg:
        attribution = {"gesix": "Berlin Geoportal — GESIx 2022 · dl-de/by-2-0"}
    class _StubGesix:
        def gesix_at(self, lon, lat):
            return {"plr_name": "X", "quintile_5": 3, "rang": 200, "total": 447}
    _sg = _shape_gesix(_StubCfg(), _StubGesix(), 52.5, 13.4)
    assert _sg["key"]  == "gesix"
    assert _sg["tier"] == TIER_AMBER
    assert _sg["metadata"]["gesix"]["quintile_5"] == 3
    assert _sg["icon"]     == "gesix"
    assert _sg["label"]    == "Neighbourhood profile"
    assert _sg["features"] == []
    assert _sg["caveat"]   == ""
    assert _sg["sources"]  == ["Berlin Geoportal — GESIx 2022 · dl-de/by-2-0"]
    assert _sg["sources"]  != ["gesix"]

    _sg2 = _shape_gesix(_StubCfg(), _StubGesix(), 52.5, 13.4,
                        card_key="gesix_newcomer",
                        label="Neighbourhood profile")
    assert _sg2["key"]  == "gesix_newcomer"
    assert _sg2["tier"] == TIER_AMBER
    assert _sg2["metadata"]["gesix"]["quintile_5"] == 3
    assert _sg2["sources"] == ["Berlin Geoportal — GESIx 2022 · dl-de/by-2-0"]

    class _StubGQ:
        def __init__(self, q): self.q = q
        def gesix_at(self, lon, lat):
            return {"plr_name": "X", "quintile_5": self.q, "rang": 100, "total": 447}
    assert _shape_gesix(_StubCfg(), _StubGQ(1), 52.5, 13.4)["tier"] == TIER_GREEN
    assert _shape_gesix(_StubCfg(), _StubGQ(2), 52.5, 13.4)["tier"] == TIER_GREEN
    assert _shape_gesix(_StubCfg(), _StubGQ(3), 52.5, 13.4)["tier"] == TIER_AMBER
    assert _shape_gesix(_StubCfg(), _StubGQ(4), 52.5, 13.4)["tier"] == TIER_RED
    assert _shape_gesix(_StubCfg(), _StubGQ(5), 52.5, 13.4)["tier"] == TIER_RED

    class _StubGesixNone:
        def gesix_at(self, lon, lat): return None
    _sg_none = _shape_gesix(_StubCfg(), _StubGesixNone(), 52.5, 13.4)
    assert _sg_none["key"]      == "gesix"
    assert _sg_none["tier"]     == TIER_UNKNOWN
    assert _sg_none["metadata"] == {"gesix": {}}
    assert _sg_none["features"] == []

    print("scorer.py: _shape_gesix selfcheck OK")

    # ==============================================================
    # Newcomer tier + composer selfchecks.
    # ==============================================================

    _t0 = _tile("k", "L", "i", tier="green", rule="r")
    assert _t0["key"] == "k" and _t0["tier"] == "green"
    assert _t0["features"] == [] and _t0["sources"] == []
    assert "metadata" not in _t0
    _t1 = _tile("k", "L", "i", tier="green", rule="r", metadata={"x": 1})
    assert "metadata" in _t1 and _t1["metadata"]["x"] == 1

    _osm_ok = {"lat": 52.5, "lon": 13.4, "distance_m": 400, "source": "osm",
               "name": "Grocery X",
               "tags": {"addr:street": "Bergmannstraße", "addr:housenumber": "5",
                        "opening_hours": "Mo-Su 08:00-20:00"}}
    _so = _shape_osm_feature(_osm_ok)
    assert _so is not None
    assert _so["name"] == "Grocery X"
    assert _so["distance_m"] == 400
    assert _so["hours"] == "Mo-Su 08:00-20:00"
    assert isinstance(_so["walk_min"], int)
    assert _shape_osm_feature({"lon": 13.4, "distance_m": 100}) is None
    _osm_noname = {"lat": 52.5, "lon": 13.4, "distance_m": 200, "source": "osm",
                   "tags": {"amenity": "restaurant"}}
    assert _shape_osm_feature(_osm_noname)["name"] == "restaurant"

    _TN = {t.key: t.thresholds for t in _CFG_YF.newcomer_lens.tiles}

    _B_f = lambda d: [{"name": "BA-Test", "lat": 52.5, "lon": 13.4,
                        "distance_m": d}]
    assert _tier_buergeramt_newcomer(_B_f(1500), _TN["buergeramt"])["tier"] == TIER_GREEN
    assert _tier_buergeramt_newcomer(_B_f(1501), _TN["buergeramt"])["tier"] == TIER_AMBER
    assert _tier_buergeramt_newcomer(_B_f(3000), _TN["buergeramt"])["tier"] == TIER_AMBER
    assert _tier_buergeramt_newcomer(_B_f(3001), _TN["buergeramt"])["tier"] == TIER_RED
    assert _tier_buergeramt_newcomer([],         _TN["buergeramt"])["tier"] == TIER_RED
    _bn = _tier_buergeramt_newcomer(_B_f(1000), _TN["buergeramt"])
    assert "1000" in _bn["numeric"] and "BA-Test" in _bn["numeric"]

    _TRN = _TN["rail_transit"]
    def _tr_f(mode, d):
        return [{"name": "Ost", "lat": 52.5, "lon": 13.4,
                 "distance_m": d, "mode": mode}]
    assert _tier_rail_transit(_tr_f("S", 800), _TRN)["tier"] == TIER_GREEN
    assert _tier_rail_transit(_tr_f("S", 801), _TRN)["tier"] == TIER_AMBER
    assert _tier_rail_transit(_tr_f("U", 500), _TRN)["tier"] == TIER_GREEN
    assert _tier_rail_transit(_tr_f("U", 501), _TRN)["tier"] == TIER_AMBER
    assert _tier_rail_transit([],              _TRN)["tier"] == TIER_RED

    _TTM = _TN["tram_transit"]
    def _tm_f(d):
        return [{"name": "TramStop", "lat": 52.5, "lon": 13.4, "distance_m": d}]
    assert _tier_tram_transit(_tm_f(500),  _TTM)["tier"] == TIER_GREEN
    assert _tier_tram_transit(_tm_f(501),  _TTM)["tier"] == TIER_AMBER
    assert _tier_tram_transit(_tm_f(1000), _TTM)["tier"] == TIER_AMBER
    assert _tier_tram_transit(_tm_f(1001), _TTM)["tier"] == TIER_RED
    assert _tier_tram_transit([],          _TTM)["tier"] == TIER_RED

    _TBS = _TN["bus_transit"]
    def _bs_f(d):
        return [{"name": "BusStop", "lat": 52.5, "lon": 13.4, "distance_m": d}]
    assert _tier_bus_transit(_bs_f(300),  _TBS)["tier"] == TIER_GREEN
    assert _tier_bus_transit(_bs_f(301),  _TBS)["tier"] == TIER_AMBER
    assert _tier_bus_transit(_bs_f(600),  _TBS)["tier"] == TIER_AMBER
    assert _tier_bus_transit(_bs_f(601),  _TBS)["tier"] == TIER_RED
    assert _tier_bus_transit([],          _TBS)["tier"] == TIER_RED

    _TIF = _TN["intl_food"]
    _ff  = lambda n: [{"name": f"Shop{i}", "lat": 52.5, "lon": 13.4,
                        "distance_m": 100}      for i in range(n)]
    assert _tier_intl_food(_ff(6),  _TIF)["tier"] == TIER_GREEN
    assert _tier_intl_food(_ff(5),  _TIF)["tier"] == TIER_AMBER
    assert _tier_intl_food(_ff(2),  _TIF)["tier"] == TIER_AMBER
    assert _tier_intl_food(_ff(1),  _TIF)["tier"] == TIER_RED
    assert _tier_intl_food([],      _TIF)["tier"] == TIER_RED
    _tn_r = _tier_intl_food(_ff(3), _TIF)
    assert "3" in _tn_r["numeric"] and str(_TIF["radius_m"]) in _tn_r["numeric"]

    _TCW = _TN["coworking"]
    _cf  = lambda n: [{"name": f"Desk{i}", "lat": 52.5, "lon": 13.4,
                        "distance_m": 200}      for i in range(n)]
    assert _tier_coworking(_cf(3), _TCW)["tier"] == TIER_GREEN
    assert _tier_coworking(_cf(2), _TCW)["tier"] == TIER_AMBER
    assert _tier_coworking(_cf(1), _TCW)["tier"] == TIER_AMBER
    assert _tier_coworking([],     _TCW)["tier"] == TIER_RED

    _TEC = _TN["english_clinic"]
    _ef  = lambda d: [{"name": "Clinic", "lat": 52.5, "lon": 13.4, "distance_m": d}]
    assert _tier_english_clinic(_ef(1000), _TEC)["tier"] == TIER_GREEN
    assert _tier_english_clinic(_ef(1001), _TEC)["tier"] == TIER_AMBER
    assert _tier_english_clinic(_ef(3000), _TEC)["tier"] == TIER_AMBER
    assert _tier_english_clinic(_ef(3001), _TEC)["tier"] == TIER_RED
    assert _tier_english_clinic([],        _TEC)["tier"] == TIER_RED

    _mkf = lambda d, name="X": [{"name": name, "lat": 52.5, "lon": 13.4, "distance_m": d}]
    _TLS = _TN["language_school"]
    assert _tier_language_school(_mkf(1500), _TLS)["tier"] == TIER_GREEN
    assert _tier_language_school(_mkf(1501), _TLS)["tier"] == TIER_AMBER
    assert _tier_language_school(_mkf(3500), _TLS)["tier"] == TIER_AMBER
    assert _tier_language_school(_mkf(3501), _TLS)["tier"] == TIER_RED
    assert _tier_language_school([],         _TLS)["tier"] == TIER_RED
    _TLB = _TN["library"]
    assert _tier_library(_mkf(1000), _TLB)["tier"] == TIER_GREEN
    assert _tier_library(_mkf(1001), _TLB)["tier"] == TIER_AMBER
    assert _tier_library(_mkf(2500), _TLB)["tier"] == TIER_AMBER
    assert _tier_library(_mkf(2501), _TLB)["tier"] == TIER_RED
    assert _tier_library([],         _TLB)["tier"] == TIER_RED
    _TPK = _TN["packstation"]
    assert _tier_packstation(_mkf(400),  _TPK)["tier"] == TIER_GREEN
    assert _tier_packstation(_mkf(401),  _TPK)["tier"] == TIER_AMBER
    assert _tier_packstation(_mkf(1000), _TPK)["tier"] == TIER_AMBER
    assert _tier_packstation(_mkf(1001), _TPK)["tier"] == TIER_RED
    assert _tier_packstation([],         _TPK)["tier"] == TIER_RED
    _TWM = _TN["wochenmarkt"]
    assert _tier_wochenmarkt(_mkf(800),  _TWM)["tier"] == TIER_GREEN
    assert _tier_wochenmarkt(_mkf(801),  _TWM)["tier"] == TIER_AMBER
    assert _tier_wochenmarkt(_mkf(2000), _TWM)["tier"] == TIER_AMBER
    assert _tier_wochenmarkt(_mkf(2001), _TWM)["tier"] == TIER_RED
    assert _tier_wochenmarkt([],         _TWM)["tier"] == TIER_RED

    _TNL = _TN.get("nightlife_density", {})
    _r_nl = _tier_nightlife_density(
        [{"name": "Bar", "lat": 52.5, "lon": 13.4, "distance_m": 300}], _TNL)
    assert _r_nl["tier"] == TIER_UNKNOWN
    assert "1 bars / clubs / pubs within 1 km" in _r_nl["numeric"]
    _r0_nl = _tier_nightlife_density([], _TNL)
    assert _r0_nl["tier"] == TIER_UNKNOWN
    assert _r0_nl["numeric"] == ""
    assert "no bars" in _r0_nl["rule"]

    # -- newcomer_lens composer smoke test.
    from app.cities.berlin import BERLIN as _CFG_NL

    class _StubNLIdx:
        sbahn = []
        ubahn = []
        tram  = []
        osm_local = None
        def buergeramt_near(self, lon, lat, radius_m=5000):
            return []
        def gesix_at(self, lon, lat):
            return {"plr_name": "X", "quintile_5": 3, "rang": 200, "total": 447}

    _out = newcomer_lens(_CFG_NL, _StubNLIdx(), 13.4, 52.5)
    assert all(k in _out for k in ("slug", "label", "audience", "tiles", "provenance"))
    assert _out["slug"] == "newcomer"
    assert _out["label"] == "Newcomer"
    assert len(_out["tiles"]) == 13
    _keys_nl = [t["key"] for t in _out["tiles"]]
    assert _keys_nl == ["buergeramt",
                        "rail_transit", "tram_transit", "bus_transit",
                        "intl_food", "coworking", "english_clinic",
                        "language_school", "library", "packstation", "wochenmarkt",
                        "nightlife_density",
                        "gesix_newcomer"], _keys_nl
    _nl_night = {t["key"]: t for t in _out["tiles"]}["nightlife_density"]
    assert _nl_night["tier"] == TIER_UNKNOWN
    assert any("OpenStreetMap" in s for s in _nl_night["sources"])
    _by_nl = {t["key"]: t for t in _out["tiles"]}
    assert _by_nl["gesix_newcomer"]["tier"] == TIER_AMBER
    _spec_d_keys = {"key","label","icon","tier","rule","numeric","caveat","sources","features"}
    for t in _out["tiles"]:
        assert _spec_d_keys <= set(t.keys()), t
    assert "metadata" in _by_nl["gesix_newcomer"]
    assert "gesix" in _by_nl["gesix_newcomer"]["metadata"]
    _nl_gesix_sources = _by_nl["gesix_newcomer"]["sources"]
    assert _nl_gesix_sources != ["gesix"] and _nl_gesix_sources != ["gesix_newcomer"]
    assert any("GESIx" in s or "Senatsverwaltung" in s for s in _nl_gesix_sources)
    _src_chk = _sources_for(_CFG_NL, "gesix_newcomer", "green")
    assert _src_chk != ["gesix_newcomer"] and _src_chk != ["gesix"]
    assert any("GESIx" in s or "Senatsverwaltung" in s for s in _src_chk)
    _bur_src = _sources_for(_CFG_NL, "buergeramt", "green")
    assert _bur_src != ["buergeramt"]
    assert any("ServicePortal" in s or "service.berlin.de" in s for s in _bur_src)

    print("scorer.py: Newcomer lens (Task 4) selfchecks OK")
