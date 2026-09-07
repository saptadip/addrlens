"""Unit tests for `app.core.scoring.tiers` — pure tier functions.

Ground truth: the selfcheck block at the bottom of `app/core/scorer.py`,
which asserts these same boundaries. Boundary convention: inclusive on
the greener side (≤ green is green; > green is amber).
"""
import pytest

from app.core.scorer import noise_tier, stroller_score


# --- noise_tier — WHO + EU-CNOSSOS action-plan thresholds --------------


@pytest.mark.parametrize(
    "l_den,expected",
    [
        (0,    "green"),
        (54,   "green"),
        (50,   "green"),
        (55,   "amber"),   # 55 dB is the WHO boundary; not < 55.
        (60,   "amber"),
        (64,   "amber"),
        (65,   "orange"),
        (68,   "orange"),
        (69,   "orange"),
        (70,   "red"),
        (75,   "red"),
        (100,  "red"),
        (None, "unknown"),
    ],
)
def test_noise_tier_band_boundaries(l_den, expected):
    assert noise_tier(l_den) == expected


# --- stroller_score — rule-based livability for a flat with a toddler --


def test_stroller_score_missing_inputs_returns_unknown():
    r = stroller_score(None, True, False, 300)
    assert r["tier"] == "unknown"
    assert r["reasons"], "unknown score must still explain itself"


@pytest.mark.parametrize(
    "floor,lift,kwr,playground_m,expected_tier",
    [
        # Ground floor, no lift, no Kinderwagenraum, close playground → green.
        (0, False, False, 300, "green"),
        # 3rd floor with lift → carry solved → green.
        (3, True,  False, 300, "green"),
        # 2nd floor, no lift → tiring → amber.
        (2, False, False, 300, "amber"),
        # 4th floor, no lift → hard-no → red.
        (4, False, False, 300, "red"),
        # 4th floor red rescued to amber by Kinderwagenraum.
        (4, False, True,  300, "amber"),
        # 2nd floor amber lifted to green by Kinderwagenraum.
        (2, False, True,  300, "green"),
        # Ground floor green downgraded when no playground within 800 m.
        (0, True,  False, 1200, "amber"),
    ],
)
def test_stroller_score_tier_matrix(floor, lift, kwr, playground_m, expected_tier):
    r = stroller_score(floor, lift, kwr, playground_m)
    assert r["tier"] == expected_tier, r


def test_stroller_score_hard_no_reason_present_for_high_floor_walkup():
    r = stroller_score(3, False, False, 300)
    assert r["tier"] == "red"
    assert any("hard no" in x["text"] for x in r["reasons"])


def test_stroller_score_reasons_have_expected_shape():
    r = stroller_score(0, False, False, 200)
    for reason in r["reasons"]:
        assert "kind" in reason
        assert "text" in reason
        assert reason["kind"] in {"good", "warn", "bad", "info"}
