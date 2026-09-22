"""Locks the public surface of the Hamburg subpackage. Every symbol
listed in `hamburg/__init__.py::__all__` must be importable via
`from app.cities.hamburg import <name>` and must be the object the
current call-site expects (spec §Public surface, grep 2026-09-22)."""

from app.cities.base import CityConfig, LensConfig, OthersAdminCardConfig


def test_HAMBURG_importable_as_CityConfig():
    from app.cities.hamburg import HAMBURG
    assert isinstance(HAMBURG, CityConfig)
    assert HAMBURG.slug == "hamburg"


def test_lenses_importable_and_correct_type():
    from app.cities.hamburg import NEWCOMER_LENS, COMMUTER_LENS
    assert isinstance(NEWCOMER_LENS, LensConfig)
    assert isinstance(COMMUTER_LENS, LensConfig)
    assert NEWCOMER_LENS.slug == "newcomer"
    assert COMMUTER_LENS.slug == "commuter"


def test_others_admin_cards_importable_and_correct_shape():
    from app.cities.hamburg import OTHERS_ADMIN_CARDS
    assert isinstance(OTHERS_ADMIN_CARDS, tuple)
    assert len(OTHERS_ADMIN_CARDS) == 5
    assert all(isinstance(c, OthersAdminCardConfig) for c in OTHERS_ADMIN_CARDS)


def test_package___all___pins_the_public_surface():
    """__all__ is the contract — narrowing it silently breaks call-sites.
    Do NOT relax this to a subset; extend it if we intentionally add a
    new public symbol."""
    from app.cities import hamburg as pkg
    assert set(pkg.__all__) >= {
        "HAMBURG", "NEWCOMER_LENS", "COMMUTER_LENS", "OTHERS_ADMIN_CARDS",
    }


def test_HAMBURG_identity_matches_config_module():
    """HAMBURG re-exported via __init__ MUST be the same object as the
    one built in hamburg.config — no accidental copy/reassignment."""
    from app.cities.hamburg import HAMBURG
    from app.cities.hamburg.config import HAMBURG as _config_HAMBURG
    assert HAMBURG is _config_HAMBURG
