"""Hamburg lens composer smoke test — guards against Berlin-only tile-key
hardcodes in the shared composer. Added after PR #81 review found KeyError
on Hamburg config."""
from app.cities.hamburg import HAMBURG
from app.core.scorer import newcomer_lens, commuter_lens


class _StubIdx:
    """Minimal Index-shaped stub with empty everything — enough to exercise
    the composer's dispatch without live data."""
    sbahn = []
    ubahn = []
    tram = []
    ferry = []
    regional_rail = []
    osm_local = None
    gs_public = []
    sozialmonitoring = []
    def buergeramt_near(self, *a, **kw): return []
    def xmas_market_near(self, *a, **kw): return []
    def parking_zone_at(self, *a, **kw): return None
    def sozialmonitoring_at(self, *a, **kw): return None
    def nearest_ferry(self, *a, **kw): return None


def test_hamburg_newcomer_composer_runs():
    out = newcomer_lens(HAMBURG, _StubIdx(), 9.99, 53.55, amenities={})
    assert out["slug"] == "newcomer"
    # No tile is an error dict — composer completed without exception.
    tile_keys = {t["key"] for t in out["tiles"]}
    # Hamburg-specific tiles must appear.
    for expected in ("ferry_transit", "sozialmonitoring_status", "sozialmonitoring_gesamt"):
        assert expected in tile_keys, f"Hamburg tile {expected!r} missing from composer output"
    # Berlin-only tiles must NOT appear.
    for banned in ("buergeramt", "xmas_market", "wochenmarkt", "tram_transit", "gesix_newcomer"):
        assert banned not in tile_keys, f"Berlin tile {banned!r} leaked into Hamburg composer output"


def test_hamburg_commuter_composer_runs():
    out = commuter_lens(HAMBURG, _StubIdx(), 9.99, 53.55, amenities={})
    assert out["slug"] == "commuter"
    tile_keys = {t["key"] for t in out["tiles"]}
    for expected in ("commuter_ferry_transit", "sozialmonitoring_status_commuter", "sozialmonitoring_gesamt_commuter"):
        assert expected in tile_keys
    for banned in ("commuter_tram_transit", "gesix_commuter"):
        assert banned not in tile_keys


def test_hamburg_new_tiles_have_provenance_mapping():
    """_sources_for must return a non-empty citation for every new Hamburg
    tile key at a real (green/amber/red) tier. Guards against the fourth-
    surface attribution drift where the tile card renders empty citations
    while the footer + impressum cite the source. Direct-tested at the
    mapping layer because the composer path returns [] on UNKNOWN tiers
    by design (tier=UNKNOWN → no citation, same as Berlin gesix)."""
    from app.core.scoring.provenance import _sources_for
    for hh_tile in ("ferry_transit", "commuter_ferry_transit",
                    "sozialmonitoring_status", "sozialmonitoring_gesamt",
                    "sozialmonitoring_status_commuter",
                    "sozialmonitoring_gesamt_commuter"):
        srcs = _sources_for(HAMBURG, hh_tile, "green")
        assert srcs, f"Hamburg tile {hh_tile!r} has empty sources at tier=green — provenance mapping gap"


def test_hamburg_new_tiles_have_legend_mapping():
    """_legend_for must return a non-empty 3-band legend for ferry tiles.
    Sozialmonitoring tiles are category-driven (like Berlin gesix) and
    correctly return []."""
    from app.core.scoring.legends import _legend_for
    ferry_th = {"green_m": 500, "amber_m": 1000}
    assert _legend_for("ferry_transit", ferry_th), "ferry_transit missing legend"
    assert _legend_for("commuter_ferry_transit", {"green_m": 400, "amber_m": 800}), \
        "commuter_ferry_transit missing legend"


def test_berlin_composers_still_produce_all_tiles():
    """Regression guard: Berlin composers must still return the full 15/10
    tile set with no KeyError from the new conditional guards."""
    from app.cities.berlin import BERLIN
    out_n = newcomer_lens(BERLIN, _StubIdx(), 13.4, 52.5, amenities={})
    keys_n = {t["key"] for t in out_n["tiles"]}
    # Berlin Newcomer must still carry all its historic tiles
    for expected in ("buergeramt", "rail_transit", "tram_transit", "bus_transit",
                     "intl_food", "coworking", "english_clinic", "language_school",
                     "library", "packstation", "parkzone",
                     "wochenmarkt", "xmas_market", "nightlife_density", "gesix_newcomer"):
        assert expected in keys_n, f"Berlin tile {expected!r} lost from composer output"
    out_c = commuter_lens(BERLIN, _StubIdx(), 13.4, 52.5, amenities={})
    keys_c = {t["key"] for t in out_c["tiles"]}
    for expected in ("commuter_rail_transit", "commuter_tram_transit", "commuter_bus_transit",
                     "regional_rail_reach", "cycling_network", "parkzone",
                     "car_sharing_reach", "ev_charging_reach", "airport_reach", "gesix_commuter"):
        assert expected in keys_c, f"Berlin commuter tile {expected!r} lost"
