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

    # nightlife_density (numeric-only) + gesix / gesix_newcomer (5-quintile)
    # don't fit a 3-band legend — skip.
    return []


if __name__ == "__main__":
    kita = _legend_for("kita", {"green_count": 3, "green_m": 400, "amber_m": 800})
    assert len(kita) == 3 and kita[0]["tier"] == TIER_GREEN
    assert "3 kitas within 400m" in kita[0]["text"]
    tram = _legend_for("tram_transit", {"green_m": 500, "amber_m": 1000})
    assert tram[0]["text"] == "≤500m walk"
    assert _legend_for("gesix", {}) == []
    assert _legend_for("nightlife_density", {}) == []
    assert _legend_for("unknown_key", {}) == []
    print("scoring.legends selfcheck OK")
