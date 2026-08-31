"""Per-tile traffic-light legend text — three-line reference the SPA
renders under each Life-Mode tile face."""

from app.core.scoring.constants import (
    TIER_AMBER, TIER_GREEN, TIER_RED, _fmt_dist,
)


def _legend_for(key: str, th: dict) -> list:
    """Per-tile traffic-light legend for the in-card criteria strip.

    Returns [{"tier": "green|amber|red", "text": "..."}] in tier order so
    the frontend can render a three-line reference under every tile. Empty
    list = tile has no 3-band verdict (GESIx uses 5 quintiles, nightlife
    is numeric-only). Text kept short — legend rows sit in a compact strip
    with limited column width.
    """
    fd = _fmt_dist

    def _dist_legend(green_m: int, amber_m: int) -> list:
        return [
            {"tier": TIER_GREEN, "text": f"≤{fd(green_m)} walk"},
            {"tier": TIER_AMBER, "text": f"≤{fd(amber_m)}"},
            {"tier": TIER_RED,   "text": f">{fd(amber_m)}"},
        ]

    def _count_legend(radius_m: int, green_c: int, amber_c: int) -> list:
        r = fd(radius_m)
        return [
            {"tier": TIER_GREEN, "text": f"≥{green_c} within {r}"},
            {"tier": TIER_AMBER, "text": f"{amber_c}–{green_c-1} within {r}"},
            {"tier": TIER_RED,   "text": f"<{amber_c} within {r}"},
        ]

    # -- Young Family ---------------------------------------------------
    if key == "kita":
        return [
            {"tier": TIER_GREEN, "text": f"≥{th['green_count']} kitas within {fd(th['green_m'])}"},
            {"tier": TIER_AMBER, "text": f"≥1 kita within {fd(th['amber_m'])}"},
            {"tier": TIER_RED,   "text": f"none within {fd(th['amber_m'])}"},
        ]
    if key == "playground":
        return [
            {"tier": TIER_GREEN, "text": f"≥1 within {fd(th['green_m'])}"},
            {"tier": TIER_AMBER, "text": f"{fd(th['green_m'])}–{fd(th['amber_m'])}"},
            {"tier": TIER_RED,   "text": f">{fd(th['amber_m'])}"},
        ]
    if key == "pediatrician":
        return [
            {"tier": TIER_GREEN, "text": f"≥1 within {fd(th['green_m'])}"},
            {"tier": TIER_AMBER, "text": f"{fd(th['green_m'])}–{fd(th['amber_m'])}"},
            {"tier": TIER_RED,   "text": f">{fd(th['amber_m'])}"},
        ]
    if key == "transit":
        return [
            {"tier": TIER_GREEN, "text": f"stop ≤{th['green_min']} min walk"},
            {"tier": TIER_AMBER, "text": f"stop ≤{th['amber_min']} min"},
            {"tier": TIER_RED,   "text": f">{th['amber_min']} min"},
        ]
    if key == "supermarket":
        return [
            {"tier": TIER_GREEN, "text": f"≥1 within {th['green_min']} min walk"},
            {"tier": TIER_AMBER, "text": f"within {th['amber_min']} min"},
            {"tier": TIER_RED,   "text": f">{th['amber_min']} min"},
        ]
    if key == "noise":
        return [
            {"tier": TIER_GREEN, "text": f"L_DEN ≤{th['green_db']} dB"},
            {"tier": TIER_AMBER, "text": f"{th['green_db']}–{th['amber_db']} dB"},
            {"tier": TIER_RED,   "text": f">{th['amber_db']} dB"},
        ]
    if key == "heat":
        return [
            {"tier": TIER_GREEN, "text": "keine / geringe"},
            {"tier": TIER_AMBER, "text": "mäßige / starke"},
            {"tier": TIER_RED,   "text": "sehr starke / extreme"},
        ]
    if key == "air":
        return [
            {"tier": TIER_GREEN, "text": f"NO₂ ≤{th['green_ugm3']} μg/m³"},
            {"tier": TIER_AMBER, "text": f"{th['green_ugm3']}–{th['amber_ugm3']} μg/m³"},
            {"tier": TIER_RED,   "text": f">{th['amber_ugm3']} μg/m³"},
        ]
    if key == "refuge":
        return [
            {"tier": TIER_GREEN, "text": f"quiet ≤{fd(th['green_quiet_m'])} OR crown ≥{th['green_crown_pct']}%"},
            {"tier": TIER_AMBER, "text": f"quiet ≤{fd(th['amber_quiet_m'])} OR crown ≥{th['amber_crown_pct']}%"},
            {"tier": TIER_RED,   "text": "neither"},
        ]

    # -- Newcomer -------------------------------------------------------
    if key == "buergeramt":
        return _dist_legend(th['green_m'], th['amber_m'])
    if key == "rail_transit":
        return [
            {"tier": TIER_GREEN, "text": f"S ≤{fd(th['sbahn_m'])} or U ≤{fd(th['ubahn_m'])}"},
            {"tier": TIER_AMBER, "text": f"rail ≤{fd(th['any_rail_m'])}"},
            {"tier": TIER_RED,   "text": f">{fd(th['any_rail_m'])}"},
        ]
    if key in ("tram_transit", "bus_transit", "english_clinic",
               "language_school", "library", "packstation", "wochenmarkt"):
        return _dist_legend(th['green_m'], th['amber_m'])
    if key == "intl_food":
        return _count_legend(th['radius_m'], th['green_count'], th['amber_count'])
    if key == "coworking":
        return _count_legend(th['radius_m'], th['green_count'], th['amber_count'])

    # -- Quiet Living ---------------------------------------------------
    if key == "quiet_zone":
        return _dist_legend(th['green_m'], th['amber_m'])
    if key == "street_trees":
        return [
            {"tier": TIER_GREEN, "text": f"≥ {th['green_pct']}% canopy"},
            {"tier": TIER_AMBER, "text": f"{th['amber_pct']}–{th['green_pct']-1}%"},
            {"tier": TIER_RED,   "text": f"< {th['amber_pct']}%"},
        ]
    if key == "tempo30":
        return [
            {"tier": TIER_GREEN, "text": f"≤ {th['green_kmh']} km/h"},
            {"tier": TIER_AMBER, "text": f"{th['green_kmh']+1}–{th['amber_kmh']} km/h"},
            {"tier": TIER_RED,   "text": f"> {th['amber_kmh']} km/h"},
        ]
    if key == "arterial_road":
        # Inverted-distance: further from the arterial is greener.
        return [
            {"tier": TIER_GREEN, "text": f"≥ {fd(th['green_m'])}"},
            {"tier": TIER_AMBER, "text": f"{fd(th['amber_m'])}–{fd(th['green_m']-1)}"},
            {"tier": TIER_RED,   "text": f"< {fd(th['amber_m'])}"},
        ]
    if key == "rail_noise":
        return [
            {"tier": TIER_GREEN, "text": f"S ≥ {fd(th['green_m'])} · U underground"},
            {"tier": TIER_AMBER, "text": f"S {fd(th['amber_m'])}–{fd(th['green_m']-1)}"},
            {"tier": TIER_RED,   "text": f"S < {fd(th['amber_m'])}"},
        ]
    if key == "nightlife_inverted":
        r = fd(th['radius_m'])
        return [
            {"tier": TIER_GREEN, "text": f"≤ {th['green_max']} within {r}"},
            {"tier": TIER_AMBER, "text": f"{th['green_max']+1}–{th['amber_max']} within {r}"},
            {"tier": TIER_RED,   "text": f"> {th['amber_max']} within {r}"},
        ]

    # nightlife_density (numeric-only) + gesix / gesix_newcomer / gesix_quiet
    # (5-quintile) don't fit a 3-band legend — skip.
    return []


if __name__ == "__main__":
    kita = _legend_for("kita", {"green_count": 3, "green_m": 400, "amber_m": 800})
    assert len(kita) == 3 and kita[0]["tier"] == TIER_GREEN
    assert "3 kitas within 400m" in kita[0]["text"]
    tram = _legend_for("tram_transit", {"green_m": 500, "amber_m": 1000})
    assert tram[0]["text"] == "≤500m walk"
    assert _legend_for("gesix", {}) == []
    assert _legend_for("nightlife_density", {}) == []
    assert _legend_for("gesix_quiet", {}) == []
    assert _legend_for("unknown_key", {}) == []

    # Quiet Living legends — spot-check inverted-distance shape.
    qz = _legend_for("quiet_zone", {"green_m": 400, "amber_m": 1000})
    assert len(qz) == 3 and qz[0]["text"] == "≤400m walk"

    art = _legend_for("arterial_road", {"green_m": 150, "amber_m": 50})
    assert len(art) == 3 and "≥ 150m" in art[0]["text"]

    t30 = _legend_for("tempo30",
                       {"green_kmh": 30, "amber_kmh": 50, "default_kmh": 50})
    assert t30[0]["text"] == "≤ 30 km/h"

    inv = _legend_for("nightlife_inverted",
                       {"radius_m": 300, "green_max": 3, "amber_max": 8})
    assert inv[0]["text"] == "≤ 3 within 300m"

    print("scoring.legends selfcheck OK")
