"""Regression guard for Sozialmonitoring legend rows.

Frontend renders the 3-arc tier donut only when `tile.legend` is a
non-empty array (`lens/index.js:118` early exit). Sozialmonitoring
tier fns returned no legend rows → donut missing on Hamburg's
Neighbourhood-status + City-watch-flag cards.
"""
from app.core.scoring.legends import _legend_for


def test_sozialmonitoring_status_legend():
    rows = _legend_for("sozialmonitoring_status", {})
    assert rows, "sozialmonitoring_status must have a legend for donut render"
    assert len(rows) == 3, f"expected 3-band legend, got {len(rows)}"
    tiers = [r["tier"] for r in rows]
    assert "green" in tiers and "amber" in tiers and "red" in tiers


def test_sozialmonitoring_status_commuter_legend_same_as_newcomer():
    rows_n = _legend_for("sozialmonitoring_status", {})
    rows_c = _legend_for("sozialmonitoring_status_commuter", {})
    assert rows_n == rows_c, "commuter variant must reuse the same 3-band shape"


def test_sozialmonitoring_gesamt_legend_binary():
    rows = _legend_for("sozialmonitoring_gesamt", {})
    assert rows, "sozialmonitoring_gesamt must have a legend"
    # Aufmerksamkeitsgebiet is a binary flag — 2-band legend (green vs red)
    assert len(rows) == 2, f"expected 2-band binary legend, got {len(rows)}"
    tiers = [r["tier"] for r in rows]
    assert "green" in tiers and "red" in tiers
    assert "amber" not in tiers, "binary flag shouldn't emit amber row"


def test_sozialmonitoring_gesamt_commuter_matches():
    assert _legend_for("sozialmonitoring_gesamt", {}) == \
           _legend_for("sozialmonitoring_gesamt_commuter", {})


def test_gesix_still_returns_empty():
    """Regression guard: gesix has its own 5-quintile renderer in the
    frontend and legitimately returns [] here — must not accidentally
    catch a sozialmonitoring branch."""
    assert _legend_for("gesix_newcomer", {}) == []
    assert _legend_for("gesix_commuter", {}) == []
