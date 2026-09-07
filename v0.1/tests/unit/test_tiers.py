"""Unit tests for the Young Family tier functions in
`app.core.scoring.tiers`.

Boundary convention across the codebase: inclusive on the greener side
(``x <= green`` is green; ``x > green`` is amber). Ground truth: the
selfcheck block in `app/core/scorer.py` (§ Young Family lens).
"""
import pytest

from app.cities.berlin import BERLIN
from app.core.scoring.constants import (
    TIER_AMBER, TIER_GREEN, TIER_RED, TIER_UNKNOWN,
)
from app.core.scoring.tiers import (
    _tier_air, _tier_from_walk, _tier_heat, _tier_kita, _tier_noise,
    _tier_pediatrician, _tier_playground,
)


@pytest.fixture(scope="module")
def yf_thresholds():
    return {t.key: t.thresholds for t in BERLIN.young_family_lens.tiles}


# --- _tier_kita --------------------------------------------------------


def test_tier_kita_green_when_three_within_green_m(yf_thresholds):
    kitas = [{"distance_m": 400}, {"distance_m": 350}, {"distance_m": 100}]
    r = _tier_kita(kitas, yf_thresholds["kita"])
    assert r["tier"] == TIER_GREEN


def test_tier_kita_amber_when_just_over_green(yf_thresholds):
    kitas = [{"distance_m": 401}, {"distance_m": 402}, {"distance_m": 403}]
    r = _tier_kita(kitas, yf_thresholds["kita"])
    assert r["tier"] == TIER_AMBER


def test_tier_kita_red_when_all_far(yf_thresholds):
    r = _tier_kita([{"distance_m": 900}], yf_thresholds["kita"])
    assert r["tier"] == TIER_RED


def test_tier_kita_empty_features_red(yf_thresholds):
    # Preloaded source — an empty list means "none nearby" not "unknown".
    r = _tier_kita([], yf_thresholds["kita"])
    assert r["tier"] == TIER_RED


# --- _tier_playground -------------------------------------------------


def test_tier_playground_unknown_when_data_missing(yf_thresholds):
    r = _tier_playground([], True, yf_thresholds["playground"])
    assert r["tier"] == TIER_UNKNOWN


@pytest.mark.parametrize(
    "distance_m,expected",
    [(400, TIER_GREEN), (401, TIER_AMBER), (800, TIER_AMBER), (801, TIER_RED)],
)
def test_tier_playground_boundaries(distance_m, expected, yf_thresholds):
    r = _tier_playground([{"distance_m": distance_m}], False,
                         yf_thresholds["playground"])
    assert r["tier"] == expected


# --- _tier_pediatrician -----------------------------------------------


@pytest.mark.parametrize(
    "distance_m,expected",
    [(800, TIER_GREEN), (801, TIER_AMBER),
     (1500, TIER_AMBER), (1501, TIER_RED)],
)
def test_tier_pediatrician_boundaries(distance_m, expected, yf_thresholds):
    feats = [{"distance_m": distance_m, "name": "Dr. X"}]
    r = _tier_pediatrician(feats, False, yf_thresholds["pediatrician"])
    assert r["tier"] == expected


def test_tier_pediatrician_unknown_when_gps_error(yf_thresholds):
    r = _tier_pediatrician([], True, yf_thresholds["pediatrician"])
    assert r["tier"] == TIER_UNKNOWN


# --- _tier_noise ------------------------------------------------------


@pytest.mark.parametrize(
    "l_den,expected",
    [(55, TIER_GREEN), (55.01, TIER_AMBER),
     (60, TIER_AMBER),  (60.01, TIER_RED)],
)
def test_tier_noise_boundaries(l_den, expected, yf_thresholds):
    r = _tier_noise({"l_den": {"total": l_den}}, yf_thresholds["noise"])
    assert r["tier"] == expected


def test_tier_noise_unavailable_returns_unknown(yf_thresholds):
    r = _tier_noise({"unavailable": True}, yf_thresholds["noise"])
    assert r["tier"] == TIER_UNKNOWN


# --- _tier_air --------------------------------------------------------


@pytest.mark.parametrize(
    "no2,expected",
    [(0, TIER_GREEN), (20, TIER_GREEN), (20.01, TIER_AMBER),
     (40, TIER_AMBER), (40.01, TIER_RED), (100, TIER_RED)],
)
def test_tier_air_boundaries(no2, expected, yf_thresholds):
    r = _tier_air({"no2_ugm3": no2}, yf_thresholds["air"])
    assert r["tier"] == expected


def test_tier_air_unavailable_returns_unknown(yf_thresholds):
    r = _tier_air({"unavailable": True}, yf_thresholds["air"])
    assert r["tier"] == TIER_UNKNOWN


# --- _tier_heat -------------------------------------------------------


@pytest.mark.parametrize(
    "day_class,expected",
    [
        ("geringe Belastung",         TIER_GREEN),
        ("keine Belastung",           TIER_GREEN),
        ("mäßige Belastung",          TIER_AMBER),
        ("starke Belastung",          TIER_AMBER),
        ("sehr starke Belastung",     TIER_RED),
        ("extreme Belastung",         TIER_RED),
        # Real Umweltatlas prefix format.
        ("<= 33 °C - geringe Belastung",                    TIER_GREEN),
        ("> 33 °C - <= 35 °C - mäßige Belastung",           TIER_AMBER),
        ("> 35 °C - sehr starke Belastung",                 TIER_RED),
    ],
)
def test_tier_heat_class_matches(day_class, expected, yf_thresholds):
    r = _tier_heat({"day_class": day_class}, yf_thresholds["heat"])
    assert r["tier"] == expected


def test_tier_heat_unavailable_returns_unknown(yf_thresholds):
    r = _tier_heat({"unavailable": True}, yf_thresholds["heat"])
    assert r["tier"] == TIER_UNKNOWN


# --- _tier_from_walk -------------------------------------------------


@pytest.mark.parametrize(
    "walk_min,expected",
    [(None, TIER_UNKNOWN), (0, TIER_GREEN), (5, TIER_GREEN),
     (6, TIER_AMBER), (10, TIER_AMBER), (11, TIER_RED)],
)
def test_tier_from_walk_ladder(walk_min, expected):
    assert _tier_from_walk(walk_min, 5, 10) == expected
