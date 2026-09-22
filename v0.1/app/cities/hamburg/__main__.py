"""Selfcheck asserts for the Hamburg CityConfig subpackage.

Invoked by `python -m app.cities.hamburg` — matches the pre-split
invocation shape byte-for-byte so CI (selfchecks matrix) and dev
workflow keep working without an edit.

Asserts every invariant the old hamburg.py `__main__` block had, plus
an extra guard that the __init__ shim's __all__ hasn't been narrowed."""
from app.cities.hamburg          import HAMBURG, NEWCOMER_LENS, COMMUTER_LENS, OTHERS_ADMIN_CARDS
from app.cities                  import hamburg as _pkg

# T12 skeleton asserts
assert HAMBURG.slug == "hamburg"
assert HAMBURG.wfs_output_format == "application/geo+json"
assert HAMBURG.geocoder == "oaf"
assert HAMBURG.noise_model == "isoline"
assert HAMBURG.air_model == "none"
assert HAMBURG.fire_zones_available is False
assert HAMBURG.bezirk_id_to_name[1] == "Hamburg-Mitte"
assert len(HAMBURG.standesamts_by_bezirk) == 7
assert len(HAMBURG.regional_rail_stations) == 13
assert HAMBURG.gesix_wfs_url is None
assert HAMBURG.sozialmonitoring_wfs_url is not None
assert HAMBURG.pools_wfs_url is None
assert HAMBURG.xmas_market_url is None
# T13/T14 lens presence asserts
assert HAMBURG.newcomer_lens is not None
assert len(HAMBURG.newcomer_lens.tiles) == 13
assert HAMBURG.commuter_lens is not None
assert len(HAMBURG.commuter_lens.tiles) == 11
assert HAMBURG.young_family_lens is None
assert HAMBURG.quiet_living_lens is None
# T15: identity asserts
assert HAMBURG.newcomer_lens is NEWCOMER_LENS
assert HAMBURG.commuter_lens is COMMUTER_LENS
assert HAMBURG.others_admin_cards is OTHERS_ADMIN_CARDS
assert HAMBURG.buergeramt_wfs_url is None
# T15: tile-key order asserts — Newcomer (13 keys)
keys = [t.key for t in HAMBURG.newcomer_lens.tiles]
assert keys == [
    "rail_transit", "ferry_transit", "bus_transit",
    "intl_food", "coworking",
    "english_clinic", "language_school", "library",
    "packstation", "parkzone",
    "nightlife_density",
    "sozialmonitoring_status", "sozialmonitoring_gesamt",
], keys
# T15: tile-key order asserts — Commuter (11 keys)
commuter_keys = [t.key for t in HAMBURG.commuter_lens.tiles]
assert commuter_keys == [
    "commuter_rail_transit", "commuter_ferry_transit", "commuter_bus_transit",
    "regional_rail_reach", "cycling_network",
    "parkzone", "car_sharing_reach", "ev_charging_reach",
    "airport_reach",
    "sozialmonitoring_status_commuter", "sozialmonitoring_gesamt_commuter",
], commuter_keys
# No tram tile in either lens
assert "tram_transit" not in keys
assert "commuter_tram_transit" not in commuter_keys
# Others tab: 5 curated cards (Kundenzentrum, Finanzamt, Standesamt, LEA, Arbeitsagentur)
admin_keys = [c.key for c in HAMBURG.others_admin_cards]
assert admin_keys == ["kundenzentrum", "finanzamt", "standesamt", "lea", "arbeitsagentur"], admin_keys
assert len(HAMBURG.kundenzentren) == 7, len(HAMBURG.kundenzentren)
assert len(HAMBURG.finanzamts) == 9, len(HAMBURG.finanzamts)
assert len(HAMBURG.arbeitsagenturs) == 4, len(HAMBURG.arbeitsagenturs)
assert HAMBURG.lea_office and HAMBURG.lea_office.get("name")
assert len(HAMBURG.intl_schools_curated) >= 3
assert HAMBURG.smoke_address, "smoke_address must be set for update.sh"
# Attribution keys wired for every provenance-bearing dataset
for k in ("schools", "kitas", "hospitals", "trees", "sozialmonitoring",
          "ferry", "parkzone", "standesamt", "kundenzentrum", "finanzamt"):
    assert k in HAMBURG.attribution, f"missing attribution: {k}"

# Regression guard: the __init__ shim's __all__ must not be narrowed
# below the four symbols current call-sites import by name (grep at
# 2026-09-22: HAMBURG, NEWCOMER_LENS, COMMUTER_LENS, OTHERS_ADMIN_CARDS).
assert set(_pkg.__all__) >= {"HAMBURG", "NEWCOMER_LENS", "COMMUTER_LENS", "OTHERS_ADMIN_CARDS"}, \
    f"__init__.py __all__ narrowed to {sorted(_pkg.__all__)} — restore missing symbols before merge"

print("selfcheck ok: Hamburg Newcomer + Commuter lenses wired")
