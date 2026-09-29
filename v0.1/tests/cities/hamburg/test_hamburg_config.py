"""Hamburg CityConfig invariants — imported at test time so CI catches
tile-key drift the same way TILE_GLOSSARY_KEYS catches Berlin's."""
from app.cities.hamburg import HAMBURG, NEWCOMER_LENS, COMMUTER_LENS, YOUNG_FAMILY_LENS


def test_hamburg_slug():
    assert HAMBURG.slug == "hamburg"


def test_hamburg_geocoder_is_oaf():
    assert HAMBURG.geocoder == "oaf"
    assert HAMBURG.geocoder_oaf_url


def test_no_tram_in_hamburg_lenses():
    for t in NEWCOMER_LENS.tiles:
        assert "tram" not in t.key
    for t in COMMUTER_LENS.tiles:
        assert "tram" not in t.key
    for t in YOUNG_FAMILY_LENS.tiles:
        assert "tram" not in t.key


def test_ferry_present_in_both_lenses():
    assert any(t.key == "ferry_transit" for t in NEWCOMER_LENS.tiles)
    assert any(t.key == "commuter_ferry_transit" for t in COMMUTER_LENS.tiles)


def test_sozialmonitoring_two_tiles_per_lens():
    n_keys = [t.key for t in NEWCOMER_LENS.tiles]
    assert "sozialmonitoring_status" in n_keys
    assert "sozialmonitoring_gesamt" in n_keys
    c_keys = [t.key for t in COMMUTER_LENS.tiles]
    assert "sozialmonitoring_status_commuter" in c_keys
    assert "sozialmonitoring_gesamt_commuter" in c_keys


def test_others_tab_has_all_five_admin_cards():
    admin_keys = [c.key for c in HAMBURG.others_admin_cards]
    assert admin_keys == ["kundenzentrum", "finanzamt", "standesamt",
                          "lea", "arbeitsagentur"]
    assert len(HAMBURG.kundenzentren) == 7    # 7 Bezirks-main Kundenzentren
    assert len(HAMBURG.finanzamts) == 9       # 9 Hamburg Finanzämter
    assert len(HAMBURG.arbeitsagenturs) == 4  # 4 Agentur für Arbeit branches
    assert HAMBURG.lea_office.get("name")     # curated Einwohner-Zentralamt
    assert len(HAMBURG.intl_schools_curated) >= 3


def test_hamburg_flags():
    assert HAMBURG.noise_model == "isoline"
    assert HAMBURG.air_model == "none"
    assert HAMBURG.fire_zones_available is False


def test_hamburg_yf_has_no_air_no_refuge():
    """Hamburg has no air-quality WFS and no tree-crown data — YF must
    skip both tiles cleanly rather than fabricate them."""
    yf_keys = [t.key for t in YOUNG_FAMILY_LENS.tiles]
    assert "air" not in yf_keys, f"air leaked into Hamburg YF: {yf_keys}"
    assert "refuge" not in yf_keys, f"refuge leaked into Hamburg YF: {yf_keys}"


def test_hamburg_yf_uses_noise_band_not_noise():
    """Hamburg's noise data is isoline-band strings, not point dB values.
    YF must use tile key `noise_band` (matching QL convention), never `noise`."""
    yf_keys = [t.key for t in YOUNG_FAMILY_LENS.tiles]
    assert "noise_band" in yf_keys, f"noise_band missing: {yf_keys}"
    assert "noise" not in yf_keys, f"Berlin key `noise` leaked into Hamburg YF: {yf_keys}"


def test_hamburg_yf_sozialmonitoring_shape_only_tile():
    """Hamburg YF replaces Berlin's `gesix` with `sozialmonitoring_status_young_family`
    (shape-only; empty thresholds; per-lens suffix matches _commuter/_quiet pattern)."""
    yf_keys = [t.key for t in YOUNG_FAMILY_LENS.tiles]
    assert "sozialmonitoring_status_young_family" in yf_keys
    assert "gesix" not in yf_keys
    tile = next(t for t in YOUNG_FAMILY_LENS.tiles
                if t.key == "sozialmonitoring_status_young_family")
    assert tile.thresholds == {}, "shape-only tile must have empty thresholds"


def test_hamburg_yf_tile_order():
    """Locks the Hamburg YF tile order so accidental reordering surfaces in CI."""
    yf_keys = [t.key for t in YOUNG_FAMILY_LENS.tiles]
    assert yf_keys == [
        "kita", "playground", "pediatrician", "transit", "supermarket",
        "noise_band", "heat", "sozialmonitoring_status_young_family",
    ], yf_keys
