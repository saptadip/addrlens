"""Selfcheck asserts for the Berlin CityConfig subpackage.

Invoked by `python -m app.cities.berlin` — matches the pre-split
invocation shape byte-for-byte so CI (selfchecks matrix) and dev
workflow keep working without an edit.

Asserts every invariant the old berlin.py `__main__` block had, plus
an extra guard that the __init__ shim's __all__ hasn't been narrowed."""
from app.cities.berlin import (
    BERLIN,
    YOUNG_FAMILY_LENS,
    NEWCOMER_LENS,
    QUIET_LIVING_LENS,
    COMMUTER_LENS,
    OTHERS_ADMIN_CARDS,
)
from app.cities import berlin as _pkg

assert BERLIN.newcomer_lens is NEWCOMER_LENS
assert BERLIN.others_admin_cards is OTHERS_ADMIN_CARDS
assert BERLIN.buergeramt_wfs_url is not None    # WFS already wired
keys = [t.key for t in BERLIN.newcomer_lens.tiles]
assert keys == ["buergeramt",
                "rail_transit", "tram_transit", "bus_transit",
                "intl_food", "coworking", "english_clinic",
                "language_school", "library",
                "packstation", "parkzone",
                "wochenmarkt", "xmas_market",
                "nightlife_density",
                "gesix_newcomer"], keys
commuter_keys = [t.key for t in BERLIN.commuter_lens.tiles]
assert commuter_keys == [
    "commuter_rail_transit", "commuter_tram_transit", "commuter_bus_transit",
    "regional_rail_reach", "cycling_network",
    "parkzone", "car_sharing_reach", "ev_charging_reach",
    "airport_reach", "gesix_commuter",
], commuter_keys
admin_keys = [c.key for c in BERLIN.others_admin_cards]
assert admin_keys == ["buergeramt", "finanzamt", "standesamt",
                      "lea", "arbeitsagentur"], admin_keys
assert "buergeramt" in BERLIN.attribution
assert BERLIN.smoke_address, "smoke_address must be set for update.sh"

# Regression guard: the __init__ shim's __all__ must not be narrowed
# below the six symbols we chose to publish (Hamburg-parity broad set).
assert set(_pkg.__all__) >= {
    "BERLIN",
    "YOUNG_FAMILY_LENS",
    "NEWCOMER_LENS",
    "QUIET_LIVING_LENS",
    "COMMUTER_LENS",
    "OTHERS_ADMIN_CARDS",
}, f"__init__.py __all__ narrowed to {sorted(_pkg.__all__)} — restore missing symbols before merge"

print("selfcheck ok: NEWCOMER_LENS + OTHERS_ADMIN_CARDS wired")
