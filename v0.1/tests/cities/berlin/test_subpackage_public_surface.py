"""Locks the public surface of the Berlin subpackage. Every symbol
listed in `berlin/__init__.py::__all__` must be importable via
`from app.cities.berlin import <name>` and must be the object the
current call-site expects (see plan Global Constraints, grep 2026-09-22)."""

from app.cities.base import CityConfig, LensConfig, OthersAdminCardConfig


def test_BERLIN_importable_as_CityConfig():
    from app.cities.berlin import BERLIN
    assert isinstance(BERLIN, CityConfig)
    assert BERLIN.slug == "berlin"


def test_all_four_lenses_importable_and_correct_type():
    from app.cities.berlin import (
        YOUNG_FAMILY_LENS,
        NEWCOMER_LENS,
        QUIET_LIVING_LENS,
        COMMUTER_LENS,
    )
    for lens in (YOUNG_FAMILY_LENS, NEWCOMER_LENS, QUIET_LIVING_LENS, COMMUTER_LENS):
        assert isinstance(lens, LensConfig)
    assert YOUNG_FAMILY_LENS.slug == "young_family"
    assert NEWCOMER_LENS.slug == "newcomer"
    assert QUIET_LIVING_LENS.slug == "quiet_living"
    assert COMMUTER_LENS.slug == "commuter"


def test_others_admin_cards_importable_and_correct_shape():
    from app.cities.berlin import OTHERS_ADMIN_CARDS
    assert isinstance(OTHERS_ADMIN_CARDS, tuple)
    assert len(OTHERS_ADMIN_CARDS) >= 1
    assert all(isinstance(c, OthersAdminCardConfig) for c in OTHERS_ADMIN_CARDS)


def test_package___all___pins_the_public_surface():
    """__all__ is the contract — narrowing it silently breaks call-sites.
    Do NOT relax this to a subset; extend it if we intentionally add a
    new public symbol. Broad shape matches the Hamburg pattern from PR #93."""
    from app.cities import berlin as pkg
    assert set(pkg.__all__) >= {
        "BERLIN",
        "YOUNG_FAMILY_LENS",
        "NEWCOMER_LENS",
        "QUIET_LIVING_LENS",
        "COMMUTER_LENS",
        "OTHERS_ADMIN_CARDS",
    }


def test_BERLIN_identity_matches_config_module():
    """BERLIN re-exported via __init__ MUST be the same object as the
    one built in berlin.config — no accidental copy/reassignment."""
    from app.cities.berlin import BERLIN
    from app.cities.berlin.config import BERLIN as _config_BERLIN
    assert BERLIN is _config_BERLIN
